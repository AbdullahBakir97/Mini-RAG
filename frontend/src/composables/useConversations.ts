import { reactive, ref, watch, type Ref } from "vue";

import { ApiError, api } from "@/api/client";
import type { Conversation } from "@/api/types";

const PAGE = 50;

// The conversation last open in each project, so the Ask tab returns to it.
const lastOpen = reactive<Record<string, string | null>>({});

export function lastConversation(project: string): string | null {
  return lastOpen[project] ?? null;
}

export function rememberConversation(project: string, id: string | null) {
  lastOpen[project] = id;
}

/** A project's conversations, most recently answered first. */
export function useConversations(project: Ref<string>) {
  const items = ref<Conversation[]>([]);
  const total = ref(0);
  const loading = ref(false);
  const error = ref<ApiError | null>(null);
  let loadCount = 0;

  async function fetchPage(offset: number) {
    const requested = ++loadCount;
    const name = project.value;
    loading.value = true;
    try {
      const page = await api.conversations(name, { offset, limit: PAGE });
      if (requested !== loadCount) return;
      items.value = offset ? [...items.value, ...page.items] : page.items;
      total.value = page.total;
      error.value = null;
    } catch (caught) {
      if (requested !== loadCount) return;
      // A project without files has no conversations either.
      if (caught instanceof ApiError && caught.signal === "project_not_found") {
        items.value = [];
        total.value = 0;
        error.value = null;
      } else {
        error.value = caught instanceof ApiError ? caught : new ApiError(0, "network_error");
      }
    } finally {
      if (requested === loadCount) loading.value = false;
    }
  }

  /** Reloads the first page; the list's order changes as questions are answered. */
  function refresh() {
    return fetchPage(0);
  }

  function more() {
    return fetchPage(items.value.length);
  }

  async function remove(id: string) {
    await api.deleteConversation(project.value, id);
    items.value = items.value.filter((conversation) => conversation.id !== id);
    total.value = Math.max(0, total.value - 1);
    if (lastOpen[project.value] === id) lastOpen[project.value] = null;
  }

  watch(project, () => void refresh(), { immediate: true });

  return { items, total, loading, error, refresh, more, remove };
}
