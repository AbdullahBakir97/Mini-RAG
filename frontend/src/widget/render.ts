// Builds an answer's DOM from the safe Markdown tree: text only, never HTML.

import { parseMarkdown, type Block, type Inline } from "../lib/markdown";

/** Makes the element for an [n] marker; null keeps it as plain text. */
export type CiteFactory = (number: number) => HTMLElement | null;

export function renderAnswer(text: string, cite: CiteFactory): DocumentFragment {
  const fragment = document.createDocumentFragment();
  for (const block of parseMarkdown(text)) fragment.append(renderBlock(block, cite));
  return fragment;
}

function renderBlock(block: Block, cite: CiteFactory): HTMLElement {
  if (block.kind === "list") {
    const list = document.createElement(block.ordered ? "ol" : "ul");
    if (block.ordered && block.start !== 1) list.setAttribute("start", String(block.start));
    for (const item of block.items) {
      const li = document.createElement("li");
      for (const child of item) li.append(renderBlock(child, cite));
      list.append(li);
    }
    return list;
  }
  const element = document.createElement(block.kind === "heading" ? "strong" : "p");
  if (block.kind === "heading") element.className = "heading";
  appendInlines(element, block.inlines, cite);
  return element;
}

function appendInlines(parent: HTMLElement, inlines: Inline[], cite: CiteFactory): void {
  for (const inline of inlines) {
    if (inline.kind === "text") {
      parent.append(inline.text);
    } else if (inline.kind === "code") {
      const code = document.createElement("code");
      code.textContent = inline.text;
      parent.append(code);
    } else if (inline.kind === "cite") {
      parent.append(cite(inline.number) ?? `[${inline.number}]`);
    } else {
      const element = document.createElement(inline.kind);
      appendInlines(element, inline.children, cite);
      parent.append(element);
    }
  }
}

/** "guide.pdf · p. 3 · Setup": where a source is. */
export function sourceLabel(citation: { file_name: string | null; page: number | null; section: string | null }): string {
  return [citation.file_name ?? "Document", citation.page ? `p. ${citation.page}` : null, citation.section]
    .filter(Boolean)
    .join(" · ");
}

/** Black or white, whichever reads better on ``hex`` (#rrggbb). */
export function textOn(hex: string): string {
  const channels = [1, 3, 5].map((start) => {
    const value = parseInt(hex.slice(start, start + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  const luminance = 0.2126 * channels[0]! + 0.7152 * channels[1]! + 0.0722 * channels[2]!;
  return luminance > 0.179 ? "#111827" : "#ffffff";
}
