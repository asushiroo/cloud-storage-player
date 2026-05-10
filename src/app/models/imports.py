from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ImportJob:
    id: int
    source_path: str
    folder_id: int | None
    requested_title: str | None
    status: str
    progress_percent: int
    error_message: str | None
    video_id: int | None
    created_at: str
    updated_at: str
    requested_tags: list[str] = field(default_factory=list)
