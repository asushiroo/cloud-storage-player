from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.models.library import CachedByteRange
from app.models.imports import ImportJob
from app.repositories.import_jobs import (
    create_cache_job,
    find_active_cache_job,
    get_import_job,
    mark_import_job_cancelled,
    mark_import_job_completed,
    mark_import_job_failed,
    mark_import_job_running,
    update_import_job_progress,
)
from app.repositories.video_cache_entries import (
    get_video_cache_entry,
    list_video_cache_entries,
    upsert_video_cache_entry,
)
from app.repositories.video_segments import (
    list_video_segments,
    update_video_segment_local_staging_path,
)
from app.repositories.videos import get_video, list_videos
from app.services.job_control import JobCancelledError, throw_if_cancel_requested
from app.services.manifests import local_segment_path
from app.services.remote_transfers import TransferResult, run_bounded_transfers
from app.services.segment_local_paths import resolve_segment_local_staging_path, serialize_local_staging_path
from app.services.segment_prefetch import cache_remote_segment
from app.storage.factory import build_storage_backend


class VideoCacheNotFoundError(RuntimeError):
    """Raised when the target video does not exist."""


class VideoAlreadyCachedError(RuntimeError):
    """Raised when the target video is already fully cached."""


@dataclass(slots=True)
class CacheSummary:
    total_size_bytes: int
    video_count: int


@dataclass(slots=True)
class CachedVideo:
    id: int
    title: str
    poster_path: str | None
    cover_path: str | None
    cached_size_bytes: int
    cached_segment_count: int
    total_segment_count: int


@dataclass(slots=True)
class VideoCacheStatus:
    cached_size_bytes: int
    cached_segment_count: int
    total_segment_count: int

    @property
    def is_fully_cached(self) -> bool:
        return self.total_segment_count > 0 and self.cached_segment_count >= self.total_segment_count


def get_cache_summary(settings: Settings) -> CacheSummary:
    cached_videos = list_cached_videos(settings)
    return CacheSummary(
        total_size_bytes=sum(video.cached_size_bytes for video in cached_videos),
        video_count=len(cached_videos),
    )


def list_cached_videos(settings: Settings) -> list[CachedVideo]:
    videos = {video.id: video for video in list_videos(settings)}
    cache_entries = {entry.video_id: entry for entry in list_video_cache_entries(settings)}
    cached_videos: list[CachedVideo] = []
    for entry in cache_entries.values():
        if entry.cached_segment_count <= 0:
            continue
        video_id = entry.video_id
        video = videos.get(video_id)
        if video is None:
            continue

        cached_videos.append(
            CachedVideo(
                id=video.id,
                title=video.title,
                poster_path=video.poster_path,
                cover_path=video.cover_path,
                cached_size_bytes=entry.cached_size_bytes,
                cached_segment_count=entry.cached_segment_count,
                total_segment_count=entry.total_segment_count,
            )
        )

    # Backfill entries lazily for videos imported before cache-table refresh hooks.
    for video in videos.values():
        if video.id in cache_entries:
            continue
        if video.segment_count <= 0:
            continue
        status = refresh_video_cache_entry(settings, video_id=video.id)
        if status.cached_segment_count <= 0:
            continue
        cached_videos.append(
            CachedVideo(
                id=video.id,
                title=video.title,
                poster_path=video.poster_path,
                cover_path=video.cover_path,
                cached_size_bytes=status.cached_size_bytes,
                cached_segment_count=status.cached_segment_count,
                total_segment_count=status.total_segment_count,
            )
        )

    cached_videos.sort(key=lambda item: (item.title.casefold(), item.id))
    return cached_videos


