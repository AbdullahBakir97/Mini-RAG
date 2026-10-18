import { describe, expect, it } from "vitest";

import { parseEvent, readEvents } from "@/api/sse";

function streamOf(...pieces: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const piece of pieces) controller.enqueue(encoder.encode(piece));
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>) {
  const events = [];
  for await (const event of readEvents(stream)) events.push(event);
  return events;
}

describe("parseEvent", () => {
  it("reads the event name and data", () => {
    expect(parseEvent('event: delta\ndata: {"text": "Hi"}')).toEqual({ event: "delta", data: '{"text": "Hi"}' });
  });

  it("joins data lines and defaults the name", () => {
    expect(parseEvent("data: a\ndata: b")).toEqual({ event: "message", data: "a\nb" });
  });

  it("ignores comments and blocks without data", () => {
    expect(parseEvent(": keep-alive")).toBeNull();
    expect(parseEvent("event: ping")).toBeNull();
  });
});

describe("readEvents", () => {
  it("yields events split across reads", async () => {
    const events = await collect(
      streamOf('event: delta\ndata: {"text":', ' "Cats"}\n\nevent: ans', 'wer\ndata: {}\n\n'),
    );

    expect(events).toEqual([
      { event: "delta", data: '{"text": "Cats"}' },
      { event: "answer", data: "{}" },
    ]);
  });

  it("accepts CRLF line endings and a last event without a blank line", async () => {
    const events = await collect(streamOf("event: delta\r\ndata: 1\r\n\r\nevent: answer\r\ndata: 2"));

    expect(events.map((event) => event.data)).toEqual(["1", "2"]);
  });

  it("decodes characters split between reads", async () => {
    const bytes = new TextEncoder().encode("data: café\n\n");
    const split = bytes.length - 4; // inside the two bytes of "é"
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, split));
        controller.enqueue(bytes.slice(split));
        controller.close();
      },
    });

    expect(await collect(stream)).toEqual([{ event: "message", data: "café" }]);
  });
});
