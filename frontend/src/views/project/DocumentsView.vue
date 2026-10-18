<script setup lang="ts">
import {
  CircleAlert,
  CircleCheck,
  Clock,
  Eye,
  FileText,
  FileType2,
  LoaderCircle,
  RefreshCw,
  Settings2,
} from "@lucide/vue";
import { computed, onMounted, ref, watch } from "vue";

import { ApiError, api } from "@/api/client";
import type { FileInfo, ProcessOptions } from "@/api/types";
import ChunkDrawer from "@/components/ChunkDrawer.vue";
import FileDropzone from "@/components/FileDropzone.vue";
import PagerControls from "@/components/PagerControls.vue";
import { type Stage, useIngest } from "@/composables/useIngest";
import { useProject } from "@/composables/useProject";
import { useProjects } from "@/composables/useProjects";
import { useToasts } from "@/composables/useToasts";
import { formatBytes, formatNumber, formatRelative } from "@/lib/format";

const LIMIT = 20;
const { name, project, refresh: refreshProject } = useProject();
const { refresh: refreshProjects } = useProjects();
const toasts = useToasts();

const files = ref<FileInfo[]>([]);
const total = ref(0);
const offset = ref(0);
const loading = ref(true);
const chunkCounts = ref<Record<string, number>>({});
const reprocessing = ref<string | null>(null);
const viewing = ref<FileInfo | null>(null);

const showOptions = ref(false);
const options = ref<ProcessOptions>({ chunk_size: 1000, overlap_size: 200 });
const optionsProblem = computed(() => {
  const { chunk_size, overlap_size } = options.value;
  if (!Number.isInteger(chunk_size) || chunk_size < 1 || chunk_size > 100_000) return "Chunk size must be 1–100,000.";
  if (!Number.isInteger(overlap_size) || overlap_size < 0) return "Overlap must be 0 or more.";
  if (overlap_size >= chunk_size) return "Overlap must be smaller than the chunk size.";
  return null;
});