def get_video_cache_status(settings: Settings, *, video_id: int) -> VideoCacheStatus:
    cached_entry = get_video_cache_entry(settings, video_id=video_id)
    if cached_entry is not None:
        return VideoCacheStatus(
            cached_size_bytes=cached_entry.cached_size_bytes,
            cached_segment_count=cached_entry.cached_segment_count,
            total_segment_count=cached_entry.total_segment_count,
        )

    status = _build_video_cache_status(
        settings,
        segments=list_video_segments(settings, video_id=video_id),
    )
    refresh_video_cache_entry(settings, video_id=video_id)
    return status


def clear_video_cache(settings: Settings, *, video_id: int) -> None:
    video = get_video(settings, video_id)
    if video is None:
        raise VideoCacheNotFoundError(f"Video not found: {video_id}")
    segments = list_video_segments(settings, video_id=video_id)
    cache_dirs = {
        _resolve_local_segment_path(
            settings,
            segment.video_id,
            segment.segment_index,
            segment.local_staging_path,
        )
        .parent
        for segment in segments
    }
    cache_dirs.add(local_segment_path(settings, video_id=video_id, segment_index=0).parent)
    for cache_dir in sorted(cache_dirs, key=lambda item: len(item.resolve(strict=False).parts), reverse=True):
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
    refresh_video_cache_entry(settings, video_id=video_id)


def clear_all_cache(settings: Settings) -> int:
    cached_videos = list_cached_videos(settings)
    for video in cached_videos:
        clear_video_cache(settings, video_id=video.id)
    return len(cached_videos)


def queue_video_cache_job(settings: Settings, *, video_id: int, worker: "ImportWorker") -> ImportJob:
    video = get_video(settings, video_id)
    if video is None:
        raise VideoCacheNotFoundError(f"Video not found: {video_id}")

    existing_job = find_active_cache_job(settings, target_video_id=video_id)
    if existing_job is not None:
        return existing_job

    # Always recompute once at queue time so stale table rows do not block recache.
    cache_status = refresh_video_cache_entry(settings, video_id=video_id)
    if cache_status.is_fully_cached:
        raise VideoAlreadyCachedError(f"Video already fully cached: {video_id}")

    job = create_cache_job(
        settings,
        source_path=video.source_path or video.manifest_path or f"video:{video.id}",
        requested_title=video.title,
        task_name=f"缓存：{video.title}",
        target_video_id=video.id,
    )
    worker.enqueue(job.id)
    return job


def process_cache_job(settings: Settings, job_id: int) -> ImportJob:
    job = get_import_job(settings, job_id)
    if job is None:
        raise VideoCacheNotFoundError(f"Cache job not found: {job_id}")
    if job.status in {"completed", "failed", "cancelled"}:
        return job
    if job.target_video_id is None:
        return mark_import_job_failed(settings, job_id, error_message="Cache job is missing target_video_id.")

    video = get_video(settings, job.target_video_id)
    if video is None:
        return mark_import_job_failed(settings, job_id, error_message=f"Video not found: {job.target_video_id}")

    segments = list_video_segments(settings, video_id=video.id)
    if not segments:
        return mark_import_job_failed(settings, job_id, error_message="Video has no segments to cache.")

    try:
        storage = build_storage_backend(settings)
    except Exception as exc:
        return mark_import_job_failed(settings, job_id, error_message=str(exc))

    mark_import_job_running(settings, job_id)

    try:
        pending_segments = []
        completed_segments = 0
        for segment in segments:
            throw_if_cancel_requested(settings, job_id)
            segment_path = _resolve_local_segment_path(
                settings,
                segment.video_id,
                segment.segment_index,
                segment.local_staging_path,
            )
            stored_path = serialize_local_staging_path(settings, segment_path)
            if segment.local_staging_path != stored_path:
                update_video_segment_local_staging_path(
                    settings,
                    segment.id,
                    local_staging_path=stored_path,
                )
                segment.local_staging_path = stored_path
            if segment_path.exists() and segment_path.is_file():
                completed_segments += 1
                continue
            if not segment.cloud_path:
                raise ValueError(f"Segment {segment.segment_index} is missing cloud_path.")
            pending_segments.append(segment)

        refresh_video_cache_entry(settings, video_id=video.id)

        if completed_segments:
            update_import_job_progress(
                settings,
                job_id,
                progress_percent=_cache_progress(completed_segments, len(segments)),
            )

        def on_result(
            _result: TransferResult,
            newly_completed_count: int,
            _total_pending: int,
        ) -> None:
            update_import_job_progress(
                settings,
                job_id,
                progress_percent=_cache_progress(completed_segments + newly_completed_count, len(segments)),
            )

        run_bounded_transfers(
            settings,
            job_id=job_id,
            tasks=pending_segments,
            transfer_func=lambda segment: cache_remote_segment(
                settings,
                segment,
                storage_backend=storage,
            ),
            on_result=on_result,
        )
        refresh_video_cache_entry(settings, video_id=video.id)
    except JobCancelledError as exc:
        refresh_video_cache_entry(settings, video_id=video.id)
        return mark_import_job_cancelled(settings, job_id, error_message=str(exc))
    except Exception as exc:
        refresh_video_cache_entry(settings, video_id=video.id)
        return mark_import_job_failed(settings, job_id, error_message=str(exc))
    finally:
        close = getattr(storage, "close", None)
        if callable(close):
            close()

    return mark_import_job_completed(settings, job_id, video_id=video.id)


