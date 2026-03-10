import { describe, expect, it } from "vitest";

import { parseChoiceOptionsFromQuestion } from "./choice";

describe("parseChoiceOptionsFromQuestion", () => {
  it("returns parsed options for A-D formatted text", () => {
    const question = [
      "Which one is correct?",
      "A. Option one",
      "B) Option two",
      "C. Option three"
    ].join("\n");

    expect(parseChoiceOptionsFromQuestion(question)).toEqual([
      "Option one",
      "Option two",
      "Option three"
    ]);
  });

  it("returns empty array when fewer than two options exist", () => {
    const question = "A. One";
    expect(parseChoiceOptionsFromQuestion(question)).toEqual([]);
  });
});
