const SECONDARY_PREFIX = "\u001fsecondary:";

export interface ParsedTag {
  level: "primary" | "secondary";
  label: string;
}

export function expandTagValue(tag: string): ParsedTag[] {
  const normalizedTag = tag.trim();
  if (normalizedTag.startsWith(SECONDARY_PREFIX)) {
    return [
      {
        level: "secondary",
        label: normalizedTag.slice(SECONDARY_PREFIX.length).trim(),
      },
    ];
  }

  const slashParts = normalizedTag
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean);
  if (slashParts.length > 1) {
    return [
      {
        level: "primary",
        label: slashParts[0] ?? "",
      },
      {
        level: "secondary",
        label: slashParts.slice(1).join("/"),
      },
    ];
  }

  return [
    {
      level: "primary",
      label: slashParts[0] ?? normalizedTag,
    },
  ];
}

export function parseTagValue(tag: string): ParsedTag {
  return expandTagValue(tag)[0] ?? { level: "primary", label: "" };
}

export function buildPrimaryTagValue(label: string): string {
  return label.trim();
}

export function buildSecondaryTagValue(label: string): string {
  const normalizedLabel = label.trim();
  return normalizedLabel ? `${SECONDARY_PREFIX}${normalizedLabel}` : "";
}
