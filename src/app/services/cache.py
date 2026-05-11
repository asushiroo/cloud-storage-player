from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from app.core.config import Settings
from app.models.imports import ImportJob
from app.repositories.import_jobs import (
    create_cache_job,
    find_active_cache_job,
    get_import_job,
    mark_import_job_cancelled,
    mark_import_job_completed,
    mark_import_job_failed,
    mark_import_job_running,
    record_import_job_transfer,
    update_import_job_progress,
)
from app.repositories.video_segments import (
    list_all_video_segments,
    list_video_segments,
    update_video_segment_local_staging_path,
)
from app.repositories.videos import get_video, list_videos
from app.services.job_control import JobCancelledError, throw_if_cancel_requested
from app.services.manifests import local_segment_path
from app.storage.factory import build_storage_backend


class VideoCacheNotFoundError(RuntimeError):
    """Raised when the target video does not exist."""


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


def get_cache_summary(settings: Settings) -> CacheSummary:
    cached_videos = list_cached_videos(settings)
    return CacheSummary(
        total_size_bytes=sum(video.cached_size_bytes for video in cached_videos),
        video_count=len(cached_videos),
    )


def list_cached_videos(settings: Settings) -> list[CachedVideo]:
    videos = {video.id: video for video in list_videos(settings)}
    segments_by_video_id: dict[int, list] = {}
    for segment in list_all_video_segments(settings):
        segments_by_video_id.setdefault(segment.video_id, []).append(segment)

    cached_videos: list[CachedVideo] = []
    for video_id, segments in segments_by_video_id.items():
        video = videos.get(video_id)
        if video is None:
            continue

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

        if cached_segment_count == 0:
            continue

        cached_videos.append(
            CachedVideo(
                id=video.id,
                title=video.title,
                poster_path=video.poster_path,
                cover_path=video.cover_path,
                cached_size_bytes=cached_size_bytes,
                cached_segment_count=cached_segment_count,
                total_segment_count=len(segments),
            )
        )

    cached_videos.sort(key=lambda item: (item.title.casefold(), item.id))
    return cached_videos


def clear_video_cache(settings: Settings, *, video_id: int) -> None:
    video = get_video(settings, video_id)
    if video is None:
        raise VideoCacheNotFoundError(f"Video not found: {video_id}")
    shutil.rmtree(settings.segment_staging_dir / str(video_id), ignore_errors=True)


def clear_all_cache(settings: Settings) -> int:
    cached_videos = list_cached_videos(settings)
    for video in cached_videos:
        shutil.rmtree(settings.segment_staging_dir / str(video.id), ignore_errors=True)
    return len(cached_videos)


def queue_video_cache_job(settings: Settings, *, video_id: int, worker: "ImportWorker") -> ImportJob:
    video = get_video(settings, video_id)
    if video is None:
        raise VideoCacheNotFoundError(f"Video not found: {video_id}")

    existing_job = find_active_cache_job(settings, target_video_id=video_id)
    if existing_job is not None:
        return existing_job

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
        for index, segment in enumerate(segments, start=1):
            throw_if_cancel_requested(settings, job_id)
            segment_path = _resolve_local_segment_path(
                settings,
                segment.video_id,
                segment.segment_index,
                segment.local_staging_path,
            )
            if not segment.local_staging_path:
                update_video_segment_local_staging_path(
                    settings,
                    segment.id,
                    local_staging_path=str(segment_path),
                )
            if segment_path.exists() and segment_path.is_file():
                update_import_job_progress(settings, job_id, progress_percent=_cache_progress(index, len(segments)))
                continue
            if not segment.cloud_path:
                raise ValueError(f"Segment {segment.segment_index} is missing cloud_path.")

            segment_path.parent.mkdir(parents=True, exist_ok=True)
            started_at = perf_counter()
            payload = storage.download_bytes(segment.cloud_path)
            elapsed_seconds = perf_counter() - started_at
            segment_path.write_bytes(payload)
            record_import_job_transfer(
                settings,
                job_id,
                byte_count=len(payload),
                elapsed_seconds=elapsed_seconds,
            )
            update_import_job_progress(settings, job_id, progress_percent=_cache_progress(index, len(segments)))
    except JobCancelledError as exc:
        return mark_import_job_cancelled(settings, job_id, error_message=str(exc))
    except Exception as exc:
        return mark_import_job_failed(settings, job_id, error_message=str(exc))
    finally:
        close = getattr(storage, "close", None)
        if callable(close):
            close()

    return mark_import_job_completed(settings, job_id, video_id=video.id)


def _resolve_local_segment_path(
    settings: Settings,
    video_id: int,
    segment_index: int,
    local_staging_path: str | None,
) -> Path:
    if local_staging_path:
        return Path(local_staging_path)
    return local_segment_path(settings, video_id=video_id, segment_index=segment_index)


def _cache_progress(current_index: int, total_segments: int) -> int:
    if total_segments <= 0:
        return 100
    return min(95, max(10, int((current_index / total_segments) * 95)))
