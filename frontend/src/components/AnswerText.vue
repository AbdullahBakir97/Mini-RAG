<script setup lang="ts">
import { computed, h, type VNode } from "vue";

import { type Block, type Inline, parseMarkdown } from "@/lib/markdown";

const props = defineProps<{ text: string; streaming?: boolean; cited?: number[]; active?: number | null }>();
const emit = defineEmits<{ cite: [number]; hover: [number | null] }>();

const blocks = computed(() => parseMarkdown(props.text));
// While streaming, markers are shown but not linked: the sources come with the finished answer.
const linked = (number: number) => !props.streaming && (props.cited ?? []).includes(number);

// Everything is built from text nodes: the model's text never becomes HTML.
function inline(node: Inline): VNode | string {
  switch (node.kind) {
    case "text":
      return node.text;
    case "strong":
      return h("strong", node.children.map(inline));
    case "em":
      return h("em", node.children.map(inline));
    case "code":
      return h("code", node.text);
    case "cite":
      if (!linked(node.number)) return h("span", { class: "cite static" }, String(node.number));
      return h(
        "button",
        {
          class: ["cite", { active: props.active === node.number }],
          "aria-label": `Source ${node.number}`,
          onClick: () => emit("cite", node.number),
          onMouseenter: () => emit("hover", node.number),
          onMouseleave: () => emit("hover", null),
          onFocus: () => emit("hover", node.number),
          onBlur: () => emit("hover", null),
        },
        String(node.number),
      );
  }
}

// The caret follows the last text written, also inside a list.
function block(node: Block, last: boolean): VNode {
  if (node.kind === "list") {
    return h(
      node.ordered ? "ol" : "ul",
      node.ordered && node.start !== 1 ? { start: node.start } : {},
      node.items.map((item, i) =>
        h("li", item.map((child, j) => block(child, last && i === node.items.length - 1 && j === item.length - 1))),
      ),
    );
  }
  const children: (VNode | string)[] = node.inlines.map(inline);
  if (last && props.streaming) children.push(h("span", { class: "caret", "aria-hidden": "true" }));
  return h(node.kind === "heading" ? "h4" : "p", children);
}

const Content = () =>
  blocks.value.length
    ? blocks.value.map((node, i) => block(node, i === blocks.value.length - 1))
    : props.streaming
      ? [h("p", [h("span", { class: "caret", "aria-hidden": "true" })])]
      : [];
</script>

<template>
  <div class="answer-text"><Content /></div>
</template>

<style scoped>
.answer-text {
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 15px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.answer-text :deep(p),
.answer-text :deep(h4) {
  margin: 0;
  white-space: pre-line;
}

.answer-text :deep(h4) {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 650;
}

.answer-text :deep(ul),
.answer-text :deep(ol) {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding-left: 1.5em;
}

.answer-text :deep(ul) {
  list-style: disc;
}

.answer-text :deep(li ul) {
  list-style: circle;
}

.answer-text :deep(li > ul),
.answer-text :deep(li > ol) {
  margin-top: 6px;
}

.answer-text :deep(li::marker) {
  color: var(--text-3);
}

.answer-text :deep(li > p + p) {
  margin-top: 6px;
}

.answer-text :deep(strong) {
  font-weight: 650;
}

.answer-text :deep(code) {
  padding: 1px 5px;
  border-radius: 5px;
  background: var(--surface-3);
  font-size: 0.88em;
}

.answer-text :deep(.cite) {
  display: inline-grid;
  place-items: center;
  min-width: 20px;
  height: 18px;
  margin: 0 2px;
  padding: 0 5px;
  border: 0;
  border-radius: 5px;
  background: var(--accent-soft);
  color: var(--accent-text);
  font: 600 11.5px/1 var(--font);
  vertical-align: 2px;
  cursor: pointer;
  transition:
    background 0.15s,
    color 0.15s;
}

.answer-text :deep(.cite:hover),
.answer-text :deep(.cite.active) {
  background: var(--accent);
  color: var(--on-accent);
}

.answer-text :deep(.cite.static) {
  background: var(--surface-3);
  color: var(--text-2);
  cursor: default;
}

.answer-text :deep(.caret) {
  display: inline-block;
  width: 7px;
  height: 1.05em;
  margin-left: 2px;
  border-radius: 1px;
  background: var(--accent);
  vertical-align: -0.15em;
  animation: blink 1s steps(2, start) infinite;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}
</style>
