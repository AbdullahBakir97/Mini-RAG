import { describe, expect, it } from "vitest";

import { type Block, parseInline, parseMarkdown } from "@/lib/markdown";

const text = (value: string) => ({ kind: "text", text: value });
const paragraph = (value: string) => ({ kind: "paragraph", inlines: [text(value)] });

describe("parseInline", () => {
  it("reads bold, italics, code and citation markers", () => {
    expect(parseInline("A **bold** and *em* `x` [1, 2].")).toEqual([
      text("A "),
      { kind: "strong", children: [text("bold")] },
      text(" and "),
      { kind: "em", children: [text("em")] },
      text(" "),
      { kind: "code", text: "x" },
      text(" "),
      { kind: "cite", number: 1 },
      { kind: "cite", number: 2 },
      text("."),
    ]);
  });

  it("nests emphasis and citations", () => {
    expect(parseInline("**Use of Proceeds [3]**")).toEqual([
      { kind: "strong", children: [text("Use of Proceeds "), { kind: "cite", number: 3 }] },
    ]);
  });

  it("leaves unfinished or ordinary symbols alone", () => {
    expect(parseInline("2 * 3 = 6, snake_case_name, **unfinished, [note]")).toEqual([
      text("2 * 3 = 6, snake_case_name, **unfinished, [note]"),
    ]);
  });
});

describe("parseMarkdown", () => {
  it("splits paragraphs and keeps line breaks inside them", () => {
    expect(parseMarkdown("One\nline two\n\nTwo")).toEqual([paragraph("One\nline two"), paragraph("Two")]);
  });

  it("reads headings", () => {
    expect(parseMarkdown("## Summary\nText")).toEqual([
      { kind: "heading", inlines: [text("Summary")] },
      paragraph("Text"),
    ]);
  });

  it("reads the nested lists models write", () => {
    const answer = [
      "The main points are:",
      "",
      "* Issuers should disclose allocations [1].",
      "* The four core components are:",
      "    1. Use of Proceeds",
      "    2. Reporting [5].",
      "* External reviews should be public [2].",
    ].join("\n");

    const [intro, list] = parseMarkdown(answer) as [Block, Extract<Block, { kind: "list" }>];

    expect(intro).toEqual(paragraph("The main points are:"));
    expect(list.ordered).toBe(false);
    expect(list.items).toHaveLength(3);
    const [, nested] = list.items[1]!;
    expect(nested).toEqual({
      kind: "list",
      ordered: true,
      start: 1,
      items: [[paragraph("Use of Proceeds")], [{ kind: "paragraph", inlines: [text("Reporting "), { kind: "cite", number: 5 }, text(".")] }]],
    });
  });

  it("keeps the numbering an ordered list starts at", () => {
    const [list] = parseMarkdown("3. Third\n4. Fourth");
    expect(list).toMatchObject({ kind: "list", ordered: true, start: 3 });
  });

  it("continues an item on the next line, and ends the list at a plain paragraph", () => {
    expect(parseMarkdown("- First\n  continued\n\nAfter")).toEqual([
      {
        kind: "list",
        ordered: false,
        start: 1,
        items: [[{ kind: "paragraph", inlines: [text("First"), text("\n"), text("continued")] }]],
      },
      paragraph("After"),
    ]);
  });
});
