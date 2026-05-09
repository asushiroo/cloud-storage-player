from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    baidu_root_path: str
    cache_limit_bytes: int


class SettingsUpdateRequest(BaseModel):
    baidu_root_path: str | None = Field(default=None, min_length=1)
    cache_limit_bytes: int | None = Field(default=None, gt=0)
