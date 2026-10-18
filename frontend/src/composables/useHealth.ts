import { onScopeDispose, ref } from "vue";

import { api } from "@/api/client";
import type { Health, Welcome } from "@/api/types";

/** The API's health, checked now and every 30 seconds while in use. */
export function useHealth() {
  const health = ref<Health | null>(null);
  const info = ref<Welcome | null>(null);
  const reachable = ref(true);

  async function check() {
    try {
      health.value = await api.health();
      reachable.value = true;
      if (!info.value) info.value = await api.welcome();
    } catch {
      reachable.value = false;
      health.value = null;
    }
  }

  void check();
  const timer = setInterval(check, 30_000);
  onScopeDispose(() => clearInterval(timer));
  return { health, info, reachable, check };
}
