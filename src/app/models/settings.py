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
    segment_cache_root_path: str
    storage_backend: str
    upload_transfer_concurrency: int
    download_transfer_concurrency: int
    baidu_authorize_url: str | None
    baidu_has_refresh_token: bool
