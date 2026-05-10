from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Folder:
    id: int
    name: str
    cover_path: str | None
    created_at: str


@dataclass(slots=True)
class Video:
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
    tags: list[str] = field(default_factory=list)
