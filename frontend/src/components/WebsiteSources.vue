<script setup lang="ts">
import { ChevronDown, ChevronRight, Globe, LoaderCircle, Plus, RefreshCw, Trash2, TriangleAlert } from "@lucide/vue";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { ApiError, api } from "@/api/client";
import type { SourcePage, WebsiteSource } from "@/api/types";
import { useToasts } from "@/composables/useToasts";
import { formatNumber, formatRelative } from "@/lib/format";

const props = defineProps<{ project: string }>();
const emit = defineEmits<{ synced: [] }>();
const toasts = useToasts();

const INTERVALS = [
  { hours: 6, label: "Every 6 hours" },
  { hours: 24, label: "Every day" },
  { hours: 168, label: "Every week" },
  { hours: 0, label: "Only when asked" },
];

const sources = ref<WebsiteSource[]>([]);
const loaded = ref(false);

// While a sync runs or is due, the list is refreshed every few seconds.
const POLL_MS = 3000;
let timer: ReturnType<typeof setTimeout> | null = null;

function busy(source: WebsiteSource): boolean {
  return source.syncing || (source.next_sync_at !== null && Date.parse(source.next_sync_at) <= Date.now() + 1000);
}

async function load() {
  if (timer) clearTimeout(timer);
  timer = null;
  try {
    const before = new Map(sources.value.map((s) => [s.id, s.last_synced_at]));
    const items = (await api.sources(props.project)).items;
    const finished = items.some((s) => before.has(s.id) && before.get(s.id) !== s.last_synced_at);
    sources.value = items;
    if (finished) emit("synced");
  } catch (caught) {
    // A project that has no files yet has no sources either.
    if (!(caught instanceof ApiError && caught.signal === "project_not_found")) {
      toasts.error("Website sources could not be loaded", caught instanceof ApiError ? caught.message : undefined);
    }
    sources.value = [];
  } finally {
    loaded.value = true;
  }
  if (sources.value.some(busy)) timer = setTimeout(load, POLL_MS);
}

// Adding one.
const url = ref("");
const maxPages = ref(50);
const interval = ref(24);
const adding = ref(false);
const validUrl = computed(() => /^https?:\/\/[^\s/]+/i.test(url.value.trim()));

async function add() {
  adding.value = true;
  try {
    await api.createSource(props.project, {
      url: url.value.trim(),
      max_pages: maxPages.value,
      sync_interval_hours: interval.value,
    });
    toasts.success("Website added", "Its pages are being fetched; each one is indexed as it arrives.");
    url.value = "";
    await load();
    emit("synced");
  } catch (caught) {
    toasts.error("The website could not be added", caught instanceof ApiError ? caught.message : undefined);
  } finally {
    adding.value = false;
  }
}

// Each source's actions, and its pages.
const acting = ref<string | null>(null);
const confirming = ref<string | null>(null);
const keepFiles = ref(false);
const open = ref<string | null>(null);
const pages = ref<SourcePage[]>([]);

async function sync(source: WebsiteSource) {
  acting.value = source.id;
  try {
    await api.syncSource(props.project, source.id);
    await load();
  } catch (caught) {
    toasts.error("The sync could not be started", caught instanceof ApiError ? caught.message : undefined);
  } finally {
    acting.value = null;
  }
}

async function remove(source: WebsiteSource) {
  acting.value = source.id;
  try {
    await api.deleteSource(props.project, source.id, keepFiles.value);
    toasts.success(
      "Website removed",
      keepFiles.value ? "Its pages stay in the project." : "Its pages were deleted from the project.",
    );
    if (open.value === source.id) open.value = null;
    await load();
    emit("synced");
  } catch (caught) {
    toasts.error("The website could not be removed", caught instanceof ApiError ? caught.message : undefined);
  } finally {
    acting.value = null;
    confirming.value = null;
    keepFiles.value = false;
  }
}

async function toggle(source: WebsiteSource) {
  open.value = open.value === source.id ? null : source.id;
  pages.value = [];
  if (!open.value) return;
  try {
    pages.value = (await api.sourcePages(props.project, source.id)).items;
  } catch (caught) {
    toasts.error("The pages could not be loaded", caught instanceof ApiError ? caught.message : undefined);
  }
}

function status(source: WebsiteSource): string {
  if (source.syncing) return "Syncing now…";
  if (source.last_synced_at === null) return "Waiting for its first sync";
  const last = `Synced ${formatRelative(source.last_synced_at)}`;
  if (source.next_sync_at === null) return last;
  return `${last} · next ${formatRelative(source.next_sync_at)}`;
}

function intervalLabel(hours: number): string {
  return INTERVALS.find((i) => i.hours === hours)?.label ?? `Every ${hours} hours`;
}

watch(
  () => props.project,
  () => {
    sources.value = [];
    open.value = null;
    void load();
  },
);
onMounted(load);
onBeforeUnmount(() => {
  if (timer) clearTimeout(timer);
});
defineExpose({ load });
</script>

