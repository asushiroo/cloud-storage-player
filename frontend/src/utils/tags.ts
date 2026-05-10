export function parseTagInput(value: string): string[] {
  const seen = new Set<string>();
  const tags: string[] = [];

  for (const rawPart of value.split(/[\n,，]/g)) {
    const part = rawPart.trim();
    if (!part) {
      continue;
    }
    const key = part.toLocaleLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    tags.push(part);
  }

  return tags;
}

export function formatTagInput(tags: string[]): string {
  return tags.join(", ");
}
