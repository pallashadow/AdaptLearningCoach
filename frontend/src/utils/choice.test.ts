import { describe, expect, it } from "vitest";

import { extractChoiceStemFromQuestion, parseChoiceOptionsFromQuestion } from "./choice";

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

  it("strips duplicated nested labels from option text", () => {
    const question = [
      "Pick the better statement:",
      "A. A) Data partitioning helps reduce training time via parallelization.",
      "B. B) Data partitioning always increases model accuracy."
    ].join("\n");

    expect(parseChoiceOptionsFromQuestion(question)).toEqual([
      "Data partitioning helps reduce training time via parallelization.",
      "Data partitioning always increases model accuracy."
    ]);
  });
});

describe("extractChoiceStemFromQuestion", () => {
  it("returns the question stem before options", () => {
    const question = [
      "Which statement is correct about distributed training?",
      "A. Option one",
      "B. Option two"
    ].join("\n");

    expect(extractChoiceStemFromQuestion(question)).toBe(
      "Which statement is correct about distributed training?"
    );
  });

  it("returns full content when no separate stem exists", () => {
    const question = ["A. Option one", "B. Option two"].join("\n");
    expect(extractChoiceStemFromQuestion(question)).toBe(question);
  });
});
