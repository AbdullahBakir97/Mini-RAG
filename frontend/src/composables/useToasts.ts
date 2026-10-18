import { ref } from "vue";

export interface Toast {
  id: number;
  kind: "success" | "error" | "info";
  title: string;
  message?: string;
}

const toasts = ref<Toast[]>([]);
let nextId = 1;

function dismiss(id: number) {
  toasts.value = toasts.value.filter((toast) => toast.id !== id);
}

function show(kind: Toast["kind"], title: string, message?: string) {
  const id = nextId++;
  toasts.value = [...toasts.value.slice(-3), { id, kind, title, message }];
  setTimeout(() => dismiss(id), kind === "error" ? 8000 : 4500);
}

/** Short notices in the corner of the screen. */
export function useToasts() {
  return {
    toasts,
    dismiss,
    success: (title: string, message?: string) => show("success", title, message),
    error: (title: string, message?: string) => show("error", title, message),
    info: (title: string, message?: string) => show("info", title, message),
  };
}
