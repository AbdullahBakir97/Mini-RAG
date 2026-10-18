import { describe, expect, it } from "vitest";

import { highlight, strip } from "@/lib/citations";

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

describe("strip", () => {
  it("previews an answer as plain prose", () => {
    expect(strip("Deploys run **on weekdays** [1].\n\n* From main [1, 2].\n1. Reviewed")).toBe(
      "Deploys run on weekdays. From main. Reviewed",
    );
  });
});
