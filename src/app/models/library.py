from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CachedByteRange:
    start: int
    end: int


@dataclass(slots=True)
class Video:
    id: int
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
    tags: list[str] = field(default_factory=list)
    content_fingerprint: str | None = None
    is_visible: bool = True
    has_custom_poster: bool = False
    manifest_sync_dirty: bool = False
    manifest_sync_requested_at: str | None = None
    cached_size_bytes: int = 0
    cached_segment_count: int = 0
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
    like_count: int = 0
    highlight_start_seconds: float | None = None
    highlight_end_seconds: float | None = None
    highlight_bucket_count: int = 20
    highlight_heatmap: list[float] = field(default_factory=list)
    cached_byte_ranges: list[CachedByteRange] = field(default_factory=list)
