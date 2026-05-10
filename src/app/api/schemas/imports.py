from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImportRequest(BaseModel):
    source_path: str = Field(min_length=1)
    folder_id: int | None = None
    title: str | None = None
    tags: list[str] = Field(default_factory=list)


class ImportFolderRequest(BaseModel):
    source_path: str = Field(min_length=1)
    folder_id: int | None = None
    tags: list[str] = Field(default_factory=list)


class ImportFolderResponse(BaseModel):
    source_path: str
    created_job_count: int
    created_job_ids: list[int] = Field(default_factory=list)


class ClearedImportJobsResponse(BaseModel):
    deleted_job_count: int
    status_group: Literal["completed", "failed"]


class CancelAllImportJobsResponse(BaseModel):
    updated_job_count: int


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_path: str
    folder_id: int | None
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
    created_at: str
    updated_at: str
