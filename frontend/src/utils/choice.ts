function stripNestedChoicePrefix(text: string): string {
  let normalized = text.trim();
  // LLM output can include duplicated labels like "A. A) xxx"; remove all leading choice markers.
  while (/^[A-D][.)]\s+/i.test(normalized)) {
    normalized = normalized.replace(/^[A-D][.)]\s+/i, "").trim();
  }
  return normalized;
}

const optionLinePattern = /^\s*[A-D][.)]\s+/i;

export function extractChoiceStemFromQuestion(question: string): string {
  const lines = question.split(/\r?\n/);
  const firstOptionIndex = lines.findIndex((line) => optionLinePattern.test(line));
  if (firstOptionIndex <= 0) {
    return question.trim();
  }

  const stem = lines.slice(0, firstOptionIndex).join("\n").trim();
  return stem || question.trim();
}

export function parseChoiceOptionsFromQuestion(question: string): string[] {
  const lines = question.split(/\r?\n/);
  const options: string[] = [];

  for (const line of lines) {
    const match = line.match(/^\s*[A-D][.)]\s+(.+)$/i);
    if (!match) {
      continue;
    }
    options.push(stripNestedChoicePrefix(match[1]));
  }

  return options.length >= 2 && options.length <= 4 ? options : [];
}
