from __future__ import annotations

from app.core.config import Settings
from app.storage.base import StorageBackend
from app.storage.baidu import BaiduStorageBackend
from app.storage.mock import MockStorageBackend


def build_storage_backend(settings: Settings) -> StorageBackend:
    backend_name = settings.storage_backend.strip().lower()
    if backend_name == "mock":
        return MockStorageBackend(settings.mock_storage_dir)
    if backend_name == "baidu":
        return BaiduStorageBackend()
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
