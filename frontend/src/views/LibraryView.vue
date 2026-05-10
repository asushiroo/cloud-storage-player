<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { buildAssetUrl } from "../api/http";
import * as importsApi from "../api/imports";
import * as libraryApi from "../api/library";
import AppShell from "../components/AppShell.vue";
import ImportJobCard from "../components/ImportJobCard.vue";
import TagChipList from "../components/TagChipList.vue";
import VideoCard from "../components/VideoCard.vue";
import type { Folder, ImportJob, Video } from "../types/api";
import { parseTagInput } from "../utils/tags";

const folders = ref<Folder[]>([]);
const videos = ref<Video[]>([]);
const importJobs = ref<ImportJob[]>([]);
const selectedFolderId = ref<number | "">("");
const importFolderId = ref<number | "">("");
const searchInput = ref("");
const appliedSearchText = ref("");
const activeTag = ref("");
const sourcePath = ref("");
const title = ref("");
const tagInput = ref("");
const loading = ref(false);
const importLoading = ref(false);
const syncLoading = ref(false);
const pollingActive = ref(false);
const message = ref("");
const error = ref("");
let pollTimer: number | null = null;

const folderMap = computed(() =>
  new Map(folders.value.map((folder) => [folder.id, folder.name])),
);
const filteredVideos = computed(() => videos.value);
const featuredVideo = computed(() => filteredVideos.value[0] ?? null);
const featuredCoverUrl = computed(() => buildAssetUrl(featuredVideo.value?.cover_path ?? null));
const totalSegments = computed(() =>
  filteredVideos.value.reduce((sum, video) => sum + video.segment_count, 0),
);
const totalTags = computed(() => {
  const tagSet = new Set<string>();
  for (const video of filteredVideos.value) {
    for (const tag of video.tags) {
      tagSet.add(tag);
    }
  }
  return tagSet.size;
});
const availableTags = computed(() => {
  const counts = new Map<string, number>();
  for (const video of videos.value) {
    for (const tag of video.tags) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name));
});
const activeImportJobs = computed(() =>
  importJobs.value.filter((job) => job.status === "queued" || job.status === "running"),
);
const recentImportJobs = computed(() => importJobs.value.slice(0, 6));
const shouldPoll = computed(() => activeImportJobs.value.length > 0);
const hasActiveLibraryFilters = computed(() => Boolean(appliedSearchText.value || activeTag.value));

async function load(options?: { silent?: boolean }): Promise<void> {
  const silent = options?.silent ?? false;
  if (!silent) {
    loading.value = true;
    error.value = "";
  }
  try {
    folders.value = await libraryApi.fetchFolders();
    videos.value = await libraryApi.fetchVideos({
      folderId: selectedFolderId.value === "" ? undefined : Number(selectedFolderId.value),
      q: appliedSearchText.value,
      tag: activeTag.value || undefined,
    });
    importJobs.value = await importsApi.fetchImportJobs();
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "加载媒体库失败。";
    } else {
      error.value = "加载媒体库失败。";
    }
  } finally {
    if (!silent) {
      loading.value = false;
    }
  }
}

async function applyLibraryFilters(): Promise<void> {
  appliedSearchText.value = searchInput.value.trim();
  await load();
}

async function toggleTagFilter(tag: string): Promise<void> {
  activeTag.value = activeTag.value === tag ? "" : tag;
  await load();
}

async function clearLibraryFilters(): Promise<void> {
  searchInput.value = "";
  appliedSearchText.value = "";
  activeTag.value = "";
  await load();
}

async function submitImport(): Promise<void> {
  importLoading.value = true;
  error.value = "";
  message.value = "";
  try {
    await importsApi.createImport({
      source_path: sourcePath.value,
      title: title.value || null,
      folder_id: importFolderId.value === "" ? null : Number(importFolderId.value),
      tags: parseTagInput(tagInput.value),
    });
    sourcePath.value = "";
    title.value = "";
    tagInput.value = "";
    message.value = "导入任务已创建，系统会自动轮询最新状态。";
    await load();
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "创建导入任务失败。";
    } else {
      error.value = "创建导入任务失败。";
    }
  } finally {
    importLoading.value = false;
  }
}

