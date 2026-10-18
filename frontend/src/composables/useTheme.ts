import { ref, watch } from "vue";

export type Theme = "system" | "light" | "dark";

function load(): Theme {
  try {
    const saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // Storage can be unavailable (private windows, blocked site data).
  }
  return "system";
}

const theme = ref<Theme>(load());

watch(theme, (value) => {
  const root = document.documentElement;
  if (value === "system") delete root.dataset.theme;
  else root.dataset.theme = value;
  try {
    if (value === "system") localStorage.removeItem("theme");
    else localStorage.setItem("theme", value);
  } catch {
    // The choice still applies for this visit.
  }
});

/** The color theme: the system's, or one chosen in the app and remembered. */
export function useTheme() {
  const order: Theme[] = ["system", "light", "dark"];
  function cycle() {
    theme.value = order[(order.indexOf(theme.value) + 1) % order.length]!;
  }
  return { theme, cycle };
}
