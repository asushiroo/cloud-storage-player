<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { buildAssetUrl } from "../api/http";
import * as libraryApi from "../api/library";
import AppShell from "../components/AppShell.vue";
import type { Video } from "../types/api";

const route = useRoute();

const video = ref<Video | null>(null);
const error = ref("");
const loading = ref(false);

const coverUrl = computed(() => buildAssetUrl(video.value?.cover_path ?? null));

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    video.value = await libraryApi.fetchVideo(Number(route.params.videoId));
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "读取视频详情失败。";
    } else {
      error.value = "读取视频详情失败。";
    }
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppShell>
    <section class="panel stack">
      <h2>视频详情</h2>
      <p v-if="loading" class="muted">加载中...</p>
      <p v-else-if="error" class="error">{{ error }}</p>
      <template v-else-if="video">
        <img v-if="coverUrl" class="cover" :src="coverUrl" :alt="video.title" />
        <div class="grid two">
          <div><strong>标题：</strong>{{ video.title }}</div>
          <div><strong>MIME：</strong>{{ video.mime_type }}</div>
          <div><strong>大小：</strong>{{ video.size }}</div>
          <div><strong>时长：</strong>{{ video.duration_seconds ?? "-" }}</div>
          <div><strong>目录 ID：</strong>{{ video.folder_id ?? "-" }}</div>
          <div><strong>源路径：</strong>{{ video.source_path ?? "-" }}</div>
        </div>
        <p class="muted">
          当前前端已经切到前后端分离架构。回放页后续将直接消费后端流接口。
        </p>
      </template>
    </section>
  </AppShell>
</template>
