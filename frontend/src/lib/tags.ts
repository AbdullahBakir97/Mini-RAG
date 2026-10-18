/** Tags as the server stores them (see the API's tag rules). */
export const MAX_TAG_LENGTH = 32;
export const MAX_TAGS = 20;

/** Lowercase, with spaces and underscores as hyphens; null when it cannot be a tag. */
export function normalizeTag(text: string): string | null {
  const tag = text
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (!tag || tag.length > MAX_TAG_LENGTH || !/^[\p{L}\p{N}][\p{L}\p{N}-]*$/u.test(tag)) return null;
  return tag;
}
