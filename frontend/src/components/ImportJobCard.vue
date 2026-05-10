<script setup lang="ts">
import { computed } from "vue";
import type { ImportJob } from "../types/api";
import TagChipList from "./TagChipList.vue";

const props = defineProps<{
  job: ImportJob;
}>();

const label = computed(() => {
  if (props.job.status === "queued") {
    return "排队中";
  }
  if (props.job.status === "running") {
    return "处理中";
  }
  if (props.job.status === "completed") {
    return "已完成";
  }
  if (props.job.status === "failed") {
    return "失败";
  }
  return props.job.status;
});

const displayTitle = computed(() => props.job.requested_title || props.job.source_path);
</script>

<template>
  <article class="job-card">
    <div class="job-card-header">
      <div>
        <h4>{{ displayTitle }}</h4>
        <p class="muted ellipsis">{{ job.source_path }}</p>
      </div>
      <span class="status-badge" :class="job.status">{{ label }}</span>
    </div>
    <TagChipList :tags="job.requested_tags" compact />
    <div class="progress-track">
      <div class="progress-fill" :style="{ width: `${job.progress_percent}%` }" />
    </div>
    <div class="job-card-footer">
      <span class="muted">{{ job.progress_percent }}%</span>
      <span v-if="job.error_message" class="error ellipsis">{{ job.error_message }}</span>
    </div>
  </article>
</template>
