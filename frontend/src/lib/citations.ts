// Splits an answer into text and the [n] markers that cite its sources.

export type AnswerPart = { kind: "text"; text: string } | { kind: "cite"; number: number };

/** Paragraphs of parts. "[1, 2]" and "[1][2]" both become separate markers. */
export function parseAnswer(answer: string): AnswerPart[][] {
  return answer
    .trim()
    .split(/\n\s*\n/)
    .map((paragraph) => parseParagraph(paragraph.trim()));
}

function parseParagraph(paragraph: string): AnswerPart[] {
  const parts: AnswerPart[] = [];
  const marker = /\[(\d+(?:\s*,\s*\d+)*)\]/g;
  let last = 0;
  for (const match of paragraph.matchAll(marker)) {
    if (match.index > last) parts.push({ kind: "text", text: paragraph.slice(last, match.index) });
    for (const number of match[1]!.split(",")) parts.push({ kind: "cite", number: Number(number.trim()) });
    last = match.index + match[0].length;
  }
  if (last < paragraph.length) parts.push({ kind: "text", text: paragraph.slice(last) });
  return parts;
}

/** Splits text around the words of a query, for highlighting search matches. */
export function highlight(text: string, query: string): { text: string; match: boolean }[] {
  const words = [...new Set(query.toLowerCase().match(/[\p{L}\p{N}]{3,}/gu) ?? [])];
  if (!words.length) return [{ text, match: false }];
  const escaped = words.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(${escaped.join("|")})`, "giu");
  return text
    .split(pattern)
    .filter(Boolean)
    .map((piece) => ({ text: piece, match: words.includes(piece.toLowerCase()) }));
}
