from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.config import Settings
from app.core.keys import load_content_key
from app.repositories.video_segments import NewVideoSegment, create_video_segments, delete_video_segments
from app.repositories.videos import (
    create_video,
    get_video_by_manifest_path,
    update_video_sync_metadata,
)
from app.services.manifests import (
    build_encrypted_manifest_filename,
    decrypt_manifest_payload,
    local_segment_path,
)
from app.services.settings import get_public_settings
from app.storage.baidu_api import BaiduApiError
from app.storage.factory import build_storage_backend


@dataclass(slots=True)
class CatalogSyncResult:
    discovered_manifest_count: int = 0
    created_video_count: int = 0
    updated_video_count: int = 0
    failed_manifest_count: int = 0
    errors: list[str] = field(default_factory=list)


class ManifestSourcePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str | None = None
    size: int = Field(ge=0)
    mime_type: str = Field(min_length=1)
    duration_seconds: float | None = None


class ManifestSegmentPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    index: int = Field(ge=0)
    original_offset: int = Field(ge=0)
    original_length: int = Field(gt=0)
    ciphertext_size: int = Field(gt=0)
    plaintext_sha256: str = Field(min_length=1)
    remote_path: str = Field(min_length=1)
    nonce_b64: str = Field(min_length=1)
    tag_b64: str = Field(min_length=1)


class ManifestPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    source: ManifestSourcePayload
    content_fingerprint: str | None = None
    original_size: int = Field(ge=0)
    mime_type: str = Field(min_length=1)
    segment_count: int = Field(ge=0)
    segments: list[ManifestSegmentPayload]

    @model_validator(mode="after")
    def validate_segment_count(self) -> "ManifestPayload":
        if self.segment_count != len(self.segments):
            raise ValueError("manifest segment_count does not match segments length.")
        return self


def sync_remote_catalog(settings: Settings) -> CatalogSyncResult:
    storage = build_storage_backend(settings)
    root_path = get_public_settings(settings).baidu_root_path.rstrip("/")
    try:
        content_key = load_content_key(settings)
    except (FileNotFoundError, ValueError):
        content_key = None
    manifest_paths = _discover_manifest_paths(
        storage,
        root_path=root_path,
        content_key=content_key,
    )

    result = CatalogSyncResult(discovered_manifest_count=len(manifest_paths))
    for manifest_path in manifest_paths:
        try:
            manifest = _load_manifest(storage, manifest_path, content_key=content_key)
            existing_video = get_video_by_manifest_path(settings, manifest_path)
            if existing_video is None:
                video = create_video(
                    settings,
                    title=manifest.title,
                    mime_type=manifest.mime_type,
                    size=manifest.original_size,
                    duration_seconds=manifest.source.duration_seconds,
                    manifest_path=manifest_path,
                    source_path=manifest.source.path,
                    tags=manifest.tags,
                    content_fingerprint=manifest.content_fingerprint,
                )
                result.created_video_count += 1
            else:
                video = update_video_sync_metadata(
                    settings,
                    existing_video.id,
                    title=manifest.title,
                    mime_type=manifest.mime_type,
                    size=manifest.original_size,
                    duration_seconds=manifest.source.duration_seconds,
                    manifest_path=manifest_path,
                    source_path=manifest.source.path,
                    tags=manifest.tags,
                    content_fingerprint=manifest.content_fingerprint,
                )
                delete_video_segments(settings, video_id=video.id)
                result.updated_video_count += 1

            create_video_segments(
                settings,
                video_id=video.id,
                segments=[
                    NewVideoSegment(
                        segment_index=segment.index,
                        original_offset=segment.original_offset,
                        original_length=segment.original_length,
                        ciphertext_size=segment.ciphertext_size,
                        plaintext_sha256=segment.plaintext_sha256,
                        nonce_b64=segment.nonce_b64,
                        tag_b64=segment.tag_b64,
                        cloud_path=segment.remote_path,
                        local_staging_path=str(
                            local_segment_path(settings, video_id=video.id, segment_index=segment.index)
                        ),
                    )
                    for segment in manifest.segments
                ],
            )
        except (OSError, ValueError, ValidationError) as exc:
            result.failed_manifest_count += 1
            result.errors.append(f"{manifest_path}: {exc}")

    return result


def _discover_manifest_paths(storage, *, root_path: str, content_key: bytes | None) -> list[str]:
    manifest_paths: set[str] = set()
    for entry in storage.list_directory(root_path):
        if not entry.is_dir:
            continue
        manifest_path = str(PurePosixPath(entry.path.rstrip("/")) / "manifest.json")
        if storage.exists(manifest_path):
            manifest_paths.add(manifest_path)

    legacy_video_root_path = f"{root_path}/videos"
    for entry in _list_directory_if_exists(storage, legacy_video_root_path):
        if not entry.is_dir:
            continue
        manifest_path = str(PurePosixPath(entry.path.rstrip("/")) / "manifest.json")
        if storage.exists(manifest_path):
            manifest_paths.add(manifest_path)

    if content_key is not None:
        encrypted_manifest_filename = build_encrypted_manifest_filename(content_key)
        for entry in storage.list_directory(root_path):
            if not entry.is_dir:
                continue
            manifest_path = str(PurePosixPath(entry.path.rstrip("/")) / encrypted_manifest_filename)
            if storage.exists(manifest_path):
                manifest_paths.add(manifest_path)

    return sorted(manifest_paths)


def _list_directory_if_exists(storage, remote_path: str):
    try:
        return storage.list_directory(remote_path)
    except (FileNotFoundError, BaiduApiError):
        return []


def _load_manifest(storage, manifest_path: str, *, content_key: bytes | None) -> ManifestPayload:
    payload_bytes = storage.download_bytes(manifest_path)
    if payload_bytes.lstrip().startswith(b"{"):
        payload = json.loads(payload_bytes.decode("utf-8"))
    else:
        payload = decrypt_manifest_payload(payload_bytes, key=content_key)
    return ManifestPayload.model_validate(payload)
