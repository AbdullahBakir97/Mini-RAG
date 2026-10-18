<script setup lang="ts">
import { LoaderCircle, Search, SearchX } from "@lucide/vue";
import { ref } from "vue";

import { ApiError, api } from "@/api/client";
import type { SearchHit } from "@/api/types";
import ChunkDrawer from "@/components/ChunkDrawer.vue";
import SourceCard from "@/components/SourceCard.vue";
import { useProject } from "@/composables/useProject";

const { name, project, fileName } = useProject();

const query = ref("");
const topK = ref(10);
const minScore = ref<number | "">("");
const results = ref<SearchHit[] | null>(null);
const searched = ref("");
const loading = ref(false);
const error = ref<string | null>(null);
const opened = ref<SearchHit | null>(null);

async function search() {
  const text = query.value.trim();
  if (!text) return;
  loading.value = true;
  error.value = null;
  try {
    const response = await api.search(name.value, text, {
      top_k: Math.max(1, Math.min(50, topK.value || 10)),
      min_score: minScore.value === "" ? null : minScore.value,
    });
    results.value = response.results;
    searched.value = text;
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "The search failed.";
    results.value = null;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="search">
    <div>
      <h2>Search</h2>
      <p class="muted small">Find passages by meaning, without generating an answer. Best match first.</p>
    </div>

    <form class="search-form card" @submit.prevent="search">
      <div class="query">
        <Search :size="18" class="subtle" />
        <input
          v-model="query"
          class="query-input"
          type="search"
          maxlength="2000"
          placeholder="Search the project's documents…"
          aria-label="Search text"
          :disabled="!project"
        />
      </div>
      <div class="controls">
        <label class="inline-field">
          <span>Results</span>
          <input v-model.number="topK" class="input small-input" type="number" min="1" max="50" />
        </label>
        <label class="inline-field">
          <span>Min score</span>
          <input v-model.number="minScore" class="input small-input" type="number" min="-1" max="1" step="0.05" placeholder="Any" />
        </label>
        <button class="btn btn-primary" type="submit" :disabled="loading || !query.trim() || !project">
          <LoaderCircle v-if="loading" :size="16" class="spin" />
          Search
        </button>
      </div>
    </form>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <template v-if="results">
      <p class="subtle small">
        {{ results.length }} {{ results.length === 1 ? "result" : "results" }} for “{{ searched }}”
      </p>
      <div v-if="results.length" class="results">
        <SourceCard
          v-for="hit in results"
          :key="`${hit.file_id}-${hit.chunk_index}`"
          :file-id="hit.file_id"
          :file-name="fileName(hit.file_id)"
          :chunk-index="hit.chunk_index"
          :page="hit.metadata.page"
          :score="hit.score"
          :text="hit.text"
          :query="searched"
          @open="opened = hit"
        />
      </div>
      <div v-else class="empty card">
        <SearchX :size="22" class="subtle" />
        <p class="muted">Nothing matched. Try other words, or lower the minimum score.</p>
      </div>
    </template>

    <ChunkDrawer
      :project="name"
      :file="opened ? { file_id: opened.file_id, original_name: fileName(opened.file_id) } : null"
      :focus-chunk="opened?.chunk_index ?? null"
      @close="opened = null"
    />
  </section>
</template>

<style scoped>
.search {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.search-form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
  padding: 10px 12px 10px 14px;
}

.search-form:focus-within {
  border-color: var(--accent);
}

.query {
  display: flex;
  flex: 1 1 320px;
  align-items: center;
  gap: 10px;
}

.query-input {
  flex: 1;
  min-width: 0;
  height: 36px;
  border: 0;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 15px;
  outline: none;
  box-shadow: none;
}

.controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.inline-field {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-2);
  font-size: 12.5px;
}

.small-input {
  width: 76px;
}

.results {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.empty {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px;
}
</style>
