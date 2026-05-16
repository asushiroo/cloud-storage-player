from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


def runtime_run_dir(settings: Settings) -> Path:
    return settings.runtime_root / "run"


def runtime_logs_dir(settings: Settings) -> Path:
    return settings.runtime_root / "logs"


def runtime_metadata_path(settings: Settings) -> Path:
    return runtime_run_dir(settings) / "service.json"
