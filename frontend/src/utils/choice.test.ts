import { describe, expect, it } from "vitest";

import { parseChoiceOptionsFromQuestion } from "./choice";

describe("parseChoiceOptionsFromQuestion", () => {
  it("returns four parsed options for A-D formatted text", () => {
    const question = [
      "Which one is correct?",
      "A. Option one",
      "B) Option two",
      "C. Option three",
      "D) Option four"
    ].join("\n");

    expect(parseChoiceOptionsFromQuestion(question)).toEqual([
      "Option one",
      "Option two",
      "Option three",
      "Option four"
    ]);
  });

  it("returns empty array when not all four options exist", () => {
    const question = "A. One\nB. Two\nC. Three";
    expect(parseChoiceOptionsFromQuestion(question)).toEqual([]);
  });
});
