from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ImportRequest(BaseModel):
    source_path: str = Field(min_length=1)
    folder_id: int | None = None
    title: str | None = None


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
