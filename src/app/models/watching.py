from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class VideoWatchSession:
    id: int
    video_id: int
    session_token: str
    started_at: str
    last_activity_at: str
    completed_at: str | None
    accumulated_watch_seconds: float
    last_position_seconds: float
    max_position_seconds: float
    valid_play_recorded: bool
    bounce_recorded: bool


@dataclass(slots=True)
class TagPreference:
    tag_value: str
    tag_level: str
    interest_sum: float
    interest_count: int
    preference_score: float
    exposure_count: int
    updated_at: str


@dataclass(slots=True)
class RecommendationShelf:
    recommended_videos: list[int] = field(default_factory=list)
    continue_watching_videos: list[int] = field(default_factory=list)
    popular_videos: list[int] = field(default_factory=list)
