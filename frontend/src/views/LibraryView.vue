<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, ref } from "vue";
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
const message = ref("");
const error = ref("");

const filteredVideos = computed(() => videos.value);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
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
    loading.value = false;
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

onMounted(load);
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

        <div class="grid two">
          <div class="field">
            <label for="folder-filter">目录过滤</label>
            <select id="folder-filter" v-model="selectedFolderId" @change="load">
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
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>源路径</th>
              <th>状态</th>
              <th>进度</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in importJobs" :key="job.id">
              <td>{{ job.id }}</td>
              <td>{{ job.source_path }}</td>
              <td>{{ job.status }}</td>
              <td>{{ job.progress_percent }}%</td>
              <td>{{ job.error_message ?? "-" }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  </AppShell>
</template>
