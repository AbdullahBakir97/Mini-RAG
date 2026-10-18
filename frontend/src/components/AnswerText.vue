<script setup lang="ts">
import { computed } from "vue";

import { parseAnswer } from "@/lib/citations";

const props = defineProps<{ text: string; streaming?: boolean; cited?: number[]; active?: number | null }>();
const emit = defineEmits<{ cite: [number]; hover: [number | null] }>();

const paragraphs = computed(() => parseAnswer(props.text));
const isLast = (i: number) => i === paragraphs.value.length - 1;
// While streaming, markers are shown but not linked: the sources come with the finished answer.
const linked = (number: number) => !props.streaming && (props.cited ?? []).includes(number);
</script>

<template>
  <div class="answer-text">
    <p v-for="(parts, i) in paragraphs" :key="i">
      <template v-for="(part, j) in parts" :key="j">
        <template v-if="part.kind === 'text'">{{ part.text }}</template>
        <button
          v-else-if="linked(part.number)"
          class="cite"
          :class="{ active: active === part.number }"
          :aria-label="`Source ${part.number}`"
          @click="emit('cite', part.number)"
          @mouseenter="emit('hover', part.number)"
          @mouseleave="emit('hover', null)"
          @focus="emit('hover', part.number)"
          @blur="emit('hover', null)"
        >
          {{ part.number }}
        </button>
        <span v-else class="cite static">{{ part.number }}</span>
      </template>
      <span v-if="streaming && isLast(i)" class="caret" aria-hidden="true" />
    </p>
  </div>
</template>

<style scoped>
.answer-text {
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 15px;
  line-height: 1.65;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.cite {
  display: inline-grid;
  place-items: center;
  min-width: 20px;
  height: 18px;
  margin: 0 2px;
  padding: 0 5px;
  border: 0;
  border-radius: 5px;
  background: var(--accent-soft);
  color: var(--accent-text);
  font: 600 11.5px/1 var(--font);
  vertical-align: 2px;
  cursor: pointer;
  transition:
    background 0.15s,
    color 0.15s;
}

.cite:hover,
.cite.active {
  background: var(--accent);
  color: var(--on-accent);
}

.cite.static {
  background: var(--surface-3);
  color: var(--text-2);
  cursor: default;
}

.caret {
  display: inline-block;
  width: 7px;
  height: 1.05em;
  margin-left: 2px;
  border-radius: 1px;
  background: var(--accent);
  vertical-align: -0.15em;
  animation: blink 1s steps(2, start) infinite;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}
</style>
