from __future__ import annotations

from pathlib import Path, PurePosixPath

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
    valid_play_count: int = 0
    total_session_count: int = 0
    total_watch_seconds: float = 0
    last_watched_at: str | None = None
    last_position_seconds: float = 0
    avg_completion_ratio: float = 0
    bounce_count: int = 0
    bounce_rate: float = 0
    rewatch_score: float = 0
    interest_score: float = 0
    popularity_score: float = 0
    resume_score: float = 0
    recommendation_score: float = 0
    cache_priority: float = 0
    highlight_start_seconds: float | None = None
    highlight_end_seconds: float | None = None
    highlight_bucket_count: int = 20
    highlight_heatmap: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_legacy_artwork_paths(self) -> "VideoResponse":
        self.cover_path = _normalize_artwork_path(self.cover_path)
        self.poster_path = _normalize_artwork_path(self.poster_path)
        return self


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


class VideoPageResponse(BaseModel):
    items: list[VideoResponse] = Field(default_factory=list)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    total: int = Field(ge=0)
    has_more: bool = False


class CatalogSyncResponse(BaseModel):
    discovered_manifest_count: int
    created_video_count: int
    updated_video_count: int
    failed_manifest_count: int
    errors: list[str]


class VideoRecommendationShelfResponse(BaseModel):
    recommended: list[VideoResponse] = Field(default_factory=list)
    continue_watching: list[VideoResponse] = Field(default_factory=list)
    popular: list[VideoResponse] = Field(default_factory=list)


class VideoWatchHeartbeatRequest(BaseModel):
    session_token: str | None = None
    position_seconds: float = Field(ge=0)
    watched_seconds_delta: float = Field(ge=0)
    completed: bool = False


class VideoWatchHeartbeatResponse(BaseModel):
    session_token: str
    video: VideoResponse


def _normalize_artwork_path(path: str | None) -> str | None:
    if not path:
        return path
    if not path.startswith("/covers/"):
        return path
    file_name = PurePosixPath(path).name
    if not file_name:
        return path
    if file_name.endswith("-poster.jpg"):
        file_name = f"{Path(file_name).stem}.avif"
    return f"/api/artwork/{file_name}"
