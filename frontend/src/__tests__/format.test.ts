import { describe, expect, it } from "vitest";

import { displayName, formatBytes, formatCost, formatPercent, formatRelative, reflow } from "@/lib/format";

describe("format", () => {
  it("formats sizes", () => {
    expect(formatBytes(835)).toBe("835 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(25 * 1024 * 1024)).toBe("25 MB");
  });

  it("formats costs down to fractions of a cent", () => {
    expect(formatCost(null)).toBe("—");
    expect(formatCost(0)).toBe("$0.00");
    expect(formatCost(0.00041)).toBe("$0.00041");
    expect(formatCost(0.5)).toBe("$0.5000");
    expect(formatCost(12.345)).toBe("$12.35");
  });

  it("formats percentages of nothing as 0%", () => {
    expect(formatPercent(0, 0)).toBe("0%");
    expect(formatPercent(1, 3)).toBe("33%");
  });

  it("formats recent times relatively", () => {
    const now = Date.parse("2026-01-10T12:00:00Z");
    expect(formatRelative("2026-01-10T11:59:50Z", now)).toBe("just now");
    expect(formatRelative("2026-01-10T11:55:00Z", now)).toBe("5 minutes ago");
    expect(formatRelative("2026-01-09T12:00:00Z", now)).toBe("yesterday");
  });

  it("takes the name out of a file id", () => {
    expect(displayName("a16q20nzrtvj_notes.txt")).toBe("notes.txt");
    expect(displayName("plain")).toBe("plain");
  });

  it("joins the lines a PDF breaks inside paragraphs", () => {
    expect(reflow("The annual report should\ninclude a list of the\nprojects.\n\nNext paragraph.")).toBe(
      "The annual report should include a list of the projects.\n\nNext paragraph.",
    );
  });

  it("keeps list lines and hyphenated words", () => {
    expect(reflow("Steps:\n• Use of Proceeds\n• Reporting\n1. One\nwell-\nknown")).toBe(
      "Steps:\n• Use of Proceeds\n• Reporting\n1. One well-known",
    );
  });
});
