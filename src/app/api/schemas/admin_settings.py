from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AdminSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    playback_download_transfer_concurrency: int
    baidu_app_key: str
    baidu_secret_key: str
    baidu_sign_key: str
    baidu_oauth_redirect_uri: str
    session_secret: str


class AdminSettingsUpdateRequest(BaseModel):
    playback_download_transfer_concurrency: int | None = Field(default=None, ge=1, le=32)
    baidu_app_key: str | None = None
    baidu_secret_key: str | None = None
    baidu_sign_key: str | None = None
    baidu_oauth_redirect_uri: str | None = None
    session_secret: str | None = Field(default=None, min_length=16)


class AdminPasswordUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class AdminPasswordUpdateResponse(BaseModel):
    updated: bool
