<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { buildAssetUrl } from "../api/http";
import * as libraryApi from "../api/library";
import AppShell from "../components/AppShell.vue";
import TagChipList from "../components/TagChipList.vue";
import type { Video } from "../types/api";
import { formatTagInput, parseTagInput } from "../utils/tags";

const route = useRoute();

const video = ref<Video | null>(null);
const tagInput = ref("");
const error = ref("");
const message = ref("");
const loading = ref(false);
const savingTags = ref(false);

const coverUrl = computed(() => buildAssetUrl(video.value?.cover_path ?? null));
const streamUrl = computed(() =>
  video.value ? buildAssetUrl(`/api/videos/${video.value.id}/stream`) : null,
);
const videoSizeText = computed(() => {
  if (!video.value) {
    return "-";
  }
  if (video.value.size >= 1024 * 1024 * 1024) {
    return `${(video.value.size / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  }
  if (video.value.size >= 1024 * 1024) {
    return `${(video.value.size / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${video.value.size} B`;
});

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    video.value = await libraryApi.fetchVideo(Number(route.params.videoId));
    tagInput.value = formatTagInput(video.value.tags);
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

async function saveTags(): Promise<void> {
  if (!video.value) {
    return;
  }
  savingTags.value = true;
  error.value = "";
  message.value = "";
  try {
    video.value = await libraryApi.updateVideoTags(video.value.id, parseTagInput(tagInput.value));
    tagInput.value = formatTagInput(video.value.tags);
    message.value = "标签已保存。";
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "保存标签失败。";
    } else {
      error.value = "保存标签失败。";
    }
  } finally {
    savingTags.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppShell>
    <div class="page-stack">
      <p v-if="error" class="error banner-message">{{ error }}</p>
      <p v-if="message" class="banner-message success">{{ message }}</p>

      <section
        v-if="video"
        class="hero detail-hero surface"
        :style="coverUrl ? { backgroundImage: `url(${coverUrl})` } : undefined"
      >
        <div class="hero-overlay" />
        <div class="hero-content">
          <div class="eyebrow">Player</div>
          <h1>{{ video.title }}</h1>
          <p>浏览器直接请求后端 Range 流；解密发生在服务端，浏览器只接收原始视频字节。</p>
          <TagChipList :tags="video.tags" tone="filled" />
          <div class="stat-row">
            <div class="stat-pill">
              <strong>{{ video.segment_count }}</strong>
              <span>分片</span>
            </div>
            <div class="stat-pill">
              <strong>{{ video.duration_seconds ?? "-" }}</strong>
              <span>时长</span>
            </div>
            <div class="stat-pill">
              <strong>{{ videoSizeText }}</strong>
              <span>大小</span>
            </div>
          </div>
        </div>
      </section>

      <section v-if="loading" class="surface empty-state">
        <p>加载中...</p>
      </section>

      <template v-else-if="video">
        <section class="surface section-card player-card">
          <video
            v-if="streamUrl"
            controls
            crossorigin="use-credentials"
            :src="streamUrl"
            class="player-frame"
          />
        </section>

        <div class="content-grid">
          <section class="surface section-card">
            <div class="section-heading">
              <div>
                <div class="eyebrow">Metadata</div>
                <h2>视频信息</h2>
              </div>
            </div>
            <div class="meta-grid">
              <div class="meta-item">
                <span class="muted">MIME</span>
                <strong>{{ video.mime_type }}</strong>
              </div>
              <div class="meta-item">
                <span class="muted">目录 ID</span>
                <strong>{{ video.folder_id ?? "-" }}</strong>
              </div>
              <div class="meta-item">
                <span class="muted">大小</span>
                <strong>{{ videoSizeText }}</strong>
              </div>
              <div class="meta-item">
                <span class="muted">源路径</span>
                <strong class="wrap-anywhere">{{ video.source_path ?? "-" }}</strong>
              </div>
            </div>
          </section>

          <section class="surface section-card">
            <div class="section-heading">
              <div>
                <div class="eyebrow">Tags</div>
                <h2>自定义标签</h2>
              </div>
            </div>
            <div class="stack">
              <TagChipList :tags="video.tags" />
              <div class="field">
                <label for="video-tags-editor">编辑标签</label>
                <input
                  id="video-tags-editor"
                  v-model="tagInput"
                  placeholder="例如 动画, 收藏, 入睡前"
                />
              </div>
              <TagChipList :tags="parseTagInput(tagInput)" compact />
              <div class="button-row">
                <button class="button" type="button" :disabled="savingTags" @click="saveTags">
                  {{ savingTags ? "保存中..." : "保存标签" }}
                </button>
              </div>
            </div>
          </section>
        </div>
      </template>
    </div>
  </AppShell>
</template>
