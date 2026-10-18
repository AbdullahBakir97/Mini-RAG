// Highlighting of search matches, and plain previews of answers.

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

/** An answer as plain prose, for previews: without [n] markers, emphasis or line breaks. */
export function strip(answer: string): string {
  return answer
    .replace(/\s?\[\d+(?:\s*,\s*\d+)*\]/g, "")
    .replace(/(\*\*|__|`)/g, "")
    .replace(/^\s*(?:[*+-]|\d{1,3}[.)])\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}