async function syncCatalog(): Promise<void> {
  syncLoading.value = true;
  error.value = "";
  message.value = "";
  try {
    const result = await libraryApi.syncRemoteCatalog();
    await load();
    message.value = [
      `发现 ${result.discovered_manifest_count} 个 manifest`,
      `新增 ${result.created_video_count} 个视频`,
      `更新 ${result.updated_video_count} 个视频`,
      `失败 ${result.failed_manifest_count} 个`,
    ].join(" · ");
    if (result.errors.length > 0) {
      error.value = result.errors.join("；");
    }
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "同步远端目录失败。";
    } else {
      error.value = "同步远端目录失败。";
    }
  } finally {
    syncLoading.value = false;
  }
}

function startPolling(): void {
  if (pollTimer !== null) {
    return;
  }
  pollingActive.value = true;
  pollTimer = window.setInterval(() => {
    void load({ silent: true });
  }, 2000);
}

function stopPolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
  pollingActive.value = false;
}

watch(
  shouldPoll,
  (value) => {
    if (value) {
      startPolling();
    } else {
      stopPolling();
    }
  },
  { immediate: true },
);

onMounted(() => {
  void load();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <AppShell>
    <div class="page-stack">
      <section class="hero surface" :style="featuredCoverUrl ? { backgroundImage: `url(${featuredCoverUrl})` } : undefined">
        <div class="hero-overlay" />
        <div class="hero-content">
          <div class="eyebrow">Kyoo Inspired Library</div>
          <h1>你的局域网私人影库</h1>
          <p>
            视频通过 Windows 主机导入、分片、加密并回放。现在前端改成了更接近 third/Kyoo
            的视觉语言：大圆角、强调色按钮、内容卡片和标签胶囊。
          </p>
          <TagChipList
            :tags="featuredVideo?.tags ?? []"
            tone="filled"
          />
          <div class="hero-actions">
            <button class="button" type="button" :disabled="syncLoading" @click="syncCatalog">
              {{ syncLoading ? "同步中..." : "同步远端目录" }}
            </button>
            <button class="button ghost" type="button" :disabled="loading" @click="() => load()">
              {{ loading ? "刷新中..." : "刷新媒体库" }}
            </button>
          </div>
          <div class="stat-row">
            <div class="stat-pill">
              <strong>{{ filteredVideos.length }}</strong>
              <span>视频</span>
            </div>
            <div class="stat-pill">
              <strong>{{ activeImportJobs.length }}</strong>
              <span>导入中</span>
            </div>
            <div class="stat-pill">
              <strong>{{ totalSegments }}</strong>
              <span>分片</span>
            </div>
            <div class="stat-pill">
              <strong>{{ totalTags }}</strong>
              <span>标签</span>
            </div>
          </div>
        </div>
      </section>

      <p v-if="error" class="error banner-message">{{ error }}</p>
      <p v-if="message" class="banner-message success">{{ message }}</p>

      <section class="surface control-bar">
        <div class="field">
          <label for="folder-filter">目录过滤</label>
          <select id="folder-filter" v-model="selectedFolderId" @change="() => load()">
            <option value="">全部目录</option>
            <option v-for="folder in folders" :key="folder.id" :value="folder.id">
              {{ folder.name }}
            </option>
          </select>
        </div>
        <div class="field">
          <label for="library-search">标题 / 路径 / 标签搜索</label>
          <div class="search-inline">
            <input
              id="library-search"
              v-model="searchInput"
              placeholder="例如 动画、weekend、tmp/rieri"
              @keyup.enter="applyLibraryFilters"
            />
            <button class="button" type="button" :disabled="loading" @click="applyLibraryFilters">
              搜索
            </button>
            <button
              v-if="hasActiveLibraryFilters"
              class="button ghost"
              type="button"
              :disabled="loading"
              @click="clearLibraryFilters"
            >
              清空
            </button>
          </div>
        </div>
        <div class="control-hint">
          <span v-if="pollingActive" class="muted">检测到导入任务，列表每 2 秒自动刷新。</span>
          <span v-else-if="activeTag" class="muted">当前标签过滤：{{ activeTag }}</span>
        </div>
      </section>

      <section v-if="availableTags.length > 0" class="surface section-card">
        <div class="section-heading">
          <div>
            <div class="eyebrow">Tags</div>
            <h2>标签筛选</h2>
          </div>
          <span class="muted">{{ availableTags.length }} 个可见标签</span>
        </div>
        <div class="tag-filter-row">
          <button
            class="chip-button"
            :class="{ active: !activeTag }"
            type="button"
            @click="toggleTagFilter('')"
          >
            全部标签
          </button>
          <button
            v-for="tag in availableTags"
            :key="tag.name"
            class="chip-button"
            :class="{ active: activeTag === tag.name }"
            type="button"
            @click="toggleTagFilter(tag.name)"
          >
            <span>{{ tag.name }}</span>
            <strong>{{ tag.count }}</strong>
          </button>
        </div>
      </section>

      <div class="content-grid">
        <section class="surface section-card">
          <div class="section-heading">
            <div>
              <div class="eyebrow">Import</div>
              <h2>导入本地视频</h2>
            </div>
          </div>

          <div class="stack">
            <div class="field">
              <label for="source-path">源文件绝对路径</label>
              <input id="source-path" v-model="sourcePath" placeholder="例如 /root/cloud-storage-player/tmp/rieri.mp4" />
            </div>
            <div class="field">
              <label for="video-title">显示标题</label>
              <input id="video-title" v-model="title" placeholder="不填则使用文件名" />
            </div>
            <div class="field">
              <label for="import-folder">导入目录</label>
              <select id="import-folder" v-model="importFolderId">
                <option value="">未分类</option>
                <option v-for="folder in folders" :key="folder.id" :value="folder.id">
                  {{ folder.name }}
                </option>
              </select>
            </div>
            <div class="field">
              <label for="video-tags">自定义标签</label>
              <input id="video-tags" v-model="tagInput" placeholder="例如 动画, 收藏, 周末重看" />
            </div>
            <TagChipList :tags="parseTagInput(tagInput)" compact />
            <div class="button-row">
              <button
                class="button"
                type="button"
                :disabled="importLoading || !sourcePath"
                @click="submitImport"
              >
                {{ importLoading ? "创建中..." : "创建导入任务" }}
              </button>
            </div>
          </div>
        </section>

        <section class="surface section-card">
          <div class="section-heading">
            <div>
              <div class="eyebrow">Queue</div>
              <h2>最近任务</h2>
            </div>
          </div>
          <div v-if="recentImportJobs.length === 0" class="empty-state">
            <p>还没有导入任务。</p>
          </div>
          <div v-else class="job-list">
            <ImportJobCard
              v-for="job in recentImportJobs"
              :key="job.id"
              :job="job"
            />
          </div>
        </section>
      </div>

      <section class="section-stack">
        <div class="section-heading">
          <div>
            <div class="eyebrow">Library</div>
            <h2>视频列表</h2>
          </div>
          <span class="muted">{{ filteredVideos.length }} 个条目</span>
        </div>

        <div v-if="loading" class="surface empty-state">
          <p>加载中...</p>
        </div>
        <div v-else-if="filteredVideos.length === 0" class="surface empty-state">
          <p>当前没有视频，先导入一个试试。</p>
        </div>
        <div v-else class="media-grid">
          <VideoCard
            v-for="video in filteredVideos"
            :key="video.id"
            :video="video"
            :folder-name="folderMap.get(video.folder_id ?? -1) ?? '未分类'"
          />
        </div>
      </section>
    </div>
  </AppShell>
</template>
