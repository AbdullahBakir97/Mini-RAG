import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, errorFromBody } from "@/api/client";

function sseResponse(body: string) {
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("errorFromBody", () => {
  it("reads the signal of an error response", () => {
    const error = errorFromBody(503, { signal: "llm_not_configured" });

    expect(error.signal).toBe("llm_not_configured");
    expect(error.message).toMatch(/No language model is configured/);
  });

  it("reads FastAPI validation errors", () => {
    const error = errorFromBody(422, { detail: [{ loc: ["body", "question"], msg: "String should have at least 1 character" }] });

    expect(error.signal).toBe("validation_error");
    expect(error.message).toBe("question: String should have at least 1 character");
  });
});

describe("api", () => {
  it("turns error responses into ApiErrors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ signal: "project_not_found" }, { status: 404 })));

    await expect(api.project("demo")).rejects.toMatchObject({ status: 404, signal: "project_not_found" });
  });

  it("reports an unreachable server", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(api.projects()).rejects.toEqual(new ApiError(0, "network_error"));
  });

  it("streams deltas and returns the answer", async () => {
    const answer = { signal: "answer_success", answer: "Cats purr [1].", citations: [], prompt_version: "answer-v1" };
    const fetch = vi.fn().mockResolvedValue(
      sseResponse(
        'event: delta\ndata: {"text": "Cats"}\n\n' +
          'event: delta\ndata: {"text": " purr [1]."}\n\n' +
          `event: answer\ndata: ${JSON.stringify(answer)}\n\n`,
      ),
    );
    vi.stubGlobal("fetch", fetch);
    const deltas: string[] = [];

    const result = await api.askStream("demo", "Do cats purr?", { top_k: 5, min_score: null }, {
      onDelta: (text) => deltas.push(text),
    });

    expect(deltas).toEqual(["Cats", " purr [1]."]);
    expect(result).toEqual(answer);
    const [url, init] = fetch.mock.calls[0]!;
    expect(url).toBe("/api/v1/ask/demo/stream");
    expect(JSON.parse(init.body)).toEqual({ question: "Do cats purr?", top_k: 5, min_score: null });
  });

  it("raises the error event of a stream", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse('event: error\ndata: {"signal": "llm_failed"}\n\n')));

    await expect(
      api.askStream("demo", "q", { top_k: 5, min_score: null }, { onDelta: () => {} }),
    ).rejects.toMatchObject({ status: 502, signal: "llm_failed" });
  });

  it("fails when a stream ends without an answer", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse('event: delta\ndata: {"text": "Ca"}\n\n')));

    await expect(
      api.askStream("demo", "q", { top_k: 5, min_score: null }, { onDelta: () => {} }),
    ).rejects.toMatchObject({ signal: "llm_failed" });
  });

  it("encodes project names and file ids in paths", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ total: 0, offset: 0, limit: 20, items: [] }));
    vi.stubGlobal("fetch", fetch);

    await api.chunks("my_project", "abc_notes.txt", { offset: 20 });

    expect(fetch.mock.calls[0]![0]).toBe("/api/v1/projects/my_project/files/abc_notes.txt/chunks?offset=20&limit=20");
  });
});
