from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    baidu_root_path: str
    cache_limit_bytes: int
    storage_backend: str
    remote_transfer_concurrency: int
    baidu_authorize_url: str | None
    baidu_has_refresh_token: bool


class SettingsUpdateRequest(BaseModel):
    baidu_root_path: str | None = Field(default=None, min_length=1)
    cache_limit_bytes: int | None = Field(default=None, gt=0)
    storage_backend: Literal["mock", "baidu"] | None = None
    remote_transfer_concurrency: int | None = Field(default=None, ge=1, le=32)


class BaiduOAuthRequest(BaseModel):
    code: str = Field(min_length=1)
