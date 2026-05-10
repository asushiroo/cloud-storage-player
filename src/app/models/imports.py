from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ImportJob:
    id: int
    source_path: str
    folder_id: int | None
    requested_title: str | None
    job_kind: str
    task_name: str
    status: str
    progress_percent: int
    error_message: str | None
    video_id: int | None
    target_video_id: int | None
    cancel_requested: bool
    created_at: str
    updated_at: str
    requested_tags: list[str] = field(default_factory=list)
