<script setup lang="ts">
import { Tag, X } from "@lucide/vue";
import { computed, ref, useId } from "vue";

import { MAX_TAGS, normalizeTag } from "@/lib/tags";

const props = withDefaults(
  defineProps<{
    modelValue: string[];
    /** Tags the project has, offered while typing. */
    suggestions?: string[];
    placeholder?: string;
    label?: string;
  }>(),
  { suggestions: () => [], placeholder: "Add a tag…", label: "Tags" },
);
const emit = defineEmits<{ "update:modelValue": [string[]] }>();

const text = ref("");
const problem = ref<string | null>(null);
const listId = useId();
const offered = computed(() => props.suggestions.filter((tag) => !props.modelValue.includes(tag)));

/** Adds what was typed; commas separate several tags. Returns whether all of it was valid. */
function commit(): boolean {
  const parts = text.value.split(",").filter((part) => part.trim());
  if (!parts.length) return true;
  const tags = [...props.modelValue];
  for (const part of parts) {
    const tag = normalizeTag(part);
    if (tag === null) {
      problem.value = `"${part.trim()}" is not a tag: use letters, digits and hyphens, up to 32.`;
      return false;
    }
    if (!tags.includes(tag)) tags.push(tag);
  }
  if (tags.length > MAX_TAGS) {
    problem.value = `At most ${MAX_TAGS} tags.`;
    return false;
  }
  problem.value = null;
  text.value = "";
  emit("update:modelValue", tags);
  return true;
}

function onKey(event: KeyboardEvent) {
  if (event.key === "Enter" || event.key === ",") {
    if (text.value.trim()) event.preventDefault();
    commit();
  } else if (event.key === "Backspace" && !text.value && props.modelValue.length) {
    emit("update:modelValue", props.modelValue.slice(0, -1));
  }
}

// Picking a suggestion from the list fills the input in one go.
function onInput() {
  problem.value = null;
  if (offered.value.includes(text.value)) commit();
}

function remove(tag: string) {
  emit(
    "update:modelValue",
    props.modelValue.filter((t) => t !== tag),
  );
}

defineExpose({ commit });
</script>

<template>
  <div class="tag-input">
    <div class="box input" :class="{ invalid: problem }">
      <Tag :size="14" class="subtle" aria-hidden="true" />
      <span v-for="tag in modelValue" :key="tag" class="chip">
        {{ tag }}
        <button type="button" class="remove" :aria-label="`Remove tag ${tag}`" @click="remove(tag)">
          <X :size="12" />
        </button>
      </span>
      <input
        v-model="text"
        :list="listId"
        :placeholder="modelValue.length ? '' : placeholder"
        :aria-label="label"
        :aria-invalid="problem !== null"
        maxlength="200"
        @keydown="onKey"
        @input="onInput"
        @blur="commit"
      />
      <datalist :id="listId">
        <option v-for="tag in offered" :key="tag" :value="tag" />
      </datalist>
    </div>
    <p v-if="problem" class="small problem" role="alert">{{ problem }}</p>
  </div>
</template>

<style scoped>
.tag-input {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.box {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  height: auto;
  min-height: 36px;
  padding: 4px 8px;
  cursor: text;
}

.box.invalid {
  border-color: var(--danger);
}

.box input {
  flex: 1 1 90px;
  min-width: 90px;
  padding: 3px 0;
  border: 0;
  outline: none;
  background: none;
  color: var(--text);
  font: inherit;
  font-size: 13.5px;
}

.problem {
  margin: 0;
  color: var(--danger);
}
</style>
