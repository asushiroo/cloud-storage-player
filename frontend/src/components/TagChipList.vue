<script setup lang="ts">
withDefaults(
  defineProps<{
    tags: string[];
    tone?: "filled" | "outline";
    compact?: boolean;
  }>(),
  {
    tone: "outline",
    compact: false,
  },
);
</script>

<template>
  <div v-if="tags.length > 0" class="tag-list">
    <span
      v-for="tag in tags"
      :key="tag"
      class="tag-chip"
      :class="[
        tone === 'filled' ? 'filled' : 'outline',
        compact ? 'compact' : null,
      ]"
    >
      {{ tag }}
    </span>
  </div>
</template>
