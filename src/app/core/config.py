from __future__ import annotations

import os
from functools import cached_property, lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.security import hash_password

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = PROJECT_ROOT / "src" / "app" / "web" / "templates"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CSP_",
        extra="ignore",
    )

    app_name: str = "Cloud Storage Player"
    host: str = "0.0.0.0"
    port: int = 8000
    session_secret: str = Field(default="change-me-before-production", min_length=16)
    password: str = "admin"
    password_hash: str | None = None
    database_path: Path = Path("data/cloud_storage_player.db")
    ffprobe_binary: str = "ffprobe"
    ffmpeg_binary: str = "ffmpeg"
    covers_path: Path = Path("data/covers")
    content_key_path: Path = Path("data/keys/content.key")
    segment_staging_path: Path = Path("data/segments")
    mock_storage_path: Path = Path("data/mock-remote")
    segment_size_bytes: int = 4 * 1024 * 1024
    storage_backend: str = "mock"
    remote_transfer_concurrency: int = Field(default=5, ge=1, le=32)
    upload_transfer_concurrency: int | None = Field(default=None, ge=1, le=32)
    download_transfer_concurrency: int | None = Field(default=None, ge=1, le=32)
    baidu_upload_resume_poll_interval_seconds: int = Field(default=3600, ge=1)
    baidu_oauth_redirect_uri: str = "oob"
    cors_allowed_origins_raw: str = "http://127.0.0.1:5173,http://localhost:5173"

    @cached_property
    def effective_password_hash(self) -> str:
        if self.password_hash:
            return self.password_hash
        return hash_password(self.password)

    @property
    def templates_dir(self) -> Path:
        return TEMPLATES_DIR

    @property
    def database_file(self) -> Path:
        if self.database_path.is_absolute():
            return self.database_path
        return PROJECT_ROOT / self.database_path

    @property
    def covers_dir(self) -> Path:
        if self.covers_path.is_absolute():
            return self.covers_path
        return PROJECT_ROOT / self.covers_path

    @property
    def content_key_file(self) -> Path:
        if self.content_key_path.is_absolute():
            return self.content_key_path
        return PROJECT_ROOT / self.content_key_path

    @property
    def segment_staging_dir(self) -> Path:
        if self.segment_staging_path.is_absolute():
            return self.segment_staging_path
        return PROJECT_ROOT / self.segment_staging_path

    @property
    def mock_storage_dir(self) -> Path:
        if self.mock_storage_path.is_absolute():
            return self.mock_storage_path
        return PROJECT_ROOT / self.mock_storage_path

    @property
    def baidu_app_key(self) -> str | None:
        return os.environ.get("BAIDU_APP_KEY")

    @property
    def baidu_secret_key(self) -> str | None:
        return os.environ.get("BAIDU_SECRET_KEY")

    @property
    def baidu_sign_key(self) -> str | None:
        return os.environ.get("BAIDU_SIGN_KEY")

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins_raw.split(",")
            if origin.strip()
        ]

    @property
    def effective_upload_transfer_concurrency(self) -> int:
        return self.upload_transfer_concurrency or self.remote_transfer_concurrency

    @property
    def effective_download_transfer_concurrency(self) -> int:
        return self.download_transfer_concurrency or self.remote_transfer_concurrency


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
