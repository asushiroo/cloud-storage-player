from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    cover_path: str | None
    created_at: str


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    folder_id: int | None
    title: str
    cover_path: str | None
    mime_type: str
    size: int
    duration_seconds: float | None
    manifest_path: str | None
    source_path: str | None
    created_at: str
    segment_count: int = 0


class CatalogSyncResponse(BaseModel):
    discovered_manifest_count: int
    created_video_count: int
    updated_video_count: int
    failed_manifest_count: int
    errors: list[str]
