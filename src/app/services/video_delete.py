from __future__ import annotations

import shutil
from pathlib import Path
from pathlib import PurePosixPath

from app.core.config import Settings
from app.models.imports import ImportJob
from app.models.library import Video
from app.repositories.import_jobs import (
    create_delete_job,
    find_active_delete_job,
    get_import_job,
    mark_import_job_completed,
    mark_import_job_failed,
    mark_import_job_running,
    update_import_job_progress,
)
from app.repositories.video_segments import list_video_segments
from app.repositories.videos import delete_video, get_video
from app.services.artwork_storage import resolve_artwork_storage_paths
from app.storage.factory import build_storage_backend


class VideoDeleteNotFoundError(RuntimeError):
    """Raised when the target video does not exist."""


def queue_video_delete_job(settings: Settings, *, video_id: int, worker: "ImportWorker") -> ImportJob:
    video = get_video(settings, video_id)
    if video is None:
        raise VideoDeleteNotFoundError(f"Video not found: {video_id}")

    existing_job = find_active_delete_job(settings, target_video_id=video_id)
    if existing_job is not None:
        return existing_job

    task_name = f"删除：{video.title}"
    job = create_delete_job(
        settings,
        source_path=video.source_path or f"video:{video.id}",
        requested_title=video.title,
        task_name=task_name,
        target_video_id=video.id,
    )
    worker.enqueue(job.id)
    return job


def process_delete_job(settings: Settings, job_id: int) -> ImportJob:
    job = get_import_job(settings, job_id)
    if job is None:
        raise VideoDeleteNotFoundError(f"Delete job not found: {job_id}")
    if job.status in {"completed", "failed", "cancelled"}:
        return job
    if job.target_video_id is None:
        return mark_import_job_failed(settings, job_id, error_message="Delete job is missing target_video_id.")

    try:
        mark_import_job_running(settings, job_id)
        delete_library_video(settings, job.target_video_id, job_id=job_id)
    except VideoDeleteNotFoundError as exc:
        return mark_import_job_failed(settings, job_id, error_message=str(exc))
    except Exception as exc:
        return mark_import_job_failed(settings, job_id, error_message=str(exc))

    return mark_import_job_completed(settings, job_id)


def delete_library_video(settings: Settings, video_id: int, *, job_id: int | None = None) -> None:
    video = get_video(settings, video_id)
    if video is None:
        raise VideoDeleteNotFoundError(f"Video not found: {video_id}")

    remote_paths = _collect_remote_paths(settings, video)
    remote_directories = _collect_remote_directories(remote_paths)
    _delete_remote_paths_best_effort(settings, remote_paths, remote_directories)
    _update_delete_job_progress(settings, job_id, progress_percent=40)
    _delete_local_artifacts(settings, video)
    _update_delete_job_progress(settings, job_id, progress_percent=70)
    _update_delete_job_progress(settings, job_id, progress_percent=90)
    delete_video(settings, video_id)


def _collect_remote_paths(settings: Settings, video: Video) -> list[str]:
    segments = list_video_segments(settings, video_id=video.id)
    paths = {
        path
        for path in [video.manifest_path, *(segment.cloud_path for segment in segments)]
        if path
    }
    return sorted(paths)


def _collect_remote_directories(remote_paths: list[str]) -> list[str]:
    directories = {
        str(PurePosixPath(remote_path).parent)
        for remote_path in remote_paths
        if remote_path and str(PurePosixPath(remote_path).parent) not in {"", ".", "/"}
    }
    return sorted(directories, key=lambda path: len(PurePosixPath(path).parts), reverse=True)


def _delete_remote_paths_best_effort(
    settings: Settings,
    remote_paths: list[str],
    remote_directories: list[str],
) -> None:
    if not remote_paths:
        return

    try:
        storage = build_storage_backend(settings)
    except Exception:
        return

    try:
        for remote_path in remote_paths:
            try:
                storage.delete_path(remote_path)
            except Exception:
                continue
        for remote_directory in remote_directories:
            try:
                storage.delete_path(remote_directory)
            except Exception:
                continue
    finally:
        close = getattr(storage, "close", None)
        if callable(close):
            close()


def _delete_local_artifacts(settings: Settings, video: Video) -> None:
    shutil.rmtree(settings.segment_staging_dir / str(video.id), ignore_errors=True)
    for cover_file in _resolve_artwork_files(settings, video):
        cover_file.unlink(missing_ok=True)


def _resolve_artwork_files(settings: Settings, video: Video) -> list[Path]:
    resolved: list[Path] = []
    seen_paths: set[Path] = set()
    for artwork_path in [video.cover_path, video.poster_path]:
        if not artwork_path:
            continue
        for storage_path in resolve_artwork_storage_paths(settings, artwork_path=artwork_path):
            if storage_path in seen_paths:
                continue
            seen_paths.add(storage_path)
            resolved.append(storage_path)
    return resolved


def _update_delete_job_progress(settings: Settings, job_id: int | None, *, progress_percent: int) -> None:
    if job_id is None:
        return
    update_import_job_progress(settings, job_id, progress_percent=progress_percent)
