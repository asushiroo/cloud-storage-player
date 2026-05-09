from __future__ import annotations

from pathlib import Path

from app.storage.base import StorageBackend


class BaiduStorageBackend(StorageBackend):
    def upload_file(self, local_path: Path, remote_path: str) -> None:
        raise NotImplementedError("Baidu storage backend is not implemented yet.")

    def upload_bytes(self, payload: bytes, remote_path: str) -> None:
        raise NotImplementedError("Baidu storage backend is not implemented yet.")

    def download_bytes(self, remote_path: str) -> bytes:
        raise NotImplementedError("Baidu storage backend is not implemented yet.")

    def exists(self, remote_path: str) -> bool:
        raise NotImplementedError("Baidu storage backend is not implemented yet.")
