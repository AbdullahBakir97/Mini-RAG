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

  it("asks in a conversation", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ signal: "answer_success" }));
    vi.stubGlobal("fetch", fetch);

    await api.ask("demo", "And why?", { top_k: 5, min_score: null, conversation_id: "c-1" });

    const [url, init] = fetch.mock.calls[0]!;
    expect(url).toBe("/api/v1/ask/demo");
    expect(JSON.parse(init.body)).toEqual({ question: "And why?", top_k: 5, min_score: null, conversation_id: "c-1" });
  });

  it("starts, reads, lists and deletes conversations", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ id: "c-1", title: null }, { status: 201 }))
      .mockResolvedValueOnce(Response.json({ id: "c-1", title: "Why?", messages: [] }))
      .mockResolvedValueOnce(Response.json({ total: 0, offset: 0, limit: 50, items: [] }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);

    expect((await api.createConversation("demo")).id).toBe("c-1");
    expect((await api.conversation("demo", "c-1")).title).toBe("Why?");
    expect((await api.conversations("demo")).total).toBe(0);
    await expect(api.deleteConversation("demo", "c-1")).resolves.toBeUndefined();

    const calls = fetch.mock.calls.map(([url, init]) => [init?.method ?? "GET", url]);
    expect(calls).toEqual([
      ["POST", "/api/v1/projects/demo/conversations"],
      ["GET", "/api/v1/projects/demo/conversations/c-1"],
      ["GET", "/api/v1/projects/demo/conversations?offset=0&limit=50"],
      ["DELETE", "/api/v1/projects/demo/conversations/c-1"],
    ]);
  });

  it("reports a conversation that no longer exists", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ signal: "conversation_not_found" }, { status: 404 })));

    await expect(api.conversation("demo", "c-1")).rejects.toMatchObject({
      status: 404,
      message: "This conversation no longer exists.",
    });
  });

  it("rates and unrates answers, and lists rated ones", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ id: 7, feedback: { rating: "down" } }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(Response.json({ up: 1, down: 0, total: 1, offset: 0, limit: 20, items: [] }));
    vi.stubGlobal("fetch", fetch);

    await api.rate("demo", "c-1", 7, "down", "Wrong window.");
    await api.unrate("demo", "c-1", 7);
    expect((await api.feedback("demo", { rating: "up" })).up).toBe(1);

    const [putUrl, put] = fetch.mock.calls[0]!;
    const [deleteUrl, del] = fetch.mock.calls[1]!;
    const [listUrl] = fetch.mock.calls[2]!;
    expect([put.method, putUrl]).toEqual(["PUT", "/api/v1/projects/demo/conversations/c-1/messages/7/feedback"]);
    expect(JSON.parse(put.body)).toEqual({ rating: "down", comment: "Wrong window." });
    expect([del.method, deleteUrl]).toEqual(["DELETE", "/api/v1/projects/demo/conversations/c-1/messages/7/feedback"]);
    expect(listUrl).toBe("/api/v1/projects/demo/feedback?offset=0&limit=20&rating=up");
  });

  it("deletes files and projects", async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response(null, { status: 204 })));
    vi.stubGlobal("fetch", fetch);

    await api.deleteFile("my docs", "a_guide.txt");
    await api.deleteProject("my docs");

    const [fileUrl, fileInit] = fetch.mock.calls[0]!;
    const [projectUrl, projectInit] = fetch.mock.calls[1]!;
    expect([fileInit.method, fileUrl]).toEqual(["DELETE", "/api/v1/projects/my%20docs/files/a_guide.txt"]);
    expect([projectInit.method, projectUrl]).toEqual(["DELETE", "/api/v1/projects/my%20docs"]);
  });

  it("queues and follows jobs", async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(Response.json({ id: "j 1" })));
    vi.stubGlobal("fetch", fetch);

    await api.createJob("demo", "a_cats.txt", { chunk_size: 500, overlap_size: 50 });
    await api.job("demo", "j 1");

    const [createUrl, create] = fetch.mock.calls[0]!;
    expect([create.method, createUrl]).toEqual(["POST", "/api/v1/projects/demo/jobs"]);
    expect(JSON.parse(create.body)).toEqual({ file_id: "a_cats.txt", chunk_size: 500, overlap_size: 50 });
    expect(fetch.mock.calls[1]![0]).toBe("/api/v1/projects/demo/jobs/j%201");
  });

  it("manages webhooks and reads their deliveries", async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(Response.json({ items: [] })));
    vi.stubGlobal("fetch", fetch);

    await api.createWebhook("demo", { url: "https://example.com/h", events: ["job.failed"] });
    await api.pingWebhook("demo", "w-1");
    await api.deliveries("demo", "w-1", { offset: 10 });

    const [createUrl, create] = fetch.mock.calls[0]!;
    expect([create.method, createUrl]).toEqual(["POST", "/api/v1/projects/demo/webhooks"]);
    expect(JSON.parse(create.body)).toEqual({ url: "https://example.com/h", events: ["job.failed"] });
    expect(fetch.mock.calls[1]![0]).toBe("/api/v1/projects/demo/webhooks/w-1/ping");
    expect(fetch.mock.calls[2]![0]).toBe("/api/v1/projects/demo/webhooks/w-1/deliveries?offset=10&limit=10");
  });
});
