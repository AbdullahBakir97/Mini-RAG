<script setup lang="ts">
import { computed } from "vue";

import { formatScore } from "@/lib/format";

const props = defineProps<{ score: number }>();
// Cosine similarity runs from -1 to 1, but useful matches sit between 0 and 1.
const width = computed(() => `${Math.max(0, Math.min(1, props.score)) * 100}%`);
</script>

<template>
  <span class="score" :title="`Similarity ${formatScore(score)} (1 is a perfect match)`">
    <span class="track"><span class="fill" :style="{ width }" /></span>
    <span class="value mono">{{ formatScore(score) }}</span>
  </span>
</template>

<style scoped>
.score {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.track {
  width: 64px;
  height: 5px;
  border-radius: 3px;
  background: var(--surface-3);
  overflow: hidden;
}

.fill {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: var(--accent);
}

.value {
  color: var(--text-2);
  font-size: 12px;
}
</style>
