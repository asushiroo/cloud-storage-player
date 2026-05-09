from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.media.covers import CoverExtractionError, extract_cover
from app.media.probe import MediaProbeError, probe_video
from app.models.imports import ImportJob
from app.models.library import Video
from app.repositories.folders import get_folder
from app.repositories.import_jobs import (
    create_import_job,
    mark_import_job_completed,
    mark_import_job_failed,
    mark_import_job_running,
)
from app.repositories.videos import create_video, update_video_cover_path


class ImportValidationError(ValueError):
    """Raised when the import request is invalid."""


def import_local_video(
    settings: Settings,
    *,
    source_path: str,
    folder_id: int | None = None,
    title: str | None = None,
) -> ImportJob:
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        raise ImportValidationError(f"Source file does not exist: {source_path}")

    if folder_id is not None and get_folder(settings, folder_id) is None:
        raise ImportValidationError(f"Folder does not exist: {folder_id}")

    requested_title = title.strip() if title else None
    job = create_import_job(
        settings,
        source_path=str(source),
        folder_id=folder_id,
        requested_title=requested_title,
    )
    mark_import_job_running(settings, job.id)

    try:
        metadata = probe_video(source, ffprobe_binary=settings.ffprobe_binary)
        video = _create_video_from_probe(
            settings,
            folder_id=folder_id,
            title=requested_title or source.stem,
            source_path=str(source),
            mime_type=metadata.mime_type,
            size=metadata.size,
            duration_seconds=metadata.duration_seconds,
        )
        video = _maybe_extract_cover(settings, source=source, video=video)
    except MediaProbeError as exc:
        return mark_import_job_failed(settings, job.id, error_message=str(exc))
    except Exception as exc:
        return mark_import_job_failed(settings, job.id, error_message=str(exc))

    return mark_import_job_completed(settings, job.id, video_id=video.id)


def _create_video_from_probe(
    settings: Settings,
    *,
    folder_id: int | None,
    title: str,
    source_path: str,
    mime_type: str,
    size: int,
    duration_seconds: float | None,
) -> Video:
    return create_video(
        settings,
        folder_id=folder_id,
        title=title,
        mime_type=mime_type,
        size=size,
        duration_seconds=duration_seconds,
        manifest_path=None,
        source_path=source_path,
    )


def _maybe_extract_cover(settings: Settings, *, source: Path, video: Video) -> Video:
    cover_output_path = settings.covers_dir / f"{video.id}.jpg"
    cover_web_path = f"/covers/{video.id}.jpg"
    try:
        extract_cover(
            source,
            cover_output_path,
            ffmpeg_binary=settings.ffmpeg_binary,
        )
    except CoverExtractionError:
        return video

    return update_video_cover_path(
        settings,
        video.id,
        cover_path=cover_web_path,
    )
