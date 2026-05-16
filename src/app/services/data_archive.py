from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

ARCHIVE_MANIFEST_NAME = "manifest.json"
ARCHIVE_FORMAT = "cloud-storage-player-local-data"
ARCHIVE_VERSION = 1


@dataclass(slots=True)
class DataArchiveResult:
    output_path: Path
    included_entries: list[str]


def save_local_data_archive(settings: Settings, *, output_path: Path) -> DataArchiveResult:
    included_entries: list[str] = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest_payload = {
            "format": ARCHIVE_FORMAT,
            "version": ARCHIVE_VERSION,
            "entries": [],
        }
        for source_path, archive_name in _iter_archive_entries(settings):
            if not source_path.exists() or not source_path.is_file():
                continue
            archive.write(source_path, arcname=archive_name)
            manifest_payload["entries"].append(archive_name)
            included_entries.append(archive_name)
        archive.writestr(
            ARCHIVE_MANIFEST_NAME,
            json.dumps(manifest_payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    return DataArchiveResult(output_path=output_path, included_entries=included_entries)


def load_local_data_archive(settings: Settings, *, archive_path: Path) -> DataArchiveResult:
    if not archive_path.exists() or not archive_path.is_file():
        raise FileNotFoundError(f"Archive file does not exist: {archive_path}")
    _ensure_restore_targets_absent(settings)
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        manifest_payload = json.loads(archive.read(ARCHIVE_MANIFEST_NAME).decode("utf-8"))
        if manifest_payload.get("format") != ARCHIVE_FORMAT or int(manifest_payload.get("version", 0)) != ARCHIVE_VERSION:
            raise ValueError("Archive format is invalid.")
        included_entries = [str(item) for item in manifest_payload.get("entries", [])]
        for entry in included_entries:
            target = _archive_target_path(settings, entry)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry, "r") as source_file, target.open("wb") as target_file:
                target_file.write(source_file.read())
    return DataArchiveResult(output_path=archive_path, included_entries=included_entries)


def _iter_archive_entries(settings: Settings):
    yield settings.database_file, "data/cloud_storage_player.db"
    yield settings.content_key_file, "data/keys/content.key"
    env_path = settings.runtime_root / ".env"
    yield env_path, ".env"


def _archive_target_path(settings: Settings, archive_name: str) -> Path:
    normalized = archive_name.replace("\\", "/").strip("/")
    if normalized == ".env":
        return settings.runtime_root / ".env"
    return settings.runtime_root / normalized


def _ensure_restore_targets_absent(settings: Settings) -> None:
    existing_targets = [
        path
        for path, _ in _iter_archive_entries(settings)
        if path.exists()
    ]
    if existing_targets:
        raise ValueError(
            "Local data already exists, refusing to overwrite: "
            + ", ".join(str(path) for path in existing_targets)
        )
