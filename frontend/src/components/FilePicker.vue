<script setup lang="ts">
import { Check, ChevronDown, Files, Tags } from "@lucide/vue";
import { computed, onBeforeUnmount, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    files: { file_id: string; original_name: string }[];
    /** The chosen files; none means all of them. */
    modelValue: string[];
    /** Picks tags instead: `files` are then the tags, by name. */
    tags?: boolean;
  }>(),
  { tags: false },
);
const emit = defineEmits<{ "update:modelValue": [string[]] }>();

const open = ref(false);
const root = ref<HTMLElement | null>(null);

const label = computed(() => {
  const chosen = props.files.filter((file) => props.modelValue.includes(file.file_id));
  if (!chosen.length) return props.tags ? "Any tag" : "All documents";
  if (chosen.length === 1) return chosen[0]!.original_name;
  return `${chosen.length} ${props.tags ? "tags" : "documents"}`;
});

function toggle(fileId: string) {
  const chosen = props.modelValue.includes(fileId)
    ? props.modelValue.filter((id) => id !== fileId)
    : [...props.modelValue, fileId];
  emit("update:modelValue", chosen);
}

function onPointer(event: PointerEvent) {
  if (root.value && !root.value.contains(event.target as Node)) open.value = false;
}

function onKey(event: KeyboardEvent) {
  if (event.key === "Escape") open.value = false;
}

// Clicking elsewhere or pressing Escape closes the list.
watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
  } else {
    document.removeEventListener("pointerdown", onPointer);
    document.removeEventListener("keydown", onKey);
  }
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onPointer);
  document.removeEventListener("keydown", onKey);
});
</script>

<template>
  <div ref="root" class="picker">
    <button
      type="button"
      class="btn btn-sm trigger"
      :class="{ chosen: modelValue.length }"
      :aria-expanded="open"
      aria-haspopup="true"
      :disabled="!files.length"
      @click="open = !open"
    >
      <Tags v-if="tags" :size="14" />
      <Files v-else :size="14" />
      <span class="label">{{ label }}</span>
      <ChevronDown :size="14" />
    </button>
    <div v-if="open" class="menu card" role="group" :aria-label="tags ? 'Tags of the documents to use' : 'Documents to use'">
      <button type="button" class="option" :aria-pressed="!modelValue.length" @click="emit('update:modelValue', [])">
        <span class="box"><Check v-if="!modelValue.length" :size="12" /></span>
        {{ tags ? "Any tag" : "All documents" }}
      </button>
      <hr />
      <button
        v-for="file in files"
        :key="file.file_id"
        type="button"
        class="option"
        :aria-pressed="modelValue.includes(file.file_id)"
        @click="toggle(file.file_id)"
      >
        <span class="box"><Check v-if="modelValue.includes(file.file_id)" :size="12" /></span>
        <span class="name">{{ file.original_name }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.picker {
  position: relative;
}

.trigger {
  max-width: 260px;
}

.trigger.chosen {
  border-color: var(--accent);
  color: var(--accent-text);
}

.label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.menu {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  width: max-content;
  min-width: 220px;
  max-width: min(360px, 80vw);
  max-height: 320px;
  padding: 6px;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.picker.below .menu {
  top: calc(100% + 6px);
  bottom: auto;
}

.option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border: 0;
  border-radius: var(--radius-sm);
  background: none;
  color: var(--text);
  font: inherit;
  font-size: 13.5px;
  text-align: left;
  cursor: pointer;
}

.option:hover {
  background: var(--surface-2);
}

.box {
  display: grid;
  flex: none;
  place-items: center;
  width: 16px;
  height: 16px;
  border: 1px solid var(--border-strong);
  border-radius: 4px;
  color: var(--accent);
}

.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

hr {
  width: 100%;
  margin: 4px 0;
  border: 0;
  border-top: 1px solid var(--border);
}
</style>
