from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.services.baidu_oauth import (
    BaiduOAuthConfigurationError,
    get_baidu_access_token,
    get_baidu_refresh_token,
    persist_baidu_token,
    set_baidu_refresh_token,
)
from app.storage.baidu_api import BaiduApiError, BaiduOpenApi
from app.storage.base import StorageBackend, StorageEntry

SLICE_MD5_WINDOW_BYTES = 256 * 1024


class BaiduStorageBackend(StorageBackend):
    def __init__(self, settings: Settings, api: BaiduOpenApi | None = None) -> None:
        self.settings = settings
        self.api = api or BaiduOpenApi()
        self._owns_api = api is None
        self._access_token: str | None = None

    def close(self) -> None:
        if self._owns_api:
            self.api.close()

    def upload_file(self, local_path: Path, remote_path: str) -> None:
        self._upload_payload(local_path.read_bytes(), remote_path)

    def upload_bytes(self, payload: bytes, remote_path: str) -> None:
        self._upload_payload(payload, remote_path)

    def _upload_payload(self, payload: bytes, remote_path: str) -> None:
        baidu_path = normalize_baidu_path(remote_path)
        access_token = self._load_access_token()
        content_md5 = hashlib.md5(payload).hexdigest()
        slice_md5 = hashlib.md5(payload[:SLICE_MD5_WINDOW_BYTES]).hexdigest()
        precreated = self.api.precreate_file(
            access_token=access_token,
            remote_path=baidu_path,
            size=len(payload),
            block_list=[content_md5],
            content_md5=content_md5,
            slice_md5=slice_md5,
        )
        if int(precreated.get("return_type", 1)) == 2:
            return

        uploadid = precreated.get("uploadid")
        if not uploadid:
            raise BaiduApiError("Baidu precreate response did not include uploadid.")

        uploaded_md5 = self.api.upload_tmpfile(
            access_token=access_token,
            remote_path=baidu_path,
            uploadid=str(uploadid),
            partseq=0,
            payload=payload,
        )
        self.api.create_file(
            access_token=access_token,
            remote_path=baidu_path,
            size=len(payload),
            uploadid=str(uploadid),
            block_list=[uploaded_md5],
        )

    def download_bytes(self, remote_path: str) -> bytes:
        baidu_path = normalize_baidu_path(remote_path)
        access_token = self._load_access_token()
        return self.api.download_file(access_token=access_token, remote_path=baidu_path)

    def exists(self, remote_path: str) -> bool:
        try:
            access_token = self._load_access_token()
            self._resolve_metadata(access_token, normalize_baidu_path(remote_path))
        except (FileNotFoundError, BaiduApiError, BaiduOAuthConfigurationError, ValueError):
            return False
        return True

    def list_directory(self, remote_path: str) -> list[StorageEntry]:
        access_token = self._load_access_token()
        entries = self.api.list_directory(
            access_token=access_token,
            dir_path=normalize_baidu_path(remote_path),
        )
        return [
            StorageEntry(
                path=str(entry.get("path") or ""),
                is_dir=bool(int(entry.get("isdir", 0))),
            )
            for entry in entries
            if entry.get("path")
        ]

    def delete_path(self, remote_path: str) -> None:
        access_token = self._load_access_token()
        self.api.delete_paths(
            access_token=access_token,
            remote_paths=[normalize_baidu_path(remote_path)],
        )

    def get_file_size(self, remote_path: str) -> int | None:
        try:
            access_token = self._load_access_token()
            metadata = self._resolve_metadata(access_token, normalize_baidu_path(remote_path))
        except (FileNotFoundError, BaiduApiError, BaiduOAuthConfigurationError, ValueError):
            return None
        size_value = metadata.get("size")
        if size_value is None:
            return None
        try:
            return int(size_value)
        except (TypeError, ValueError):
            return None

    def _resolve_metadata(self, access_token: str, remote_path: str) -> dict:
        parent_path = PurePosixPath(remote_path).parent.as_posix() or "/"
        entries = self.api.list_directory(access_token=access_token, dir_path=parent_path)
        for entry in entries:
            if entry.get("path") == remote_path:
                fs_id = entry.get("fs_id")
                if fs_id is None:
                    break
                metadata = self.api.get_file_metas(
                    access_token=access_token,
                    fsids=[int(fs_id)],
                    dlink=True,
                )
                if metadata:
                    return metadata[0]
                break
        raise FileNotFoundError(f"Baidu remote object not found: {remote_path}")

    def _load_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        stored_access_token = get_baidu_access_token(self.settings)
        if stored_access_token:
            self._access_token = stored_access_token
            return self._access_token
        refresh_token = get_baidu_refresh_token(self.settings)
        if not refresh_token:
            raise BaiduOAuthConfigurationError("Baidu refresh token is not configured.")
        if not self.settings.baidu_app_key:
            raise BaiduOAuthConfigurationError("BAIDU_APP_KEY is not configured.")
        if not self.settings.baidu_secret_key:
            raise BaiduOAuthConfigurationError("BAIDU_SECRET_KEY is not configured.")

        token = self.api.refresh_access_token(
            client_id=self.settings.baidu_app_key,
            client_secret=self.settings.baidu_secret_key,
            refresh_token=refresh_token,
        )
        if token.refresh_token != refresh_token:
            set_baidu_refresh_token(self.settings, token.refresh_token)
        persist_baidu_token(self.settings, token)
        self._access_token = token.access_token
        return self._access_token


def normalize_baidu_path(remote_path: str) -> str:
    relative_path = PurePosixPath(remote_path.strip().lstrip("/"))
    if not relative_path.parts:
        raise ValueError("remote_path must not be empty.")
    if any(part == ".." for part in relative_path.parts):
        raise ValueError("remote_path must not escape the storage root.")

    normalized_path = "/" + "/".join(relative_path.parts)
    if normalized_path.startswith("/apps/"):
        return normalized_path
    return f"/apps{normalized_path}"
