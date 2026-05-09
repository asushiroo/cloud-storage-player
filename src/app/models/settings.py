from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Setting:
    key: str
    value: str
    updated_at: str


@dataclass(slots=True)
class PublicSettings:
    baidu_root_path: str
    cache_limit_bytes: int
