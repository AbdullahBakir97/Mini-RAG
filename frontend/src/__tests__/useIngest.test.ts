import { flushPromises } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

import { api } from "@/api/client";
import { useIngest } from "@/composables/useIngest";

afterEach(() => vi.restoreAllMocks());

function setUp() {
  const onFileReady = vi.fn();
  const ingest = useIngest(ref("demo"), ref({ chunk_size: 500, overlap_size: 50 }), onFileReady);
  return { ...ingest, onFileReady };
}

describe("useIngest", () => {
  it("uploads, splits and indexes a file", async () => {
    vi.spyOn(api, "upload").mockResolvedValue({ signal: "file_uploaded_successfully", file_id: "a_cats.txt" } as never);
    const process = vi.spyOn(api, "process").mockResolvedValue({ chunks_count: 3 } as never);
    vi.spyOn(api, "index").mockResolvedValue({} as never);
    const { jobs, add } = setUp();

    add([new File(["Cats purr."], "cats.txt", { type: "text/plain" })]);
    await flushPromises();

    expect(process).toHaveBeenCalledWith("demo", "a_cats.txt", { chunk_size: 500, overlap_size: 50 });
    expect(jobs.value[0]).toMatchObject({ stage: "done", fileId: "a_cats.txt", chunks: 3 });
  });

  it("stops at the upload when the project has the content already", async () => {
    vi.spyOn(api, "upload").mockResolvedValue({ signal: "file_already_uploaded", file_id: "a_cats.txt" } as never);
    const process = vi.spyOn(api, "process");
    const { jobs, add, clearFinished } = setUp();

    add([new File(["Cats purr."], "copy of cats.txt", { type: "text/plain" })]);
    await flushPromises();

    expect(process).not.toHaveBeenCalled();
    expect(jobs.value[0]).toMatchObject({ stage: "duplicate", fileId: "a_cats.txt", error: null });

    clearFinished();
    expect(jobs.value).toEqual([]);
  });
});
