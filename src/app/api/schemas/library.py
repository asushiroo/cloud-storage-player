from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    poster_path: str | None
    mime_type: str
    size: int
    duration_seconds: float | None
    manifest_path: str | None
    source_path: str | None
    created_at: str
    segment_count: int = 0
    cached_size_bytes: int = 0
    cached_segment_count: int = 0
    tags: list[str] = Field(default_factory=list)
    content_fingerprint: str | None = None
    manifest_sync_dirty: bool = False
    manifest_sync_requested_at: str | None = None


class VideoTagsUpdateRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)


class VideoMetadataUpdateRequest(BaseModel):
    title: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class VideoArtworkUpdateRequest(BaseModel):
    cover_data_url: str | None = None
    poster_data_url: str | None = None

    @model_validator(mode="after")
    def validate_at_least_one_payload(self) -> "VideoArtworkUpdateRequest":
        if self.cover_data_url is None and self.poster_data_url is None:
            raise ValueError("At least one artwork image is required.")
        return self


class CatalogSyncResponse(BaseModel):
    discovered_manifest_count: int
    created_video_count: int
    updated_video_count: int
    failed_manifest_count: int
    errors: list[str]
