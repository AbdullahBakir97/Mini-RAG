import { ref, watch, type Ref } from "vue";

import { ApiError, api } from "@/api/client";
import type { Answer, SearchOptions } from "@/api/types";

export interface Turn {
  id: number;
  question: string;
  status: "streaming" | "done" | "stopped" | "failed";
  /** The text so far while streaming; the answer's text once done. */
  text: string;
  answer: Answer | null;
  error: string | null;
  seconds: number | null;
}

export interface AskSettings extends SearchOptions {
  stream: boolean;
}

const MAX_TURNS = 30;

function storageKey(project: string) {
  return `mini-rag:ask:${project}`;
}

function restore(project: string): Turn[] {
  try {
    const saved = sessionStorage.getItem(storageKey(project));
    const turns = saved ? (JSON.parse(saved) as Turn[]) : [];
    // A reload interrupts a streaming answer.
    return turns.map((turn) => (turn.status === "streaming" ? { ...turn, status: "stopped" } : turn));
  } catch {
    return [];
  }
}

function save(project: string, turns: Turn[]) {
  try {
    sessionStorage.setItem(storageKey(project), JSON.stringify(turns.slice(-MAX_TURNS)));
  } catch {
    // The history then lasts until the page is left; nothing else depends on it.
  }
}

/**
 * Questions and answers for one project. Each question is answered on its
 * own (the API has no conversations yet); the list is kept for this browser
 * tab so it survives navigating between the project's sections.
 */
export function useAsk(project: Ref<string>, settings: Ref<AskSettings>) {
  const turns = ref<Turn[]>(restore(project.value));
  const busy = ref(false);
  let controller: AbortController | null = null;
  let nextId = Math.max(0, ...turns.value.map((turn) => turn.id)) + 1;

  watch(project, (name) => {
    stop();
    turns.value = restore(name);
  });

  function update(id: number, changes: Partial<Turn>) {
    turns.value = turns.value.map((turn) => (turn.id === id ? { ...turn, ...changes } : turn));
    if (changes.status && changes.status !== "streaming") save(project.value, turns.value);
  }

  async function ask(question: string) {
    if (busy.value || !question.trim()) return;
    const id = nextId++;
    const started = performance.now();
    const { stream, top_k, min_score } = settings.value;
    turns.value = [
      ...turns.value,
      { id, question: question.trim(), status: "streaming", text: "", answer: null, error: null, seconds: null },
    ];
    busy.value = true;
    controller = new AbortController();
    const options = { top_k, min_score };
    try {
      let text = "";
      const answer = stream
        ? await api.askStream(
            project.value,
            question,
            options,
            {
              onDelta: (piece) => {
                text += piece;
                update(id, { text });
              },
            },
            controller.signal,
          )
        : await api.ask(project.value, question, options, controller.signal);
      update(id, {
        status: "done",
        text: answer.answer ?? "",
        answer,
        seconds: (performance.now() - started) / 1000,
      });
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") {
        update(id, { status: "stopped" });
      } else {
        update(id, {
          status: "failed",
          error: caught instanceof ApiError ? caught.message : "Something went wrong.",
        });
      }
    } finally {
      busy.value = false;
      controller = null;
    }
  }

  function stop() {
    controller?.abort();
  }

  function retry(turn: Turn) {
    turns.value = turns.value.filter((candidate) => candidate.id !== turn.id);
    void ask(turn.question);
  }

  function clear() {
    stop();
    turns.value = [];
    save(project.value, []);
  }

  return { turns, busy, ask, stop, retry, clear };
}
