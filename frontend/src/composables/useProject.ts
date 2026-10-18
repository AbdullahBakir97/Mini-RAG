import { inject, provide, ref, watch, type InjectionKey, type Ref } from "vue";

import { ApiError, api } from "@/api/client";
import type { Project } from "@/api/types";
import { displayName } from "@/lib/format";

export interface ProjectContext {
  name: Ref<string>;
  /** Null while loading, and for a project without files (the server does not know it yet). */
  project: Ref<Project | null>;
  loading: Ref<boolean>;
  error: Ref<ApiError | null>;
  refresh: () => Promise<void>;
  /** The name a file was uploaded with, from its file_id. */
  fileName: (fileId: string) => string;
  /** The project's first 100 files, for choosing what to search. */
  files: Ref<{ file_id: string; original_name: string }[]>;
}

const KEY: InjectionKey<ProjectContext> = Symbol("project");

/** Loads the project named by `name` and shares it with the views below. */
export function provideProject(name: Ref<string>): ProjectContext {
  const project = ref<Project | null>(null);
  const loading = ref(true);
  const error = ref<ApiError | null>(null);
  const names = ref<Record<string, string>>({});
  const files = ref<{ file_id: string; original_name: string }[]>([]);

  // Sources only carry file ids; the upload's own name reads better. Large
  // projects fall back to the name kept in the id.
  async function loadNames(requested: string) {
    try {
      const page = await api.files(requested, { limit: 100 });
      if (requested === name.value) {
        names.value = Object.fromEntries(page.items.map((file) => [file.file_id, file.original_name]));
        files.value = page.items.map(({ file_id, original_name }) => ({ file_id, original_name }));
      }
    } catch {
      // Ids still show a readable name.
    }
  }

  function fileName(fileId: string) {
    return names.value[fileId] ?? displayName(fileId);
  }

  async function refresh() {
    const requested = name.value;
    try {
      const loaded = await api.project(requested);
      if (requested === name.value) {
        project.value = loaded;
        error.value = null;
        void loadNames(requested);
      }
    } catch (caught) {
      if (requested !== name.value) return;
      project.value = null;
      // A project without files is not an error: it is empty.
      const notFound = caught instanceof ApiError && caught.signal === "project_not_found";
      error.value = notFound ? null : caught instanceof ApiError ? caught : new ApiError(0, "network_error");
    } finally {
      if (requested === name.value) loading.value = false;
    }
  }

  watch(
    name,
    () => {
      project.value = null;
      names.value = {};
      files.value = [];
      loading.value = true;
      void refresh();
    },
    { immediate: true },
  );

  const context = { name, project, loading, error, refresh, fileName, files };
  provide(KEY, context);
  return context;
}

export function useProject(): ProjectContext {
  const context = inject(KEY);
  if (!context) throw new Error("useProject() needs a ProjectView above it");
  return context;
}
