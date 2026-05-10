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
