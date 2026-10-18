import { describe, expect, it } from "vitest";

import { highlight, parseAnswer } from "@/lib/citations";

describe("parseAnswer", () => {
  it("splits text and citation markers", () => {
    expect(parseAnswer("Cats purr [1].")).toEqual([
      [
        { kind: "text", text: "Cats purr " },
        { kind: "cite", number: 1 },
        { kind: "text", text: "." },
      ],
    ]);
  });

  it("splits grouped markers and paragraphs", () => {
    const [first, second] = parseAnswer("One [1, 2][3]\n\nTwo");

    expect(first!.filter((part) => part.kind === "cite").map((part) => part.kind === "cite" && part.number)).toEqual([
      1, 2, 3,
    ]);
    expect(second).toEqual([{ kind: "text", text: "Two" }]);
  });

  it("leaves other brackets alone", () => {
    expect(parseAnswer("See [note] and [a1]")).toEqual([[{ kind: "text", text: "See [note] and [a1]" }]]);
  });
});

describe("highlight", () => {
  it("marks the words of the query, ignoring case, also inside longer words", () => {
    expect(highlight("Deploys on Fridays", "friday deploys")).toEqual([
      { text: "Deploys", match: true },
      { text: " on ", match: false },
      { text: "Friday", match: true },
      { text: "s", match: false },
    ]);
  });

  it("ignores short words and regex characters", () => {
    expect(highlight("a (b) c", "a (b)")).toEqual([{ text: "a (b) c", match: false }]);
  });
});