async function load(at = offset.value) {
  try {
    const page = await api.files(name.value, { offset: at, limit: LIMIT });
    files.value = page.items;
    total.value = page.total;
    offset.value = at;
    void loadChunkCounts(page.items);
  } catch (caught) {
    // A new project has no files, so the server does not know it yet.
    if (!(caught instanceof ApiError && caught.signal === "project_not_found")) {
      toasts.error("Could not load the files", caught instanceof ApiError ? caught.message : undefined);
    }
    files.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

async function loadChunkCounts(items: FileInfo[]) {
  const counts = await Promise.all(
    items.map((file) =>
      api
        .chunks(name.value, file.file_id, { limit: 1 })
        .then((page) => [file.file_id, page.total] as const)
        .catch(() => null),
    ),
  );
  chunkCounts.value = { ...chunkCounts.value, ...Object.fromEntries(counts.filter((c) => c !== null)) };
}

let refreshTimer: ReturnType<typeof setTimeout> | undefined;
function onFileReady() {
  // Several files can finish close together: refresh once.
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => {
    void load();
    void refreshProject();
    void refreshProjects();
  }, 150);
}

const { jobs, running, add, clearFinished } = useIngest(name, options, onFileReady);

function addFiles(selected: File[]) {
  if (optionsProblem.value) {
    showOptions.value = true;
    toasts.error("Check the chunking options", optionsProblem.value);
    return;
  }
  add(selected);
}

async function reprocess(file: FileInfo) {
  if (optionsProblem.value) {
    showOptions.value = true;
    return;
  }
  reprocessing.value = file.file_id;
  try {
    const result = await api.process(name.value, file.file_id, options.value);
    chunkCounts.value = { ...chunkCounts.value, [file.file_id]: result.chunks_count };
    try {
      await api.index(name.value, file.file_id);
      toasts.success("File re-processed", `${formatNumber(result.chunks_count)} chunks, indexed.`);
    } catch (caught) {
      toasts.info("File re-processed, not indexed", caught instanceof ApiError ? caught.message : undefined);
    }
  } catch (caught) {
    toasts.error("Re-processing failed", caught instanceof ApiError ? caught.message : undefined);
  } finally {
    reprocessing.value = null;
    await refreshProject();
  }
}

const stageLabel: Record<Stage, string> = {
  queued: "Waiting",
  uploading: "Uploading",
  processing: "Splitting into chunks",
  indexing: "Indexing",
  done: "Ready",
  "not-indexed": "Not indexed",
  failed: "Failed",
};

const busyStages: Stage[] = ["uploading", "processing", "indexing"];
const finished = computed(() => jobs.value.some((job) => ["done", "failed", "not-indexed"].includes(job.stage)));
const isEmpty = computed(() => !loading.value && total.value === 0 && jobs.value.length === 0);

function kind(file: FileInfo) {
  return file.content_type === "application/pdf" ? "PDF" : "TXT";
}

watch(name, () => {
  loading.value = true;
  chunkCounts.value = {};
  void load(0);
});
onMounted(() => load(0));
</script>

<template>
  <section class="documents">
    <div class="toolbar">
      <div>
        <h2>Documents</h2>
        <p class="muted small">Files are split into chunks and indexed as soon as they are uploaded.</p>
      </div>
      <button class="btn btn-sm" :aria-expanded="showOptions" @click="showOptions = !showOptions">
        <Settings2 :size="14" /> Chunking
      </button>
    </div>

    <div v-if="showOptions" class="options card">
      <label class="field">
        <span>Chunk size (characters)</span>
        <input v-model.number="options.chunk_size" class="input" type="number" min="1" max="100000" step="100" />
      </label>
      <label class="field">
        <span>Overlap (characters)</span>
        <input v-model.number="options.overlap_size" class="input" type="number" min="0" step="50" />
      </label>
      <p class="hint small" :class="optionsProblem ? 'error' : 'subtle'">
        {{
          optionsProblem ??
          "Applies to new uploads and to re-processing. Overlap repeats the end of one chunk at the start of the next."
        }}
      </p>
    </div>

    <FileDropzone :large="isEmpty" @files="addFiles" />

    <div v-if="jobs.length" class="jobs card">
      <div class="jobs-head">
        <h3>{{ running ? "Processing uploads…" : "Uploads" }}</h3>
        <button v-if="finished && !running" class="btn btn-ghost btn-sm" @click="clearFinished">Clear</button>
      </div>
      <ul class="job-list">
        <li v-for="job in jobs" :key="job.id" class="job">
          <span class="job-icon" :class="job.stage">
            <LoaderCircle v-if="busyStages.includes(job.stage)" :size="16" class="spin" />
            <CircleCheck v-else-if="job.stage === 'done'" :size="16" />
            <CircleAlert v-else-if="job.stage === 'failed' || job.stage === 'not-indexed'" :size="16" />
            <Clock v-else :size="16" />
          </span>
          <div class="job-body">
            <div class="job-line">
              <span class="job-name">{{ job.name }}</span>
              <span class="subtle small">{{ formatBytes(job.size) }}</span>
            </div>
            <div v-if="job.stage === 'uploading'" class="progress" role="progressbar" :aria-valuenow="Math.round(job.progress * 100)" aria-valuemin="0" aria-valuemax="100">
              <span :style="{ width: `${job.progress * 100}%` }" />
            </div>
            <p class="small" :class="job.error ? 'job-error' : 'subtle'">
              {{ job.error ?? stageLabel[job.stage] }}
              <template v-if="job.stage === 'done' && job.chunks !== null">· {{ formatNumber(job.chunks) }} chunks</template>
            </p>
          </div>
          <span class="badge" :class="{
            'badge-success': job.stage === 'done',
            'badge-danger': job.stage === 'failed',
            'badge-warning': job.stage === 'not-indexed',
            'badge-accent': busyStages.includes(job.stage),
          }">{{ stageLabel[job.stage] }}</span>
        </li>
      </ul>
    </div>

    <div v-if="loading" class="card table-card">
      <div v-for="i in 3" :key="i" class="skeleton row-skeleton" />
    </div>

    <div v-else-if="total > 0" class="card table-card">
      <table class="table">
        <thead>
          <tr>
            <th>Name</th>
            <th class="hide-sm">Size</th>
            <th class="num">Chunks</th>
            <th class="hide-sm">Uploaded</th>
            <th class="actions-col"><span class="visually-hidden">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="file in files" :key="file.file_id">
            <td>
              <div class="file-name">
                <span class="file-icon" :class="kind(file).toLowerCase()">
                  <FileType2 v-if="kind(file) === 'PDF'" :size="16" />
                  <FileText v-else :size="16" />
                </span>
                <div class="file-text">
                  <button class="link-button" @click="viewing = file">{{ file.original_name }}</button>
                  <span class="subtle small mono file-id" :title="file.file_id">{{ file.file_id }}</span>
                </div>
              </div>
            </td>
            <td class="hide-sm muted">{{ formatBytes(file.size_bytes) }}</td>
            <td class="num">
              <span v-if="chunkCounts[file.file_id] === undefined" class="skeleton count-skeleton" />
              <span v-else-if="chunkCounts[file.file_id] === 0" class="badge badge-warning">None</span>
              <span v-else>{{ formatNumber(chunkCounts[file.file_id]!) }}</span>
            </td>
            <td class="hide-sm muted" :title="file.created_at">{{ formatRelative(file.created_at) }}</td>
            <td class="actions-col">
              <button class="btn btn-ghost btn-sm btn-icon" title="View chunks" aria-label="View chunks" @click="viewing = file">
                <Eye :size="15" />
              </button>
              <button
                class="btn btn-ghost btn-sm btn-icon"
                title="Re-process with the current chunking options"
                aria-label="Re-process"
                :disabled="reprocessing !== null"
                @click="reprocess(file)"
              >
                <LoaderCircle v-if="reprocessing === file.file_id" :size="15" class="spin" />
                <RefreshCw v-else :size="15" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="table-foot">
        <PagerControls :total="total" :offset="offset" :limit="LIMIT" noun="files" @change="load" />
      </div>
    </div>

    <p v-else-if="!jobs.length && project === null" class="subtle small center">
      Upload a document to start. The project is saved with its first file.
    </p>

    <ChunkDrawer :project="name" :file="viewing" @close="viewing = null" />
  </section>
