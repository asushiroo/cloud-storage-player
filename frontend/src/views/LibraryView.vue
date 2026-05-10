<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import * as importsApi from "../api/imports";
import * as libraryApi from "../api/library";
import { buildAssetUrl } from "../api/http";
import AppShell from "../components/AppShell.vue";
import type { Folder, ImportJob, Video } from "../types/api";

const folders = ref<Folder[]>([]);
const videos = ref<Video[]>([]);
const importJobs = ref<ImportJob[]>([]);
const selectedFolderId = ref<number | "">("");
const sourcePath = ref("");
const title = ref("");
const loading = ref(false);
const importLoading = ref(false);
const syncLoading = ref(false);
const pollingActive = ref(false);
const message = ref("");
const error = ref("");
let pollTimer: number | null = null;

const filteredVideos = computed(() => videos.value);
const activeImportJobs = computed(() =>
  importJobs.value.filter((job) => job.status === "queued" || job.status === "running"),
);
const completedImportJobs = computed(() =>
  importJobs.value.filter((job) => job.status === "completed"),
);
const failedImportJobs = computed(() =>
  importJobs.value.filter((job) => job.status === "failed"),
);
const shouldPoll = computed(() => activeImportJobs.value.length > 0);

async function load(options?: { silent?: boolean }): Promise<void> {
  const silent = options?.silent ?? false;
  if (!silent) {
    loading.value = true;
    error.value = "";
  }
  try {
    folders.value = await libraryApi.fetchFolders();
    videos.value = await libraryApi.fetchVideos(
      selectedFolderId.value === "" ? undefined : Number(selectedFolderId.value),
    );
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

async function submitImport(): Promise<void> {
  importLoading.value = true;
  error.value = "";
  message.value = "";
  try {
    await importsApi.createImport({
      source_path: sourcePath.value,
      title: title.value || null,
      folder_id: selectedFolderId.value === "" ? null : Number(selectedFolderId.value),
    });
    sourcePath.value = "";
    title.value = "";
    message.value = "导入任务已入队，页面会自动刷新任务状态。";
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

function statusLabel(status: string): string {
  if (status === "queued") {
    return "排队中";
  }
  if (status === "running") {
    return "处理中";
  }
  if (status === "completed") {
    return "已完成";
  }
  if (status === "failed") {
    return "失败";
  }
  return status;
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
      `新建 ${result.created_video_count} 个视频`,
      `更新 ${result.updated_video_count} 个视频`,
      `失败 ${result.failed_manifest_count} 个`,
    ].join("，");
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
    <div class="stack">
      <section class="panel stack">
        <div>
          <h2>媒体库</h2>
          <p class="muted">后端通过 JSON API 提供目录、视频和导入任务数据。</p>
        </div>

        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="message">{{ message }}</p>

        <div class="grid three">
          <div class="panel stat-card">
            <div class="muted">视频总数</div>
            <strong>{{ filteredVideos.length }}</strong>
          </div>
          <div class="panel stat-card">
            <div class="muted">进行中任务</div>
            <strong>{{ activeImportJobs.length }}</strong>
          </div>
          <div class="panel stat-card">
            <div class="muted">失败任务</div>
            <strong>{{ failedImportJobs.length }}</strong>
          </div>
        </div>

        <div class="grid two">
          <div class="field">
            <label for="folder-filter">目录过滤</label>
            <select id="folder-filter" v-model="selectedFolderId" @change="() => load()">
              <option value="">全部目录</option>
              <option v-for="folder in folders" :key="folder.id" :value="folder.id">
                {{ folder.name }}
              </option>
            </select>
          </div>
        </div>

        <div class="button-row">
          <button class="button secondary" type="button" :disabled="syncLoading" @click="syncCatalog">
            {{ syncLoading ? "同步中..." : "同步远端目录" }}
          </button>
          <button class="button secondary" type="button" :disabled="loading" @click="() => load()">
            {{ loading ? "刷新中..." : "刷新列表" }}
          </button>
          <span v-if="pollingActive" class="muted">检测到导入任务正在进行，列表每 2 秒自动刷新。</span>
        </div>
      </section>

      <section class="panel stack">
        <h3>导入本地视频</h3>
        <div class="grid two">
          <div class="field">
            <label for="source-path">源文件绝对路径</label>
            <input id="source-path" v-model="sourcePath" placeholder="例如 /tmp/rieri.mp4" />
          </div>
          <div class="field">
            <label for="video-title">显示标题（可选）</label>
            <input id="video-title" v-model="title" placeholder="不填则使用文件名" />
          </div>
        </div>
        <div class="button-row">
          <button
            class="button"
            type="button"
            :disabled="importLoading || !sourcePath"
            @click="submitImport"
          >
            {{ importLoading ? "导入中..." : "创建导入任务" }}
          </button>
        </div>
      </section>

      <section class="panel stack">
        <h3>视频列表</h3>
        <p v-if="loading" class="muted">加载中...</p>
        <table v-else class="table">
          <thead>
            <tr>
              <th>封面</th>
              <th>标题</th>
              <th>目录</th>
              <th>分片数</th>
              <th>时长</th>
              <th>大小</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="video in filteredVideos" :key="video.id">
              <td>
                <img
                  v-if="video.cover_path"
                  class="cover"
                  :src="buildAssetUrl(video.cover_path) ?? undefined"
                  :alt="video.title"
                  style="max-width: 120px;"
                />
                <span v-else class="muted">无封面</span>
              </td>
              <td>
                <RouterLink :to="`/videos/${video.id}`">{{ video.title }}</RouterLink>
              </td>
              <td>{{ video.folder_id ?? "-" }}</td>
              <td>{{ video.segment_count }}</td>
              <td>{{ video.duration_seconds ?? "-" }}</td>
              <td>{{ video.size }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="panel stack">
        <h3>导入任务</h3>
        <p class="muted">
          已完成 {{ completedImportJobs.length }} 个，进行中 {{ activeImportJobs.length }} 个，失败
          {{ failedImportJobs.length }} 个。
        </p>
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>标题</th>
              <th>源路径</th>
              <th>状态</th>
              <th>进度</th>
              <th>结果</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in importJobs" :key="job.id">
              <td>{{ job.id }}</td>
              <td>{{ job.requested_title ?? "-" }}</td>
              <td>{{ job.source_path }}</td>
              <td>
                <span class="status-badge" :class="job.status">{{ statusLabel(job.status) }}</span>
              </td>
              <td style="min-width: 180px;">
                <div class="progress-track">
                  <div class="progress-fill" :style="{ width: `${job.progress_percent}%` }" />
                </div>
                <div class="muted progress-text">{{ job.progress_percent }}%</div>
              </td>
              <td>
                <RouterLink v-if="job.video_id" :to="`/videos/${job.video_id}`">查看视频</RouterLink>
                <span v-else class="muted">-</span>
              </td>
              <td>{{ job.error_message ?? "-" }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  </AppShell>
</template>