def list_cached_byte_ranges(settings: Settings, *, video_id: int) -> list[CachedByteRange]:
    segments = list_video_segments(settings, video_id=video_id)
    if not segments:
        return []
    ranges: list[CachedByteRange] = []
    for segment in segments:
        segment_path = _resolve_local_segment_path(
            settings,
            segment.video_id,
            segment.segment_index,
            segment.local_staging_path,
        )
        if not segment_path.exists() or not segment_path.is_file():
            continue
        ranges.append(
            CachedByteRange(
                start=int(segment.original_offset),
                end=int(segment.original_offset + segment.original_length),
            )
        )
    return ranges


def refresh_video_cache_entry(settings: Settings, *, video_id: int) -> VideoCacheStatus:
    segments = list_video_segments(settings, video_id=video_id)
    status = _build_video_cache_status(settings, segments=segments)
    cache_segments_dir = local_segment_path(settings, video_id=video_id, segment_index=0).parent
    relative_dir = None
    try:
        relative_dir = str(cache_segments_dir.relative_to(settings.segment_staging_dir))
    except ValueError:
        relative_dir = str(cache_segments_dir)
    upsert_video_cache_entry(
        settings,
        video_id=video_id,
        cached_size_bytes=status.cached_size_bytes,
        cached_segment_count=status.cached_segment_count,
        total_segment_count=status.total_segment_count,
        cache_root_relative_segments_dir=relative_dir,
    )
    return status


def _resolve_local_segment_path(
    settings: Settings,
    video_id: int,
    segment_index: int,
    local_staging_path: str | None,
) -> Path:
    return resolve_segment_local_staging_path(
        settings,
        video_id=video_id,
        segment_index=segment_index,
        local_staging_path=local_staging_path,
    )


def _build_video_cache_status(settings: Settings, *, segments: list) -> VideoCacheStatus:
    cached_size_bytes = 0
    cached_segment_count = 0
    for segment in segments:
        segment_path = _resolve_local_segment_path(
            settings,
            segment.video_id,
            segment.segment_index,
            segment.local_staging_path,
        )
        if not segment_path.exists() or not segment_path.is_file():
            continue
        cached_segment_count += 1
        cached_size_bytes += segment_path.stat().st_size

    return VideoCacheStatus(
        cached_size_bytes=cached_size_bytes,
        cached_segment_count=cached_segment_count,
        total_segment_count=len(segments),
    )


def _cache_progress(current_index: int, total_segments: int) -> int:
    if total_segments <= 0:
        return 100
    return min(95, max(10, int((current_index / total_segments) * 95)))
