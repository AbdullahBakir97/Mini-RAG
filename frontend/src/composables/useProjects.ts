import { computed, ref } from "vue";

import { api } from "@/api/client";
import type { ProjectListItem } from "@/api/types";

const saved = ref<ProjectListItem[]>([]);
// Projects created in this browser that have no file yet. The server only
// knows a project once a file is uploaded into it.
const drafts = ref<string[]>([]);
const loading = ref(false);
const loaded = ref(false);
const error = ref<unknown>(null);

async function refresh() {
  loading.value = true;
  try {
    saved.value = (await api.projects()).items;
    drafts.value = drafts.value.filter((name) => !saved.value.some((project) => project.name === name));
    error.value = null;
  } catch (caught) {
    error.value = caught;
  } finally {
    loading.value = false;
    loaded.value = true;
  }
}

function addDraft(name: string) {
  if (!drafts.value.includes(name) && !saved.value.some((project) => project.name === name)) {
    drafts.value = [...drafts.value, name];
  }
}

const names = computed(() =>
  [...new Set([...saved.value.map((project) => project.name), ...drafts.value])].sort((a, b) =>
    a.localeCompare(b),
  ),
);

export const PROJECT_NAME = /^[A-Za-z0-9_-]{1,64}$/;

/** The list of projects, shared by every view. */
export function useProjects() {
  return { projects: saved, drafts, names, loading, loaded, error, refresh, addDraft };
}
