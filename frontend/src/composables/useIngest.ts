import { ref, type Ref } from "vue";

import { ApiError, api } from "@/api/client";
import type { ProcessOptions } from "@/api/types";

export type Stage =
  | "queued"
  | "uploading"
  | "processing"
  | "indexing"
  | "done"
  | "duplicate"
  | "not-indexed"
  | "failed";

export interface IngestJob {
  id: number;
  name: string;
  size: number;
  stage: Stage;
  /** Upload progress from 0 to 1. */
  progress: number;
  fileId: string | null;
  chunks: number | null;
  error: string | null;
}

const ACCEPTED = /\.(pdf|txt)$/i;
export const FINISHED: Stage[] = ["done", "duplicate", "failed", "not-indexed"];
let nextId = 1;

/**
 * Takes files through the whole pipeline, one at a time: upload, split into
 * chunks, and index. A file that cannot be indexed (no embedding model) stays
 * chunked, and is indexed later from the project's banner.
 */
export function useIngest(project: Ref<string>, options: Ref<ProcessOptions>, onFileReady: () => void) {
  const jobs = ref<IngestJob[]>([]);
  const running = ref(false);
  const files = new Map<number, File>();

  function update(id: number, changes: Partial<IngestJob>) {
    jobs.value = jobs.value.map((job) => (job.id === id ? { ...job, ...changes } : job));
  }

  function add(selected: File[]) {
    for (const file of selected) {
      const id = nextId++;
      const supported = ACCEPTED.test(file.name) || ["application/pdf", "text/plain"].includes(file.type);
      jobs.value = [
        ...jobs.value,
        {
          id,
          name: file.name,
          size: file.size,
          stage: supported ? "queued" : "failed",
          progress: 0,
          fileId: null,
          chunks: null,
          error: supported ? null : "Only PDF and plain-text files can be uploaded.",
        },
      ];
      if (supported) files.set(id, file);
    }
    void run();
  }

  async function ingest(job: IngestJob, file: File) {
    update(job.id, { stage: "uploading" });
    const upload = await api.upload(project.value, file, {
      onProgress: (progress) => update(job.id, { progress }),
    });
    // The project has this content already: nothing more to do.
    if (upload.signal === "file_already_uploaded") {
      update(job.id, { stage: "duplicate", progress: 1, fileId: upload.file_id });
      return;
    }
    update(job.id, { stage: "processing", progress: 1, fileId: upload.file_id });
    const processed = await api.process(project.value, upload.file_id, options.value);
    update(job.id, { stage: "indexing", chunks: processed.chunks_count });
    onFileReady();
    try {
      await api.index(project.value, upload.file_id);
      update(job.id, { stage: "done" });
    } catch (caught) {
      if (caught instanceof ApiError && caught.signal === "embedding_not_configured") {
        update(job.id, { stage: "not-indexed", error: caught.message });
      } else {
        throw caught;
      }
    }
  }

  async function run() {
    if (running.value) return;
    running.value = true;
    try {
      for (;;) {
        const job = jobs.value.find((candidate) => candidate.stage === "queued");
        if (!job) break;
        const file = files.get(job.id)!;
        try {
          await ingest(job, file);
        } catch (caught) {
          const current = jobs.value.find((candidate) => candidate.id === job.id);
          const failedAt = current?.stage === "indexing" ? "not-indexed" : "failed";
          update(job.id, {
            stage: failedAt,
            error: caught instanceof ApiError ? caught.message : "Something went wrong.",
          });
        } finally {
          files.delete(job.id);
          onFileReady();
        }
      }
    } finally {
      running.value = false;
    }
  }

  function clearFinished() {
    jobs.value = jobs.value.filter((job) => !FINISHED.includes(job.stage));
  }

  return { jobs, running, add, clearFinished };
}