</template>

<style scoped>
.documents {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.toolbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 220px)) 1fr;
  align-items: end;
  gap: 14px;
  padding: 14px 16px;
}

@media (max-width: 720px) {
  .options {
    grid-template-columns: 1fr 1fr;
  }

  .options .hint {
    grid-column: 1 / -1;
  }
}

.hint {
  align-self: center;
}

.error,
.job-error {
  color: var(--danger);
}

.jobs {
  padding: 12px 14px;
}

.jobs-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.job-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.job {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--border);
}

.job:first-child {
  border-top: 0;
}

.job-icon {
  display: grid;
  flex: none;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text-3);
}

.job-icon.done {
  background: var(--success-soft);
  color: var(--success);
}

.job-icon.failed {
  background: var(--danger-soft);
  color: var(--danger);
}

.job-icon.not-indexed {
  background: var(--warning-soft);
  color: var(--warning);
}

.job-icon.uploading,
.job-icon.processing,
.job-icon.indexing {
  background: var(--accent-soft);
  color: var(--accent);
}

.job-body {
  flex: 1;
  min-width: 0;
}

.job-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.job-name {
  overflow: hidden;
  font-weight: 550;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress {
  height: 4px;
  margin: 6px 0 4px;
  border-radius: 2px;
  background: var(--surface-3);
  overflow: hidden;
}

.progress span {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width 0.2s;
}

@media (max-width: 560px) {
  .job > .badge {
    display: none;
  }
}

.table-card {
  overflow: hidden;
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table th {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-3);
  font-size: 12px;
  font-weight: 600;
  text-align: left;
  letter-spacing: 0.02em;
}

.table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}

.table tbody tr:last-child td {
  border-bottom: 0;
}

.table tbody tr:hover {
  background: var(--surface-2);
}

.num {
  text-align: right !important;
  font-variant-numeric: tabular-nums;
}

.actions-col {
  width: 1%;
  white-space: nowrap;
  text-align: right;
}

@media (max-width: 640px) {
  .hide-sm {
    display: none;
  }
}

.file-name {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.file-icon {
  display: grid;
  flex: none;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text-2);
}

.file-icon.pdf {
  background: var(--danger-soft);
  color: var(--danger);
}

.file-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.link-button {
  padding: 0;
  border: 0;
  background: none;
  color: var(--text);
  font: inherit;
  font-weight: 550;
  text-align: left;
  overflow-wrap: anywhere;
  cursor: pointer;
}

.link-button:hover {
  color: var(--accent);
}

.file-id {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.count-skeleton {
  display: inline-block;
  width: 32px;
  height: 14px;
}

.row-skeleton {
  height: 44px;
  margin: 8px;
}

.table-foot {
  padding: 0 14px;
}

.table-foot:has(.pager) {
  padding: 10px 14px;
  border-top: 1px solid var(--border);
}

.center {
  text-align: center;
}
</style>
