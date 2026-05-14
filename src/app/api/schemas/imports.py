from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImportRequest(BaseModel):
    source_path: str = Field(min_length=1)
    title: str | None = None
    tags: list[str] = Field(default_factory=list)


class FolderImportRequest(BaseModel):
    source_dir: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class ClearedImportJobsResponse(BaseModel):
    deleted_job_count: int
    status_group: Literal["completed", "failed"]


class CancelAllImportJobsResponse(BaseModel):
    updated_job_count: int


class FolderImportResponse(BaseModel):
    discovered_file_count: int
    jobs: list["ImportJobResponse"] = Field(default_factory=list)


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requested_title: str | None
    requested_tags: list[str] = Field(default_factory=list)
    job_kind: str
    task_name: str
    status: str
    progress_percent: int
    error_message: str | None
    video_id: int | None
    target_video_id: int | None
    cancel_requested: bool
    remote_bytes_transferred: int
    remote_transfer_millis: int
    transfer_speed_bytes_per_second: float | None
    created_at: str
    updated_at: str
