from __future__ import annotations

from app.core.config import Settings
from app.services.settings import get_public_settings
from app.storage.baidu import BaiduStorageBackend
from app.storage.base import StorageBackend
from app.storage.mock import MockStorageBackend


def build_storage_backend(settings: Settings) -> StorageBackend:
    backend_name = get_public_settings(settings).storage_backend
    if backend_name == "mock":
        return MockStorageBackend(settings.mock_storage_dir)
    if backend_name == "baidu":
        return BaiduStorageBackend(settings)
    raise ValueError(f"Unsupported storage backend: {backend_name}")
