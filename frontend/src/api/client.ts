import { signalMessage } from "@/lib/signals";

import { readEvents } from "./sse";
import type {
  Answer,
  AskOptions,
  Chunk,
  Conversation,
  ConversationDetail,
  ConversationMessage,
  FeedbackList,
  FileInfo,
  Health,
  IndexResult,
  Page,
  ProcessOptions,
  ProcessResult,
  Project,
  ProjectListItem,
  ProjectUsage,
  Rating,
  SearchOptions,
  SearchResult,
  UploadResult,
  Welcome,
} from "./types";

const BASE = "/api/v1";

/** An error response of the API, or a failure to reach it. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly signal: string,
    message = signalMessage(signal),
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Turns an error response into an ApiError: `{"signal"}` bodies, or FastAPI's 422 `{"detail"}`. */
export function errorFromBody(status: number, body: unknown): ApiError {
  if (body && typeof body === "object") {
    if ("signal" in body && typeof body.signal === "string") return new ApiError(status, body.signal);
    if ("detail" in body && Array.isArray(body.detail) && body.detail.length > 0) {
      const [first] = body.detail as { msg?: string; loc?: unknown[] }[];
      const field = first?.loc?.at(-1);
      const detail = [field, first?.msg].filter(Boolean).join(": ");
      return new ApiError(status, "validation_error", detail || signalMessage("validation_error"));
    }
  }
  return new ApiError(status, `http_${status}`, `The server answered with status ${status}.`);
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(BASE + path, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw errorFromBody(response.status, body);
  }
  return response;
}

async function get<T>(path: string, params?: Record<string, number | string>): Promise<T> {
  const query = params ? "?" + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])) : "";
  return (await send(path + query)).json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const init: RequestInit = { method: "POST", signal };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  return (await send(path, init)).json() as Promise<T>;
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const response = await send(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return response.json() as Promise<T>;
}

async function remove(path: string): Promise<void> {
  await send(path, { method: "DELETE" });
}

const project = (name: string) => encodeURIComponent(name);
const conversations = (name: string) => `/projects/${project(name)}/conversations`;
const feedbackPath = (name: string, conversationId: string, messageId: number) =>
  `${conversations(name)}/${encodeURIComponent(conversationId)}/messages/${messageId}/feedback`;

export interface PageParams {
  offset?: number;
  limit?: number;
}

export interface UploadOptions {
  onProgress?: (fraction: number) => void;
  signal?: AbortSignal;
}

export interface StreamHandlers {
  onDelta: (text: string) => void;
}

export const api = {
  welcome: () => get<Welcome>("/"),

  /** The health check answers 503 with the same body when the database is down. */
  async health(): Promise<Health> {
    try {
      const response = await fetch(`${BASE}/health`);
      return (await response.json()) as Health;
    } catch {
      throw new ApiError(0, "network_error");
    }
  },

  projects: (page: PageParams = {}) =>
    get<Page<ProjectListItem>>("/projects", { offset: page.offset ?? 0, limit: page.limit ?? 100 }),
  project: (name: string) => get<Project>(`/projects/${project(name)}`),
  usage: (name: string) => get<ProjectUsage>(`/projects/${project(name)}/usage`),
  /** Deletes the project with all its files, chunks, answers and conversations. */
  deleteProject: (name: string) => remove(`/projects/${project(name)}`),
  deleteFile: (name: string, fileId: string) => remove(`/projects/${project(name)}/files/${encodeURIComponent(fileId)}`),
  files: (name: string, page: PageParams = {}) =>
    get<Page<FileInfo>>(`/projects/${project(name)}/files`, { offset: page.offset ?? 0, limit: page.limit ?? 100 }),
  chunks: (name: string, fileId: string, page: PageParams = {}) =>
    get<Page<Chunk>>(`/projects/${project(name)}/files/${encodeURIComponent(fileId)}/chunks`, {
      offset: page.offset ?? 0,
      limit: page.limit ?? 20,
    }),

  /** Uploads with XMLHttpRequest, because fetch cannot report upload progress. */
  upload(name: string, file: File, options: UploadOptions = {}): Promise<UploadResult> {
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open("POST", `${BASE}/data/upload/${project(name)}`);
      request.responseType = "json";
      request.upload.onprogress = (event) => {
        if (event.lengthComputable) options.onProgress?.(event.loaded / event.total);
      };
      request.onload = () => {
        if (request.status >= 200 && request.status < 300) resolve(request.response as UploadResult);
        else reject(errorFromBody(request.status, request.response));
      };
      request.onerror = () => reject(new ApiError(0, "network_error"));
      request.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
      options.signal?.addEventListener("abort", () => request.abort());
      const form = new FormData();
      form.append("file", file, file.name);
      request.send(form);
    });
  },

  process: (name: string, fileId: string, options: ProcessOptions) =>
    post<ProcessResult>(`/data/process/${project(name)}`, { file_id: fileId, ...options }),
  index: (name: string, fileId?: string) =>
    post<IndexResult>(`/index/${project(name)}`, fileId ? { file_id: fileId } : undefined),
  search: (name: string, query: string, options: SearchOptions) =>
    post<SearchResult>(`/search/${project(name)}`, { query, ...options }),
  conversations: (name: string, page: PageParams = {}) =>
    get<Page<Conversation>>(conversations(name), { offset: page.offset ?? 0, limit: page.limit ?? 50 }),
  createConversation: (name: string) => post<Conversation>(conversations(name)),
  conversation: (name: string, id: string) =>
    get<ConversationDetail>(`${conversations(name)}/${encodeURIComponent(id)}`),
  deleteConversation: (name: string, id: string) => remove(`${conversations(name)}/${encodeURIComponent(id)}`),

  /** Rates an answer in a conversation, replacing any rating it had. */
  rate: (name: string, conversationId: string, messageId: number, rating: Rating, comment?: string) =>
    put<ConversationMessage>(feedbackPath(name, conversationId, messageId), { rating, comment: comment || null }),
  unrate: (name: string, conversationId: string, messageId: number) =>
    remove(feedbackPath(name, conversationId, messageId)),
  feedback: (name: string, options: PageParams & { rating?: Rating } = {}) =>
    get<FeedbackList>(`/projects/${project(name)}/feedback`, {
      offset: options.offset ?? 0,
      limit: options.limit ?? 20,
      ...(options.rating ? { rating: options.rating } : {}),
    }),

  /** With `conversation_id`, the question follows on from that conversation and is added to it. */
  ask: (name: string, question: string, options: AskOptions, signal?: AbortSignal) =>
    post<Answer>(`/ask/${project(name)}`, { question, ...options }, signal),

  /** Streams an answer: text pieces go to `onDelta`, the finished Answer is returned. */
  async askStream(
    name: string,
    question: string,
    options: AskOptions,
    handlers: StreamHandlers,
    signal?: AbortSignal,
  ): Promise<Answer> {
    const response = await send(`/ask/${project(name)}/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ question, ...options }),
      signal,
    });
    if (!response.body) throw new ApiError(0, "network_error");
    for await (const event of readEvents(response.body)) {
      const data = JSON.parse(event.data) as Record<string, unknown>;
      if (event.event === "delta") handlers.onDelta(String(data.text ?? ""));
      else if (event.event === "answer") return data as unknown as Answer;
      else if (event.event === "error") throw new ApiError(502, String(data.signal ?? "llm_failed"));
    }
    throw new ApiError(502, "llm_failed", "The answer stream ended before the answer was complete.");
  },
};
