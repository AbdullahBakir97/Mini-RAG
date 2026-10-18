import { describe, expect, it } from "vitest";

import { highlight } from "@/lib/citations";

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
