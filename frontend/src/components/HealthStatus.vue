<script setup lang="ts">
import { computed } from "vue";

import { useHealth } from "@/composables/useHealth";

const { health, info, reachable } = useHealth();

const state = computed(() => {
  if (!reachable.value) return { tone: "down", label: "API unreachable" };
  if (!health.value) return { tone: "pending", label: "Checking…" };
  if (health.value.database !== "ok") return { tone: "down", label: "Database unavailable" };
  return { tone: "up", label: "All systems normal" };
});
</script>

<template>
  <div class="health" :title="info ? `${info.app_name} ${info.app_version}` : undefined" role="status">
    <span class="dot" :class="state.tone" aria-hidden="true" />
    <span class="label">{{ state.label }}</span>
    <span v-if="info" class="version subtle mono">v{{ info.app_version }}</span>
  </div>
</template>

<style scoped>
.health {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  color: var(--text-2);
  font-size: 12.5px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-3);
}

.dot.up {
  background: var(--success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--success) 20%, transparent);
}

.dot.down {
  background: var(--danger);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--danger) 20%, transparent);
}

.label {
  flex: 1;
}

.version {
  font-size: 11.5px;
}
</style>
