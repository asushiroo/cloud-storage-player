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
const streamUrl = computed(() =>
  video.value ? buildAssetUrl(`/api/videos/${video.value.id}/stream`) : null,
);

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
        <video
          v-if="streamUrl"
          controls
          crossorigin="use-credentials"
          :src="streamUrl"
          style="width: 100%; max-width: 960px; border-radius: 0.75rem;"
        />
        <div class="grid two">
          <div><strong>标题：</strong>{{ video.title }}</div>
          <div><strong>MIME：</strong>{{ video.mime_type }}</div>
          <div><strong>大小：</strong>{{ video.size }}</div>
          <div><strong>时长：</strong>{{ video.duration_seconds ?? "-" }}</div>
          <div><strong>目录 ID：</strong>{{ video.folder_id ?? "-" }}</div>
          <div><strong>源路径：</strong>{{ video.source_path ?? "-" }}</div>
          <div><strong>分片数：</strong>{{ video.segment_count }}</div>
        </div>
        <p class="muted">
          当前页面已经直接消费后端流接口；目前流来自本地主机源文件，后续会切到分片/加密/百度网盘链路。
        </p>
      </template>
    </section>
  </AppShell>
</template>