<template>
  <section class="card sources" aria-labelledby="websites-title">
    <div class="head">
      <Globe :size="18" class="subtle" aria-hidden="true" />
      <div>
        <h3 id="websites-title">Websites</h3>
        <p class="muted small">
          Keep a website's pages in this project: its pages under the address are fetched by following their links
          (robots.txt is obeyed), indexed, and synced again on a schedule, adding new pages, replacing changed ones and
          removing the ones that are gone.
        </p>
      </div>
    </div>

    <form class="add" @submit.prevent="add">
      <label class="field grow">
        <span>Address</span>
        <input v-model="url" class="input" type="url" required maxlength="2000" placeholder="https://docs.example.com/guide/" />
      </label>
      <label class="field">
        <span>Most pages</span>
        <input v-model.number="maxPages" class="input pages-input" type="number" min="1" max="1000" required />
      </label>
      <label class="field">
        <span>Sync</span>
        <select v-model.number="interval" class="input">
          <option v-for="option in INTERVALS" :key="option.hours" :value="option.hours">{{ option.label }}</option>
        </select>
      </label>
      <button class="btn btn-primary" type="submit" :disabled="adding || !validUrl || maxPages < 1 || maxPages > 1000">
        <LoaderCircle v-if="adding" :size="16" class="spin" />
        <Plus v-else :size="16" />
        Add website
      </button>
    </form>

    <ul v-if="sources.length" class="list">
      <li v-for="source in sources" :key="source.id" class="item">
        <div class="row">
          <button
            class="btn btn-ghost btn-icon btn-sm"
            :aria-expanded="open === source.id"
            :aria-label="`Pages of ${source.url}`"
            @click="toggle(source)"
          >
            <ChevronDown v-if="open === source.id" :size="16" />
            <ChevronRight v-else :size="16" />
          </button>
          <div class="info">
            <a class="url mono" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.url }}</a>
            <p class="small muted">
              <LoaderCircle v-if="source.syncing" :size="12" class="spin" aria-hidden="true" />
              {{ formatNumber(source.pages_count) }} of at most {{ formatNumber(source.max_pages) }} pages ·
              {{ intervalLabel(source.sync_interval_hours) }} · {{ status(source) }}
            </p>
            <p v-if="source.last_error" class="small error">
              <TriangleAlert :size="13" aria-hidden="true" />
              The last sync failed: {{ source.last_error }}. Its pages are kept.
            </p>
          </div>
          <div v-if="confirming === source.id" class="confirm">
            <label class="small keep"><input v-model="keepFiles" type="checkbox" /> Keep its pages</label>
            <button class="btn btn-danger btn-sm" :disabled="acting !== null" @click="remove(source)">Remove</button>
            <button class="btn btn-ghost btn-sm" @click="confirming = null">Cancel</button>
          </div>
          <div v-else class="buttons">
            <button class="btn btn-sm" :disabled="acting !== null || busy(source)" @click="sync(source)">
              <RefreshCw :size="14" :class="{ spin: source.syncing }" />
              Sync now
            </button>
            <button
              class="btn btn-ghost btn-icon btn-sm"
              :aria-label="`Remove ${source.url}`"
              title="Remove"
              @click="confirming = source.id"
            >
              <Trash2 :size="15" />
            </button>
          </div>
        </div>
        <ul v-if="open === source.id" class="pages">
          <li v-if="!pages.length" class="subtle small">No pages yet.</li>
          <li v-for="page in pages" :key="page.url" class="small">
            <a class="mono" :href="page.url" target="_blank" rel="noopener noreferrer">{{ page.url }}</a>
            <span class="subtle"> · {{ formatRelative(page.synced_at) }}</span>
          </li>
        </ul>
      </li>
    </ul>
    <p v-else-if="loaded" class="subtle small">No websites yet.</p>
  </section>
</template>

<style scoped>
.sources {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
}

.head {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.head h3 {
  margin: 0 0 2px;
  font-size: 15px;
}

.head p {
  margin: 0;
}

.add {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--text-2);
  font-size: 12.5px;
  font-weight: 550;
}

.field.grow {
  flex: 1 1 300px;
}

.field.grow .input {
  width: 100%;
}

.pages-input {
  width: 96px;
}

.list,
.pages {
  margin: 0;
  padding: 0;
  list-style: none;
}

.list {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--border);
}

.item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.info {
  flex: 1;
  min-width: 200px;
}

.info p {
  margin: 2px 0 0;
  display: flex;
  align-items: center;
  gap: 5px;
}

.url {
  font-size: 13px;
  word-break: break-all;
}

.error {
  color: var(--danger);
}

.buttons,
.confirm {
  display: flex;
  align-items: center;
  gap: 6px;
}

.keep {
  display: flex;
  align-items: center;
  gap: 5px;
}

.pages {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 8px 0 0 40px;
  word-break: break-all;
}
</style>
