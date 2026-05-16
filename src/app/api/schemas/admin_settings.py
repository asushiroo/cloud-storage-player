from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AdminSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    playback_download_transfer_concurrency: int


class AdminSettingsUpdateRequest(BaseModel):
    playback_download_transfer_concurrency: int | None = Field(default=None, ge=1, le=32)


class AdminPasswordUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class AdminPasswordUpdateResponse(BaseModel):
    updated: bool
