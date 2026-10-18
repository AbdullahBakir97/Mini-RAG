// A Server-Sent Events reader for POST responses, which EventSource cannot make.

export interface ServerEvent {
  event: string;
  data: string;
}

/** Parses one event block ("event: x\ndata: y"); comments and unknown fields are ignored. */
export function parseEvent(block: string): ServerEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length ? { event, data: data.join("\n") } : null;
}

/** Yields each event of a stream as soon as its block is complete. */
export async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<ServerEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const event = parseEvent(block);
        if (event) yield event;
      }
    }
    const last = parseEvent(buffer + decoder.decode());
    if (last) yield last;
  } finally {
    // Stop reading when the caller is done early (or fails), so the request ends too.
    await reader.cancel().catch(() => {});
  }
}
