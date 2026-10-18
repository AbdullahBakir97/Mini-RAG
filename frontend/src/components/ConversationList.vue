<script setup lang="ts">
import { LoaderCircle, MessageSquare, SquarePen, Trash2, X } from "@lucide/vue";
import { ref } from "vue";

import type { Conversation } from "@/api/types";
import { formatRelative } from "@/lib/format";

defineProps<{
  items: Conversation[];
  total: number;
  loading: boolean;
  error: string | null;
  active: string | null;
}>();
const emit = defineEmits<{
  select: [string];
  create: [];
  remove: [string];
  more: [];
  retry: [];
  close: [];
}>();

// The conversation asking to be confirmed before it is deleted.
const confirming = ref<string | null>(null);

function confirmRemove(id: string) {
  confirming.value = null;
  emit("remove", id);
}
</script>

<template>
  <nav class="conversations" aria-label="Conversations">
    <header class="head">
      <h2 class="title">Conversations</h2>
      <button class="btn btn-sm" title="Start a new conversation" @click="emit('create')">
        <SquarePen :size="14" /> New
      </button>
      <button class="btn btn-ghost btn-icon btn-sm close" aria-label="Close conversations" @click="emit('close')">
        <X :size="16" />
      </button>
    </header>

    <p v-if="error" class="alert alert-danger small">
      <span class="grow">{{ error }}</span>
      <button class="btn btn-sm" @click="emit('retry')">Retry</button>
    </p>
    <template v-else-if="loading && !items.length">
      <div v-for="i in 3" :key="i" class="skeleton item-skeleton" />
    </template>
    <p v-else-if="!items.length" class="subtle small empty">
      Your questions and their answers are kept here as conversations.
    </p>

    <ul class="list">
      <li v-for="conversation in items" :key="conversation.id">
        <div v-if="confirming === conversation.id" class="item confirm" role="group" aria-label="Confirm deletion">
          <span class="small">Delete this conversation?</span>
          <div class="confirm-actions">
            <button class="btn btn-sm btn-danger" @click="confirmRemove(conversation.id)">Delete</button>
            <button class="btn btn-ghost btn-sm" @click="confirming = null">Cancel</button>
          </div>
        </div>
        <div v-else class="item" :class="{ active: conversation.id === active }">
          <button
            class="open"
            :aria-current="conversation.id === active ? 'page' : undefined"
            @click="emit('select', conversation.id)"
          >
            <MessageSquare :size="14" class="icon" />
            <span class="text">
              <span class="name">{{ conversation.title ?? "New conversation" }}</span>
              <span class="when subtle">{{ formatRelative(conversation.updated_at) }}</span>
            </span>
          </button>
          <button
            class="btn btn-ghost btn-icon btn-sm delete"
            :aria-label="`Delete ${conversation.title ?? 'this conversation'}`"
            title="Delete"
            @click="confirming = conversation.id"
          >
            <Trash2 :size="14" />
          </button>
        </div>
      </li>
    </ul>

    <button v-if="items.length < total" class="btn btn-ghost btn-sm more" :disabled="loading" @click="emit('more')">
      <LoaderCircle v-if="loading" :size="14" class="spin" />
      Show more
    </button>
  </nav>
</template>

<style scoped>
.conversations {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 4px;
}

.title {
  flex: 1;
  color: var(--text-3);
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.close {
  display: none;
}

.empty {
  padding: 4px 2px;
}

.item-skeleton {
  height: 46px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.item {
  position: relative;
  display: flex;
  align-items: center;
  border-radius: var(--radius);
  transition: background 0.15s;
}

.item:hover,
.item:focus-within {
  background: var(--surface-2);
}

.item.active {
  background: var(--accent-soft);
}

.open {
  display: flex;
  flex: 1;
  align-items: flex-start;
  gap: 9px;
  min-width: 0;
  padding: 8px 4px 8px 10px;
  border: 0;
  background: none;
  color: var(--text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.icon {
  flex: none;
  margin-top: 3px;
  color: var(--text-3);
}

.active .icon {
  color: var(--accent-text);
}

.text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.name {
  overflow: hidden;
  font-size: 13.5px;
  font-weight: 550;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.when {
  font-size: 12px;
}

.delete {
  flex: none;
  margin-right: 4px;
  opacity: 0;
}

.item:hover .delete,
.item:focus-within .delete {
  opacity: 1;
}

@media (hover: none) {
  .delete {
    opacity: 1;
  }
}

.confirm {
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--border);
  background: var(--surface-2);
}

.confirm-actions {
  display: flex;
  gap: 6px;
}

.more {
  align-self: flex-start;
}

.grow {
  flex: 1;
}

@media (max-width: 1179px) {
  .close {
    display: inline-flex;
  }
}
</style>
