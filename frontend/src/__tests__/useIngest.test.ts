import { flushPromises } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

import { api } from "@/api/client";
import type { Job } from "@/api/types";
import { useIngest } from "@/composables/useIngest";

afterEach(() => vi.restoreAllMocks());

function serverJob(changes: Partial<Job> = {}): Job {
  return {
    id: "j-1",
    file_id: "a_cats.txt",
    status: "queued",
    stage: null,
    progress: 0,
    chunks_count: null,
    attempts: 0,
    max_attempts: 3,
    chunk_size: 500,
    overlap_size: 50,
    error: null,
    created_at: "2026-10-18T10:00:00Z",
    started_at: null,
    finished_at: null,
    ...changes,
  };
}

function setUp() {
  const onFileReady = vi.fn();
  const ingest = useIngest(ref("demo"), ref({ chunk_size: 500, overlap_size: 50 }), onFileReady, 0);
  return { ...ingest, onFileReady };
}

async function settle() {
  for (let i = 0; i < 10; i++) {
    await new Promise((resolve) => setTimeout(resolve, 0));
    await flushPromises();
  }
}

const cats = () => new File(["Cats purr."], "cats.txt", { type: "text/plain" });

describe("useIngest", () => {
  it("uploads the file and follows its job until it is indexed", async () => {
    vi.spyOn(api, "upload").mockResolvedValue({ signal: "file_uploaded_successfully", file_id: "a_cats.txt" } as never);
    const createJob = vi.spyOn(api, "createJob").mockResolvedValue(serverJob());
    const seen: string[] = [];
    const states = [
      serverJob({ status: "running", stage: "processing" }),
      serverJob({ status: "running", stage: "indexing", progress: 0.5 }),
      serverJob({ status: "succeeded", stage: "indexing", progress: 1, chunks_count: 3 }),
    ];
    const { jobs, add, onFileReady } = setUp();
    vi.spyOn(api, "job").mockImplementation(async () => {
      seen.push(`${jobs.value[0]!.stage} ${jobs.value[0]!.progress}`);
      return states.shift()!;
    });

    add([cats()]);
    await settle();

    expect(createJob).toHaveBeenCalledWith("demo", "a_cats.txt", { chunk_size: 500, overlap_size: 50 });
    expect(seen).toEqual(["waiting 0", "processing 0", "indexing 0.5"]);
    expect(jobs.value[0]).toMatchObject({ stage: "done", fileId: "a_cats.txt", chunks: 3, progress: 1 });
    // Once when the chunks exist, once when the job ended.
    expect(onFileReady).toHaveBeenCalledTimes(2);
  });

  it("uploads the next file while the server works on the last one", async () => {
    const calls: string[] = [];
    vi.spyOn(api, "upload").mockImplementation(async (_project, file) => {
      calls.push(`upload ${file.name}`);
      return { signal: "file_uploaded_successfully", file_id: `a_${file.name}` } as never;
    });
    vi.spyOn(api, "createJob").mockImplementation(async (_project, fileId) => serverJob({ id: fileId }));
    vi.spyOn(api, "job").mockImplementation(async (_project, id) => {
      calls.push(`job ${id}`);
      return serverJob({ id, status: "succeeded", chunks_count: 1 });
    });
    const { jobs, add, running } = setUp();

    add([cats(), new File(["Dogs bark."], "dogs.txt", { type: "text/plain" })]);
    expect(running.value).toBe(true);
    await settle();

    expect(calls.slice(0, 2)).toEqual(["upload cats.txt", "upload dogs.txt"]);
    expect(jobs.value.map((job) => job.stage)).toEqual(["done", "done"]);
    expect(running.value).toBe(false);
  });

  it("shows a retry, then the failure", async () => {
    vi.spyOn(api, "upload").mockResolvedValue({ signal: "file_uploaded_successfully", file_id: "a_cats.txt" } as never);
    vi.spyOn(api, "createJob").mockResolvedValue(serverJob());
    const states = [
      serverJob({ status: "queued", stage: "indexing", attempts: 1, error: "embedding_failed" }),
      serverJob({ status: "failed", stage: "indexing", attempts: 3, error: "embedding_failed" }),
    ];
    const { jobs, add } = setUp();
    const errors: (string | null)[] = [];
    vi.spyOn(api, "job").mockImplementation(async () => {
      errors.push(jobs.value[0]!.error);
      return states.shift()!;
    });

    add([cats()]);
    await settle();

    expect(errors[1]).toMatch(/embedding model failed.*Trying again soon/);
    expect(jobs.value[0]).toMatchObject({ stage: "failed" });
    expect(jobs.value[0]!.error).toMatch(/embedding model failed/);
  });

  it("keeps the chunks of a file that cannot be indexed", async () => {
    vi.spyOn(api, "upload").mockResolvedValue({ signal: "file_uploaded_successfully", file_id: "a_cats.txt" } as never);
    vi.spyOn(api, "createJob").mockResolvedValue(serverJob());
    vi.spyOn(api, "job").mockResolvedValue(serverJob({ status: "failed", stage: "processing", error: "embedding_not_configured" }));
    const { jobs, add } = setUp();

    add([cats()]);
    await settle();

    expect(jobs.value[0]).toMatchObject({ stage: "not-indexed" });
    expect(jobs.value[0]!.error).toMatch(/No embedding model is configured/);
  });

  it("stops at the upload when the project has the content already", async () => {
    vi.spyOn(api, "upload").mockResolvedValue({ signal: "file_already_uploaded", file_id: "a_cats.txt" } as never);
    const createJob = vi.spyOn(api, "createJob");
    const { jobs, add, clearFinished } = setUp();

    add([new File(["Cats purr."], "copy of cats.txt", { type: "text/plain" })]);
    await settle();

    expect(createJob).not.toHaveBeenCalled();
    expect(jobs.value[0]).toMatchObject({ stage: "duplicate", fileId: "a_cats.txt", error: null });

    clearFinished();
    expect(jobs.value).toEqual([]);
  });
});
