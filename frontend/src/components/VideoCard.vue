<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { buildAssetUrl } from "../api/http";
import type { Video } from "../types/api";
import TagChipList from "./TagChipList.vue";

const props = defineProps<{
  video: Video;
  folderName: string;
}>();

const coverUrl = computed(() => buildAssetUrl(props.video.cover_path));
const sizeText = computed(() => {
  if (props.video.size >= 1024 * 1024 * 1024) {
    return `${(props.video.size / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  }
  if (props.video.size >= 1024 * 1024) {
    return `${(props.video.size / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (props.video.size >= 1024) {
    return `${(props.video.size / 1024).toFixed(1)} KB`;
  }
  return `${props.video.size} B`;
});

const durationText = computed(() => {
  if (props.video.duration_seconds == null) {
    return "未知时长";
  }
  if (props.video.duration_seconds < 60) {
    return `${Math.round(props.video.duration_seconds)} 秒`;
  }
  const minutes = Math.floor(props.video.duration_seconds / 60);
  const seconds = Math.round(props.video.duration_seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${seconds}`;
});
</script>

<template>
  <RouterLink :to="`/videos/${video.id}`" class="video-card">
    <div class="video-card-cover">
      <img v-if="coverUrl" :src="coverUrl" :alt="video.title" class="video-card-image" />
      <div v-else class="video-card-placeholder">
        <span>{{ video.title.slice(0, 1) }}</span>
      </div>
      <div class="video-card-overlay">
        <span class="metric-badge">{{ durationText }}</span>
      </div>
    </div>
    <div class="video-card-body">
      <div class="video-card-header">
        <h3>{{ video.title }}</h3>
        <p>{{ folderName }}</p>
      </div>
      <TagChipList :tags="video.tags" compact />
      <div class="video-card-meta">
        <span>{{ video.segment_count }} 个分片</span>
        <span>{{ sizeText }}</span>
      </div>
    </div>
  </RouterLink>
</template>
