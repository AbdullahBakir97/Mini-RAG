<script setup lang="ts">
import { ChevronLeft, ChevronRight } from "@lucide/vue";
import { computed } from "vue";

import { formatNumber } from "@/lib/format";

const props = defineProps<{ total: number; offset: number; limit: number; noun?: string }>();
const emit = defineEmits<{ change: [offset: number] }>();

const first = computed(() => (props.total ? props.offset + 1 : 0));
const last = computed(() => Math.min(props.offset + props.limit, props.total));
</script>

<template>
  <div v-if="total > limit" class="pager">
    <span class="subtle small">
      {{ formatNumber(first) }}–{{ formatNumber(last) }} of {{ formatNumber(total) }} {{ noun }}
    </span>
    <div class="buttons">
      <button
        class="btn btn-sm btn-icon"
        :disabled="offset === 0"
        aria-label="Previous page"
        @click="emit('change', Math.max(0, offset - limit))"
      >
        <ChevronLeft :size="16" />
      </button>
      <button
        class="btn btn-sm btn-icon"
        :disabled="last >= total"
        aria-label="Next page"
        @click="emit('change', offset + limit)"
      >
        <ChevronRight :size="16" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.buttons {
  display: flex;
  gap: 6px;
}
</style>
