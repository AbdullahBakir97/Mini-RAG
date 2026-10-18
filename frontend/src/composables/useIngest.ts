import { ref, type Ref } from "vue";

import { ApiError, api } from "@/api/client";
import type { Job, ProcessOptions } from "@/api/types";
import { SUPPORTED_LABEL, isSupported } from "@/lib/fileTypes";
import { signalMessage } from "@/lib/signals";

export type Stage =
  | "queued"
  | "uploading"
  | "waiting"
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
  /** Upload progress, then indexing progress, from 0 to 1. */
  progress: number;
  fileId: string | null;
  chunks: number | null;
  error: string | null;
}

export const FINISHED: Stage[] = ["done", "duplicate", "failed", "not-indexed"];
let nextId = 1;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Takes files through the whole pipeline, one at a time: upload, then a
 * background job on the server splits it into chunks and indexes them, while
 * its progress is polled. A file that cannot be indexed (no embedding model)
 * stays chunked, and is indexed later from the project's banner.
 */
export function useIngest(
  project: Ref<string>,
  options: Ref<ProcessOptions>,
  onFileReady: () => void,
  pollMs = 600,
) {
  const jobs = ref<IngestJob[]>([]);
  const running = ref(false);
  const files = new Map<number, File>();
  const tagsOf = new Map<number, string[]>();

  function update(id: number, changes: Partial<IngestJob>) {
    jobs.value = jobs.value.map((job) => (job.id === id ? { ...job, ...changes } : job));
  }

  /** Queues the files; each gets `tags`. */
  function add(selected: File[], tags: string[] = []) {
    for (const file of selected) {
      const id = nextId++;
      const supported = isSupported(file);
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
          error: supported ? null : `Only ${SUPPORTED_LABEL} can be uploaded.`,
        },
      ];
      if (supported) {
        files.set(id, file);
        tagsOf.set(id, tags);
      }
    }
    void run();
  }

  /** Uploads the file and queues its job; null when the project has its content already. */
  async function upload(job: IngestJob, file: File): Promise<Job | null> {
    update(job.id, { stage: "uploading" });
    const tags = tagsOf.get(job.id) ?? [];
    tagsOf.delete(job.id);
    const uploaded = await api.upload(project.value, file, {
      tags,
      onProgress: (progress) => update(job.id, { progress }),
    });
    if (uploaded.signal === "file_already_uploaded") {
      update(job.id, { stage: "duplicate", progress: 1, fileId: uploaded.file_id });
      return null;
    }
    update(job.id, { stage: "waiting", progress: 0, fileId: uploaded.file_id });
    return api.createJob(project.value, uploaded.file_id, options.value);
  }

  async function follow(id: number, server: Job) {
    let chunked = false;
    while (server.status === "queued" || server.status === "running") {
      await sleep(pollMs);
      server = await api.job(project.value, server.id);
      if (server.stage === "indexing" && !chunked) {
        chunked = true;
        onFileReady();
      }
      update(id, progressOf(server));
    }
    if (server.status === "succeeded") {
      update(id, { stage: "done", progress: 1, chunks: server.chunks_count, error: null });
    } else if (server.error === "embedding_not_configured") {
      update(id, { stage: "not-indexed", error: signalMessage(server.error) });
    } else {
      update(id, { stage: "failed", error: signalMessage(server.error ?? "job_failed") });
    }
  }

  function progressOf(server: Job): Partial<IngestJob> {
    if (server.status === "running") {
      return { stage: server.stage ?? "processing", progress: server.progress };
    }
    // Queued: not started yet, or waiting to try again after a failure.
    return { stage: "waiting", progress: 0, error: server.error ? `${signalMessage(server.error)} Trying again soon.` : null };
  }

  function failed(id: number, caught: unknown) {
    update(id, { stage: "failed", error: caught instanceof ApiError ? caught.message : "Something went wrong." });
  }

  let uploading = false;
  let following = 0;
  const settle = () => {
    running.value = uploading || following > 0;
  };

  /** Uploads files one at a time; their jobs are followed side by side, as the server runs them. */
  async function run() {
    if (uploading) return;
    uploading = true;
    settle();
    try {
      for (;;) {
        const job = jobs.value.find((candidate) => candidate.stage === "queued");
        if (!job) break;
        const file = files.get(job.id)!;
        files.delete(job.id);
        try {
          const server = await upload(job, file);
          if (server === null) {
            onFileReady();
            continue;
          }
          following++;
          void follow(job.id, server)
            .catch((caught) => failed(job.id, caught))
            .finally(() => {
              following--;
              settle();
              onFileReady();
            });
        } catch (caught) {
          failed(job.id, caught);
          onFileReady();
        }
      }
    } finally {
      uploading = false;
      settle();
    }
  }

  function clearFinished() {
    jobs.value = jobs.value.filter((job) => !FINISHED.includes(job.stage));
  }

  return { jobs, running, add, clearFinished };
}
