<script setup lang="ts">
import { ExternalLink, FileText } from "@lucide/vue";
import { computed, ref } from "vue";

import ScoreBar from "@/components/ScoreBar.vue";
import { highlight } from "@/lib/citations";

const props = defineProps<{
  fileId: string;
  fileName: string;
  chunkIndex: number;
  page: number | null | undefined;
  score: number;
  text: string;
  number?: number;
  active?: boolean;
  query?: string;
}>();
const emit = defineEmits<{ open: [] }>();

const expanded = ref(false);
const long = computed(() => props.text.length > 360);
const pieces = computed(() => highlight(props.text, props.query ?? ""));
</script>

<template>
  <article class="source" :class="{ active }">
    <header class="head">
      <span v-if="number !== undefined" class="number">{{ number }}</span>
      <FileText v-else :size="15" class="subtle" />
      <span class="file" :title="fileId">{{ fileName }}</span>
      <span v-if="page" class="badge">p. {{ page }}</span>
      <span class="badge mono">#{{ chunkIndex }}</span>
      <span class="spacer" />
      <ScoreBar :score="score" />
      <button class="btn btn-ghost btn-icon btn-sm" title="Open in the document" aria-label="Open in the document" @click="emit('open')">
        <ExternalLink :size="14" />
      </button>
    </header>
    <p class="text" :class="{ clamped: long && !expanded }">
      <template v-for="(piece, i) in pieces" :key="i">
        <mark v-if="piece.match">{{ piece.text }}</mark>
        <template v-else>{{ piece.text }}</template>
      </template>
    </p>
    <button v-if="long" class="more" @click="expanded = !expanded">{{ expanded ? "Show less" : "Show more" }}</button>
  </article>
</template>

<style scoped>
.source {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}

.source.active {
  border-color: var(--accent);
  box-shadow: var(--focus);
}

.head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 8px;
  margin-bottom: 6px;
}

.number {
  display: grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 6px;
  background: var(--accent);
  color: var(--on-accent);
  font-size: 12px;
  font-weight: 650;
}

.file {
  max-width: 100%;
  overflow: hidden;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.spacer {
  flex: 1;
}

.text {
  color: var(--text-2);
  font-size: 13.5px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.clamped {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
  overflow: hidden;
}

mark {
  border-radius: 3px;
  background: color-mix(in srgb, var(--warning) 22%, transparent);
  color: inherit;
}

.more {
  margin-top: 4px;
  padding: 0;
  border: 0;
  background: none;
  color: var(--accent);
  font: inherit;
  font-size: 12.5px;
  font-weight: 550;
  cursor: pointer;
}
</style>
