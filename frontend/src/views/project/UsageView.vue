<script setup lang="ts">
import { Info } from "@lucide/vue";
import { computed, onMounted, ref, watch } from "vue";

import { ApiError, api } from "@/api/client";
import type { ProjectUsage } from "@/api/types";
import { useProject } from "@/composables/useProject";
import { formatCost, formatNumber, formatPercent } from "@/lib/format";

const { name } = useProject();
const usage = ref<ProjectUsage | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);

async function load() {
  loading.value = true;
  try {
    usage.value = await api.usage(name.value);
    error.value = null;
  } catch (caught) {
    const empty = caught instanceof ApiError && caught.signal === "project_not_found";
    usage.value = empty
      ? { answers: 0, answered: 0, input_tokens: 0, output_tokens: 0, cost_usd: 0, unpriced_answers: 0 }
      : null;
    error.value = empty ? null : caught instanceof ApiError ? caught.message : "Usage could not be loaded.";
  } finally {
    loading.value = false;
  }
}

const cards = computed(() => {
  const u = usage.value;
  if (!u) return [];
  return [
    { label: "Questions", value: formatNumber(u.answers), note: "Streamed or not" },
    {
      label: "Answered",
      value: formatPercent(u.answered, u.answers),
      note: `${formatNumber(u.answered)} answered, ${formatNumber(u.answers - u.answered)} not in the documents`,
    },
    { label: "Input tokens", value: formatNumber(u.input_tokens), note: "Prompts with their sources" },
    { label: "Output tokens", value: formatNumber(u.output_tokens), note: "Written by the model" },
    {
      label: "Cost",
      value: formatCost(u.cost_usd),
      note: u.answers ? `${formatCost(u.cost_usd / Math.max(1, u.answers - u.unpriced_answers))} per priced answer` : "US dollars",
    },
  ];
});

watch(name, load);
onMounted(load);
</script>

<template>
  <section class="usage">
    <div>
      <h2>Usage</h2>
      <p class="muted small">Tokens and cost of every answer in this project. Questions and answers are not stored.</p>
    </div>

    <div v-if="error" class="alert alert-danger">{{ error }}</div>

    <div class="grid">
      <template v-if="loading">
        <div v-for="i in 5" :key="i" class="skeleton stat-skeleton" />
      </template>
      <div v-for="card in cards" v-else :key="card.label" class="stat card">
        <p class="label">{{ card.label }}</p>
        <p class="value">{{ card.value }}</p>
        <p class="subtle small">{{ card.note }}</p>
      </div>
    </div>

    <div v-if="usage && usage.unpriced_answers > 0" class="alert">
      <Info :size="18" class="subtle" />
      <span class="muted">
        {{ formatNumber(usage.unpriced_answers) }}
        {{ usage.unpriced_answers === 1 ? "answer has" : "answers have" }} no known cost and
        {{ usage.unpriced_answers === 1 ? "is" : "are" }} not in the total. Set
        <code>LLM_INPUT_PRICE_PER_MILLION</code> and <code>LLM_OUTPUT_PRICE_PER_MILLION</code> on the server to
        price answers.
      </span>
    </div>
  </section>
</template>

<style scoped>
.usage {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 12px;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 16px;
}

.label {
  color: var(--text-2);
  font-size: 12.5px;
  font-weight: 550;
}

.value {
  font-size: 26px;
  font-weight: 650;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.stat-skeleton {
  height: 104px;
  border-radius: var(--radius);
}
</style>
