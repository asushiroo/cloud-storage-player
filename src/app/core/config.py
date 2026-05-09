from __future__ import annotations

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
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins_raw.split(",")
            if origin.strip()
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
