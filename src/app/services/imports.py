from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.core.keys import load_or_create_content_key
from app.media.chunker import iter_file_chunks
from app.media.covers import CoverExtractionError, extract_cover
from app.media.crypto import encrypt_segment
from app.media.probe import MediaProbeError, probe_video
from app.models.imports import ImportJob
from app.models.library import Video
from app.models.segments import VideoSegment
from app.repositories.folders import get_folder
from app.repositories.import_jobs import (
    create_import_job,
    mark_import_job_completed,
    mark_import_job_failed,
    mark_import_job_running,
    update_import_job_progress,
)
from app.repositories.video_segments import NewVideoSegment, create_video_segments
from app.repositories.videos import (
    create_video,
    update_video_cover_path,
    update_video_manifest_path,
)
from app.services.manifests import (
    build_remote_manifest_path,
    build_remote_segment_path,
    write_local_manifest,
)


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
        update_import_job_progress(settings, job.id, progress_percent=40)
        segments = _materialize_encrypted_segments(settings, source=source, video=video)
        update_import_job_progress(settings, job.id, progress_percent=70)
        video = _write_manifest(settings, video=video, segments=segments)
        update_import_job_progress(settings, job.id, progress_percent=85)
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


def _materialize_encrypted_segments(
    settings: Settings,
    *,
    source: Path,
    video: Video,
) -> list[VideoSegment]:
    content_key = load_or_create_content_key(settings)
    video_stage_dir = settings.segment_staging_dir / str(video.id)
    video_segment_dir = video_stage_dir / "segments"
    video_segment_dir.mkdir(parents=True, exist_ok=True)

    segments_to_insert: list[NewVideoSegment] = []
    for chunk in iter_file_chunks(source, segment_size=settings.segment_size_bytes):
        encrypted = encrypt_segment(chunk.payload, content_key)
        segment_path = video_segment_dir / f"{chunk.index:06d}.cspseg"
        segment_path.write_bytes(encrypted.ciphertext + encrypted.tag)
        segments_to_insert.append(
            NewVideoSegment(
                segment_index=chunk.index,
                original_offset=chunk.original_offset,
                original_length=chunk.original_length,
                ciphertext_size=encrypted.ciphertext_size,
                plaintext_sha256=encrypted.plaintext_sha256,
                nonce_b64=encrypted.nonce_b64,
                tag_b64=encrypted.tag_b64,
                cloud_path=build_remote_segment_path(
                    settings,
                    video_id=video.id,
                    segment_index=chunk.index,
                ),
                local_staging_path=str(segment_path),
            )
        )

    return create_video_segments(
        settings,
        video_id=video.id,
        segments=segments_to_insert,
    )


def _write_manifest(
    settings: Settings,
    *,
    video: Video,
    segments: list[VideoSegment],
) -> Video:
    remote_manifest_path = build_remote_manifest_path(settings, video_id=video.id)
    write_local_manifest(
        settings,
        video=video,
        segments=segments,
    )
    return update_video_manifest_path(
        settings,
        video.id,
        manifest_path=remote_manifest_path,
    )
