<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { useRouter } from "vue-router";

import { PROJECT_NAME, useProjects } from "@/composables/useProjects";

const router = useRouter();
const { names, addDraft } = useProjects();
const dialog = ref<HTMLDialogElement | null>(null);
const input = ref<HTMLInputElement | null>(null);
const name = ref("");
const touched = ref(false);

const problem = computed(() => {
  const value = name.value.trim();
  if (!value) return "Enter a name.";
  if (!PROJECT_NAME.test(value)) return "Use letters, digits, '-' and '_' only (up to 64).";
  if (names.value.includes(value)) return "A project with this name exists.";
  return null;
});

async function open() {
  name.value = "";
  touched.value = false;
  dialog.value?.showModal();
  await nextTick();
  input.value?.focus();
}

function close() {
  dialog.value?.close();
}

async function create() {
  touched.value = true;
  if (problem.value) return;
  const value = name.value.trim();
  addDraft(value);
  close();
  await router.push({ name: "documents", params: { project: value } });
}

defineExpose({ open });
</script>

<template>
  <dialog ref="dialog" class="dialog" aria-labelledby="new-project-title" @click.self="close">
    <form class="content" @submit.prevent="create">
      <h2 id="new-project-title">New project</h2>
      <p class="muted">A project holds the documents that answer its questions.</p>
      <label class="field">
        <span>Name</span>
        <input
          ref="input"
          v-model="name"
          class="input"
          placeholder="e.g. research-papers"
          maxlength="64"
          autocomplete="off"
          spellcheck="false"
          :aria-invalid="touched && !!problem"
          @blur="touched = true"
        />
      </label>
      <p v-if="touched && problem" class="error small">{{ problem }}</p>
      <div class="actions">
        <button type="button" class="btn" @click="close">Cancel</button>
        <button type="submit" class="btn btn-primary">Create project</button>
      </div>
    </form>
  </dialog>
</template>

<style scoped>
.dialog {
  width: min(420px, calc(100vw - 32px));
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-lg);
}

.dialog::backdrop {
  background: rgb(0 0 0 / 40%);
}

.content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 22px;
}

.error {
  margin-top: -4px;
  color: var(--danger);
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 6px;
}
</style>
