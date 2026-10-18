<script setup lang="ts">
import { Monitor, Moon, Sun } from "@lucide/vue";
import { computed } from "vue";

import { useTheme } from "@/composables/useTheme";

const { theme, cycle } = useTheme();
const label = computed(() => `Theme: ${theme.value} (click to change)`);
</script>

<template>
  <button class="btn btn-ghost btn-icon btn-sm" :aria-label="label" :title="label" @click="cycle">
    <Monitor v-if="theme === 'system'" :size="16" />
    <Sun v-else-if="theme === 'light'" :size="16" />
    <Moon v-else :size="16" />
  </button>
</template>
