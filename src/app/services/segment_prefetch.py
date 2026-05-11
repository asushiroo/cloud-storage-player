from __future__ import annotations

from pathlib import Path
from threading import Lock, Thread

from app.core.config import Settings
from app.models.segments import VideoSegment
from app.repositories.video_segments import update_video_segment_local_staging_path
from app.services.manifests import local_segment_path
from app.storage.factory import build_storage_backend

_PREFETCH_WINDOW_SIZE = 5
_inflight_lock = Lock()
_inflight_segments: set[tuple[int, int]] = set()


def select_prefetch_segments(segments: list[VideoSegment], *, start_segment_index: int) -> list[VideoSegment]:
    return [
        segment
        for segment in segments
        if segment.segment_index > start_segment_index and segment.cloud_path
    ][: _PREFETCH_WINDOW_SIZE]


def trigger_segment_prefetch(settings: Settings, segments: list[VideoSegment]) -> None:
    for segment in segments:
        segment_path = _resolve_segment_cache_path(settings, segment)
        if segment_path.exists() and segment_path.is_file():
            continue

        key = (segment.video_id, segment.segment_index)
        with _inflight_lock:
            if key in _inflight_segments:
                continue
            _inflight_segments.add(key)

        Thread(
            target=_prefetch_segment,
            args=(settings, segment, key),
            name=f"cloud-storage-player-prefetch-{segment.video_id}-{segment.segment_index}",
            daemon=True,
        ).start()


def cache_remote_segment(settings: Settings, segment: VideoSegment) -> bytes:
    if not segment.cloud_path:
        raise FileNotFoundError("Segment cloud path is missing.")

    storage = build_storage_backend(settings)
    try:
        payload = storage.download_bytes(segment.cloud_path)
    finally:
        close = getattr(storage, "close", None)
        if callable(close):
            close()

    segment_path = _resolve_segment_cache_path(settings, segment)
    segment_path.parent.mkdir(parents=True, exist_ok=True)
    segment_path.write_bytes(payload)
    if segment.local_staging_path != str(segment_path):
        update_video_segment_local_staging_path(
            settings,
            segment.id,
            local_staging_path=str(segment_path),
        )
    return payload


def _prefetch_segment(
    settings: Settings,
    segment: VideoSegment,
    key: tuple[int, int],
) -> None:
    try:
        cache_remote_segment(settings, segment)
    except Exception:
        pass
    finally:
        with _inflight_lock:
            _inflight_segments.discard(key)


def _resolve_segment_cache_path(settings: Settings, segment: VideoSegment) -> Path:
    if segment.local_staging_path:
        return Path(segment.local_staging_path)
    return local_segment_path(
        settings,
        video_id=segment.video_id,
        segment_index=segment.segment_index,
    )
