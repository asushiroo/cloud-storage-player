from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath

from app.storage.base import StorageBackend, StorageEntry


class MockStorageBackend(StorageBackend):
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        destination = self.local_path_for(remote_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, destination)

    def upload_bytes(self, payload: bytes, remote_path: str) -> None:
        destination = self.local_path_for(remote_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    def download_bytes(self, remote_path: str) -> bytes:
        path = self.local_path_for(remote_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Remote object not found: {remote_path}")
        return path.read_bytes()

    def exists(self, remote_path: str) -> bool:
        path = self.local_path_for(remote_path)
        return path.exists() and path.is_file()

    def list_directory(self, remote_path: str) -> list[StorageEntry]:
        directory = self.local_path_for(remote_path)
        if not directory.exists() or not directory.is_dir():
            return []

        base_path = _normalized_remote_string(remote_path)
        return [
            StorageEntry(
                path=_join_remote_path(base_path, child.name),
                is_dir=child.is_dir(),
            )
            for child in sorted(directory.iterdir(), key=lambda child: child.name)
        ]

    def delete_path(self, remote_path: str) -> None:
        path = self.local_path_for(remote_path)
        if not path.exists():
            return
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
            return
        path.unlink(missing_ok=True)

    def local_path_for(self, remote_path: str) -> Path:
        relative_path = _normalize_remote_path(remote_path)
        return self.root_dir / Path(*relative_path.parts)


def _normalize_remote_path(remote_path: str) -> PurePosixPath:
    normalized = PurePosixPath(remote_path.lstrip("/"))
    if not normalized.parts:
        raise ValueError("remote_path must not be empty.")
    if any(part == ".." for part in normalized.parts):
        raise ValueError("remote_path must not escape the storage root.")
    return normalized


def _normalized_remote_string(remote_path: str) -> str:
    return "/" + "/".join(_normalize_remote_path(remote_path).parts)


def _join_remote_path(remote_path: str, child_name: str) -> str:
    return str(PurePosixPath(remote_path) / child_name)
