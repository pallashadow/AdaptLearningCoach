export function parseChoiceOptionsFromQuestion(question: string): string[] {
  const lines = question.split(/\r?\n/);
  const options: string[] = [];

  for (const line of lines) {
    const match = line.match(/^\s*[A-D][.)]\s+(.+)$/i);
    if (!match) {
      continue;
    }
    options.push(match[1].trim());
  }

  return options.length >= 2 && options.length <= 4 ? options : [];
}
