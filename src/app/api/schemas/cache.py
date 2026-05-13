from __future__ import annotations

from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, model_validator


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

    @model_validator(mode="after")
    def normalize_legacy_artwork_paths(self) -> "CachedVideoResponse":
        self.poster_path = _normalize_artwork_path(self.poster_path)
        self.cover_path = _normalize_artwork_path(self.cover_path)
        return self


class ClearedCacheResponse(BaseModel):
    cleared_video_count: int


def _normalize_artwork_path(path: str | None) -> str | None:
    if not path or not path.startswith("/covers/"):
        return path
    file_name = PurePosixPath(path).name
    if not file_name:
        return path
    return f"/api/artwork/{file_name}"
