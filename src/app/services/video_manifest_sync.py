from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import Settings
from app.core.keys import load_content_key
from app.models.library import Video
from app.models.segments import VideoSegment
from app.repositories.video_segments import list_video_segments
from app.repositories.videos import (
    get_video,
    list_dirty_manifest_videos,
    mark_video_manifest_sync_clean,
    update_video_manifest_path,
)
from app.services.manifests import (
    build_remote_manifest_path,
    encrypted_remote_manifest_upload_path,
    write_encrypted_remote_manifest,
    write_local_manifest,
)
from app.storage.factory import build_storage_backend

logger = logging.getLogger(__name__)
_SYNC_DELAY = timedelta(minutes=10)


def rewrite_local_video_manifests(settings: Settings, video_id: int) -> Video:
    video = get_video(settings, video_id)
    if video is None:
        raise ValueError(f"Video not found: {video_id}")

    segments = list_video_segments(settings, video_id=video_id)
    if not segments:
        raise ValueError(f"Video has no segments: {video_id}")

    content_key = load_content_key(settings)
    remote_manifest_path = build_remote_manifest_path(settings, video_id=video.id, key=content_key)
    write_local_manifest(settings, video=video, segments=segments)
    write_encrypted_remote_manifest(settings, video=video, segments=segments, key=content_key)
    return update_video_manifest_path(settings, video.id, manifest_path=remote_manifest_path)


def can_rewrite_video_manifests(settings: Settings, video_id: int) -> bool:
    video = get_video(settings, video_id)
    if video is None or not video.manifest_path:
        return False
    return bool(list_video_segments(settings, video_id=video_id))


def sync_due_video_manifests(settings: Settings, *, now: datetime | None = None) -> int:
    current_time = now or datetime.now(UTC)
    synced_count = 0

    for video in list_dirty_manifest_videos(settings):
        if not _is_due(video, now=current_time):
            continue
        try:
            _upload_remote_manifest(settings, video)
        except Exception as exc:
            logger.warning("Failed to sync remote manifest for video %s: %s", video.id, exc)
            continue
        mark_video_manifest_sync_clean(settings, video.id)
        synced_count += 1

    return synced_count


def _upload_remote_manifest(settings: Settings, video: Video) -> None:
    manifest_upload_path = encrypted_remote_manifest_upload_path(settings, video_id=video.id)
    if not manifest_upload_path.exists() or not manifest_upload_path.is_file():
        rewrite_local_video_manifests(settings, video.id)

    upload_path = encrypted_remote_manifest_upload_path(settings, video_id=video.id)
    if video.manifest_path is None:
        raise ValueError(f"Video manifest path is missing: {video.id}")

    storage = build_storage_backend(settings)
    try:
        storage.upload_file(upload_path, video.manifest_path)
    finally:
        close = getattr(storage, "close", None)
        if callable(close):
            close()


def _is_due(video: Video, *, now: datetime) -> bool:
    if not video.manifest_sync_requested_at:
        return True
    requested_at = datetime.fromisoformat(video.manifest_sync_requested_at.replace(" ", "T"))
    if requested_at.tzinfo is None:
        requested_at = requested_at.replace(tzinfo=UTC)
    return now >= requested_at + _SYNC_DELAY
