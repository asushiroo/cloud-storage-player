from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    @abstractmethod
    def upload_file(self, local_path: Path, remote_path: str) -> None:
        """Upload a local file into the storage backend."""

    @abstractmethod
    def upload_bytes(self, payload: bytes, remote_path: str) -> None:
        """Upload an in-memory payload into the storage backend."""

    @abstractmethod
    def download_bytes(self, remote_path: str) -> bytes:
        """Download a full object payload from the storage backend."""

    @abstractmethod
    def exists(self, remote_path: str) -> bool:
        """Return whether a remote object exists."""
