<script setup lang="ts">
import { CircleAlert, CircleCheck, Info, X } from "@lucide/vue";

import { useToasts } from "@/composables/useToasts";

const { toasts, dismiss } = useToasts();
</script>

<template>
  <div class="toasts" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="toast in toasts" :key="toast.id" class="toast" :class="toast.kind" role="status">
        <CircleCheck v-if="toast.kind === 'success'" :size="18" class="icon" />
        <CircleAlert v-else-if="toast.kind === 'error'" :size="18" class="icon" />
        <Info v-else :size="18" class="icon" />
        <div class="body">
          <strong>{{ toast.title }}</strong>
          <p v-if="toast.message" class="muted">{{ toast.message }}</p>
        </div>
        <button class="btn btn-ghost btn-icon btn-sm" aria-label="Dismiss" @click="dismiss(toast.id)">
          <X :size="14" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toasts {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(380px, calc(100vw - 32px));
}

.toast {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 12px 10px 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: var(--shadow-lg);
}

.icon {
  flex: none;
  margin-top: 1px;
}

.success .icon {
  color: var(--success);
}

.error .icon {
  color: var(--danger);
}

.info .icon {
  color: var(--accent);
}

.body {
  flex: 1;
  min-width: 0;
}

.body p {
  margin-top: 2px;
  font-size: 13px;
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 0.2s,
    transform 0.2s;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
