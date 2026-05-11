from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CacheSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_size_bytes: int
    video_count: int


class CachedVideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    poster_path: str | None
    cover_path: str | None
    cached_size_bytes: int
    cached_segment_count: int
    total_segment_count: int


class ClearedCacheResponse(BaseModel):
    cleared_video_count: int
