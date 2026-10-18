// A small Markdown reader for answers: paragraphs, headings, nested lists,
// bold, italics, inline code and [n] citation markers. It returns a tree of
// plain strings that the page renders as text, so nothing the model writes
// ever becomes HTML.

export type Inline =
  | { kind: "text"; text: string }
  | { kind: "strong"; children: Inline[] }
  | { kind: "em"; children: Inline[] }
  | { kind: "code"; text: string }
  | { kind: "cite"; number: number };

export type Block =
  | { kind: "paragraph"; inlines: Inline[] }
  | { kind: "heading"; inlines: Inline[] }
  | { kind: "list"; ordered: boolean; start: number; items: Block[][] };

const LIST_ITEM = /^(\s*)([*+-]|\d{1,3}[.)])\s+(.*)$/;
const HEADING = /^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/;
const CITATION = /^\[(\d+(?:\s*,\s*\d+)*)\]/;

interface OpenList {
  indent: number;
  list: Extract<Block, { kind: "list" }>;
}

/** Splits an answer into blocks. Unfinished syntax (while streaming) stays plain text. */
export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  let lists: OpenList[] = [];
  let paragraph: string[] | null = null;
  let blank = false;

  const closeParagraph = () => {
    if (paragraph) blocks.push({ kind: "paragraph", inlines: parseInline(paragraph.join("\n")) });
    paragraph = null;
  };
  const lastItem = () => {
    const open = lists.at(-1)!;
    return open.list.items.at(-1)!;
  };

  for (const line of source.replace(/\r\n?/g, "\n").trim().split("\n")) {
    if (!line.trim()) {
      closeParagraph();
      blank = true;
      continue;
    }

    const item = LIST_ITEM.exec(line);
    if (item) {
      closeParagraph();
      const indent = item[1]!.replace(/\t/g, "    ").length;
      const marker = item[2]!;
      const ordered = /\d/.test(marker);
      while (lists.length && lists.at(-1)!.indent > indent) lists.pop();
      const top = lists.at(-1);
      if (top && top.indent === indent && top.list.ordered !== ordered) lists.pop();
      const current = lists.at(-1);
      const content: Block = { kind: "paragraph", inlines: parseInline(item[3]!) };
      if (current && current.indent === indent) {
        current.list.items.push([content]);
      } else {
        const list: OpenList["list"] = {
          kind: "list",
          ordered,
          start: ordered ? parseInt(marker, 10) : 1,
          items: [[content]],
        };
        if (current) current.list.items.at(-1)!.push(list);
        else blocks.push(list);
        lists.push({ indent, list });
      }
      blank = false;
      continue;
    }

    // A line under a list item continues it when it is indented, or directly follows it.
    if (lists.length && (!blank || /^\s+/.test(line))) {
      const blocksOfItem = lastItem();
      const last = blocksOfItem.at(-1)!;
      if (last.kind === "paragraph" && !blank) {
        last.inlines.push({ kind: "text", text: "\n" }, ...parseInline(line.trim()));
      } else {
        blocksOfItem.push({ kind: "paragraph", inlines: parseInline(line.trim()) });
      }
      blank = false;
      continue;
    }

    lists = [];
    const heading = HEADING.exec(line);
    if (heading) {
      closeParagraph();
      blocks.push({ kind: "heading", inlines: parseInline(heading[1]!) });
    } else {
      paragraph = [...(paragraph ?? []), line.trim()];
    }
    blank = false;
  }
  closeParagraph();
  return blocks;
}

function isWordChar(char: string | undefined): boolean {
  return !!char && /[\p{L}\p{N}]/u.test(char);
}

/** Emphasis with `delimiter`, starting at `start`; null when it is not closed. */
function delimited(text: string, start: number, delimiter: string): { inner: string; end: number } | null {
  const open = start + delimiter.length;
  if (open >= text.length || /\s/.test(text[open]!)) return null;
  // Underscores inside words (snake_case) are not emphasis.
  if (delimiter[0] === "_" && isWordChar(text[start - 1])) return null;
  let close = text.indexOf(delimiter, open + 1);
  while (close !== -1) {
    const valid =
      !/\s/.test(text[close - 1]!) &&
      // "**" must not be read as two single "*".
      (delimiter.length === 2 || text[close + 1] !== delimiter) &&
      !(delimiter[0] === "_" && isWordChar(text[close + delimiter.length]));
    if (valid) return { inner: text.slice(open, close), end: close + delimiter.length };
    close = text.indexOf(delimiter, close + 1);
  }
  return null;
}

/** Bold, italics, inline code and [n] markers within one block. */
export function parseInline(text: string): Inline[] {
  const result: Inline[] = [];
  let plain = "";
  const flush = () => {
    if (plain) result.push({ kind: "text", text: plain });
    plain = "";
  };

  let i = 0;
  while (i < text.length) {
    const char = text[i]!;
    if (char === "`") {
      const close = text.indexOf("`", i + 1);
      if (close > i + 1) {
        flush();
        result.push({ kind: "code", text: text.slice(i + 1, close) });
        i = close + 1;
        continue;
      }
    }
    if (char === "[") {
      const marker = CITATION.exec(text.slice(i));
      if (marker) {
        flush();
        for (const number of marker[1]!.split(",")) result.push({ kind: "cite", number: Number(number.trim()) });
        i += marker[0].length;
        continue;
      }
    }
    if (char === "*" || char === "_") {
      const double = text[i + 1] === char;
      const found = (double && delimited(text, i, char + char)) || delimited(text, i, char);
      if (found) {
        flush();
        const strong = double && found.end - i - found.inner.length === 4;
        result.push({ kind: strong ? "strong" : "em", children: parseInline(found.inner) });
        i = found.end;
        continue;
      }
    }
    plain += char;
    i += 1;
  }
  flush();
  return result;
}
