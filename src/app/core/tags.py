from __future__ import annotations

import json


def normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = tag.strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def decode_tags(value: str | None) -> list[str]:
    if not value:
        return []
    payload = json.loads(value)
    if not isinstance(payload, list):
        return []
    return normalize_tags([str(item) for item in payload])


def encode_tags(tags: list[str] | None) -> str:
    return json.dumps(normalize_tags(tags), ensure_ascii=False, separators=(",", ":"))


def extract_primary_tags(tags: list[str] | None) -> list[str]:
    primary_tags: list[str] = []
    seen: set[str] = set()
    for tag in normalize_tags(tags):
        value = tag.strip()
        if not value:
            continue
        lowered = value.casefold()
        if lowered.startswith("secondary:"):
            continue
        slash_parts = [part.strip() for part in value.split("/") if part.strip()]
        primary_tag = slash_parts[0] if slash_parts else value
        key = primary_tag.casefold()
        if not primary_tag or key in seen:
            continue
        seen.add(key)
        primary_tags.append(primary_tag)
    return primary_tags
