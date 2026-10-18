<script setup lang="ts">
import { X } from "@lucide/vue";
import { nextTick, onBeforeUnmount, ref, watch } from "vue";

import { ApiError, api } from "@/api/client";
import type { Chunk, FileInfo } from "@/api/types";
import PagerControls from "@/components/PagerControls.vue";
import { formatNumber } from "@/lib/format";

const props = defineProps<{
  project: string;
  file: Pick<FileInfo, "file_id" | "original_name"> | null;
  focusChunk?: number | null;
}>();
const emit = defineEmits<{ close: [] }>();

const LIMIT = 20;
const chunks = ref<Chunk[]>([]);
const total = ref(0);
const offset = ref(0);
const loading = ref(false);
const error = ref<string | null>(null);
const panel = ref<HTMLElement | null>(null);

async function load(at: number) {
  if (!props.file) return;
  loading.value = true;
  error.value = null;
  try {
    const page = await api.chunks(props.project, props.file.file_id, { offset: at, limit: LIMIT });
    chunks.value = page.items;
    total.value = page.total;
    offset.value = at;
    await nextTick();
    const target = props.focusChunk != null ? panel.value?.querySelector(`[data-chunk="${props.focusChunk}"]`) : null;
    if (target) target.scrollIntoView({ block: "center" });
    else panel.value?.querySelector(".list")?.scrollTo({ top: 0 });
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "The chunks could not be loaded.";
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.file?.file_id, props.focusChunk] as const,
  ([fileId, focus]) => {
    if (!fileId) return;
    const start = focus != null ? Math.floor(focus / LIMIT) * LIMIT : 0;
    void load(start);
  },
  { immediate: true },
);

function onKey(event: KeyboardEvent) {
  if (event.key === "Escape") emit("close");
}

// Escape closes the drawer wherever the focus is; the close button takes it on open.
watch(
  () => !!props.file,
  async (open) => {
    if (open) {
      window.addEventListener("keydown", onKey);
      await nextTick();
      panel.value?.querySelector<HTMLButtonElement>(".head button")?.focus();
    } else {
      window.removeEventListener("keydown", onKey);
    }
  },
  { immediate: true },
);
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));
</script>

<template>
  <Transition name="drawer">
    <div v-if="file" class="overlay" @click.self="emit('close')">
      <aside ref="panel" class="drawer" role="dialog" aria-modal="true" :aria-label="`Chunks of ${file.original_name}`">
        <header class="head">
          <div class="title">
            <h2>{{ file.original_name }}</h2>
            <p class="subtle small">{{ formatNumber(total) }} chunks</p>
          </div>
          <button class="btn btn-ghost btn-icon" aria-label="Close" @click="emit('close')">
            <X :size="18" />
          </button>
        </header>

        <div class="list">
          <p v-if="error" class="alert alert-danger">{{ error }}</p>
          <template v-else-if="loading && !chunks.length">
            <div v-for="i in 4" :key="i" class="skeleton chunk-skeleton" />
          </template>
          <p v-else-if="!chunks.length" class="muted empty">
            This file has not been split into chunks yet.
          </p>
          <article
            v-for="chunk in chunks"
            :key="chunk.chunk_index"
            class="chunk"
            :class="{ focus: chunk.chunk_index === focusChunk }"
            :data-chunk="chunk.chunk_index"
          >
            <div class="chunk-meta">
              <span class="badge mono">#{{ chunk.chunk_index }}</span>
              <span v-if="chunk.metadata.page" class="badge">Page {{ chunk.metadata.page }}</span>
              <span class="subtle small">{{ formatNumber(chunk.text.length) }} characters</span>
            </div>
            <p class="chunk-text">{{ chunk.text }}</p>
          </article>
        </div>

        <footer class="foot">
          <PagerControls :total="total" :offset="offset" :limit="LIMIT" noun="chunks" @change="load" />
        </footer>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  justify-content: flex-end;
  background: rgb(0 0 0 / 35%);
}

.drawer {
  display: flex;
  flex-direction: column;
  width: min(640px, 100vw);
  height: 100%;
  background: var(--surface);
  box-shadow: var(--shadow-lg);
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
}

.title {
  min-width: 0;
}

.title h2 {
  overflow-wrap: anywhere;
}

.list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  padding: 16px 20px;
  overflow-y: auto;
}

.chunk {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-2);
}

.chunk.focus {
  border-color: var(--accent);
  box-shadow: var(--focus);
}

.chunk-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.chunk-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.chunk-skeleton {
  height: 110px;
}

.empty {
  padding: 24px 0;
  text-align: center;
}

.foot {
  padding: 12px 20px;
  border-top: 1px solid var(--border);
}

.foot:empty {
  display: none;
}

.drawer-enter-active,
.drawer-leave-active {
  transition: background-color 0.2s;
}

.drawer-enter-active .drawer,
.drawer-leave-active .drawer {
  transition: transform 0.2s ease;
}

.drawer-enter-from,
.drawer-leave-to {
  background-color: transparent;
}

.drawer-enter-from .drawer,
.drawer-leave-to .drawer {
  transform: translateX(100%);
}
</style>
