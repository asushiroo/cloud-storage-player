from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from app.core.config import Settings
from app.core.keys import load_content_key, load_or_create_content_key
from app.core.tags import normalize_tags
from app.media.chunker import iter_file_chunks
from app.media.covers import CoverExtractionError, extract_poster_at_ratio
from app.media.crypto import encrypt_segment
from app.media.probe import MediaProbeError, probe_video
from app.models.imports import ImportJob
from app.models.library import Video
from app.models.segments import VideoSegment
from app.repositories.import_jobs import (
    create_import_job,
    get_import_job,
    mark_import_job_cancelled,
    mark_import_job_completed,
    mark_import_job_failed,
    mark_import_job_running,
    update_import_job_progress,
)
from app.repositories.video_segments import NewVideoSegment, create_video_segments
from app.repositories.videos import (
    create_video,
    get_video_by_content_fingerprint,
    update_video_artwork_paths,
    update_video_fields,
    update_video_manifest_path,
)
from app.services.job_control import JobCancelledError, throw_if_cancel_requested
from app.services.manifests import (
    build_remote_manifest_path,
    build_remote_segment_path,
    local_segment_path,
    write_encrypted_remote_manifest,
    write_local_manifest,
)
from app.services.segment_local_paths import resolve_segment_local_staging_path, serialize_local_staging_path
from app.services.remote_transfers import (
    DeferredTransferRetry,
    TransferResult,
    measure_transfer,
    run_bounded_transfers,
)
from app.services.artwork_storage import build_poster_file_name, store_encrypted_artwork_file
from app.services.cache_eviction import enforce_cache_limit
from app.services.cache import refresh_video_cache_entry
from app.services.settings import get_upload_transfer_concurrency
from app.services.video_fingerprint import build_video_content_fingerprint
from app.services.video_delete import delete_library_video
from app.storage.factory import build_storage_backend
from app.storage.baidu_api import BaiduFrequencyControlError

VIDEO_FILE_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".ts",
    ".m2ts",
}


class ImportValidationError(ValueError):
    """Raised when the import request is invalid."""


def queue_import_job(
    settings: Settings,
    *,
    source_path: str,
    title: str | None = None,
    tags: list[str] | None = None,
    worker: "ImportWorker",
) -> ImportJob:
    source, requested_title, normalized_tags = validate_import_request(
        settings,
        source_path=source_path,
        title=title,
        tags=tags,
    )
    job = create_import_job(
        settings,
        source_path=str(source),
        requested_title=requested_title,
        requested_tags=normalized_tags,
        task_name=requested_title or source.stem,
    )
    worker.enqueue(job.id)
    return job


def import_local_video(
    settings: Settings,
    *,
    source_path: str,
    title: str | None = None,
    tags: list[str] | None = None,
) -> ImportJob:
    source, requested_title, normalized_tags = validate_import_request(
        settings,
        source_path=source_path,
        title=title,
        tags=tags,
    )
    job = create_import_job(
        settings,
        source_path=str(source),
        requested_title=requested_title,
        requested_tags=normalized_tags,
        task_name=requested_title or source.stem,
    )
    return process_import_job(settings, job.id)


def process_import_job(settings: Settings, job_id: int) -> ImportJob:
    job = get_import_job(settings, job_id)
    if job is None:
        raise ImportValidationError(f"Import job does not exist: {job_id}")
    if job.status in {"completed", "failed", "cancelled"}:
        return job

    try:
        source, requested_title, requested_tags = validate_import_request(
            settings,
            source_path=job.source_path,
            title=job.requested_title,
            tags=job.requested_tags,
        )
    except ImportValidationError as exc:
        return mark_import_job_failed(settings, job.id, error_message=str(exc))

    video: Video | None = None
    mark_import_job_running(settings, job.id)

    try:
        throw_if_cancel_requested(settings, job.id)
        metadata = probe_video(source, ffprobe_binary=settings.ffprobe_binary)
        video = _create_video_from_probe(
            settings,
            title=requested_title or source.stem,
            source_path=str(source),
            mime_type=metadata.mime_type,
            size=metadata.size,
            duration_seconds=metadata.duration_seconds,
            tags=requested_tags,
        )
        throw_if_cancel_requested(settings, job.id)
        update_import_job_progress(settings, job.id, progress_percent=40)
        segments = _materialize_encrypted_segments(settings, source=source, video=video, job_id=job.id)
        content_fingerprint = build_video_content_fingerprint(segments, size=metadata.size)
        duplicate_video = get_video_by_content_fingerprint(settings, content_fingerprint)
        if duplicate_video is not None and duplicate_video.id != video.id:
            raise ImportValidationError(f"Duplicate video content already exists: {duplicate_video.title}")
        video = update_video_fields(
            settings,
            video.id,
            title=video.title,
            tags=video.tags,
            content_fingerprint=content_fingerprint,
        )
        throw_if_cancel_requested(settings, job.id)
        update_import_job_progress(settings, job.id, progress_percent=70)
        video, remote_manifest_upload_path = _write_manifest(settings, video=video, segments=segments)
        throw_if_cancel_requested(settings, job.id)
        update_import_job_progress(settings, job.id, progress_percent=85)
        _upload_remote_artifacts(
            settings,
            video=video,
            segments=segments,
            manifest_path=remote_manifest_upload_path,
            job_id=job.id,
        )
        throw_if_cancel_requested(settings, job.id)
        update_import_job_progress(settings, job.id, progress_percent=95)
        video = _maybe_extract_cover(
            settings,
            source=source,
            video=video,
            duration_seconds=metadata.duration_seconds,
        )
        refresh_video_cache_entry(settings, video_id=video.id)
        _enforce_post_import_cache_limit(settings, current_video_id=video.id)
        throw_if_cancel_requested(settings, job.id)
    except JobCancelledError as exc:
        if video is not None:
            try:
                delete_library_video(settings, video.id)
            except Exception:
                pass
        return mark_import_job_cancelled(settings, job.id, error_message=str(exc))
    except MediaProbeError as exc:
        if video is not None:
            try:
                delete_library_video(settings, video.id)
            except Exception:
                pass
        return mark_import_job_failed(settings, job.id, error_message=str(exc))
    except Exception as exc:
        if video is not None:
            try:
                delete_library_video(settings, video.id)
            except Exception:
                pass
        return mark_import_job_failed(settings, job.id, error_message=str(exc))

    return mark_import_job_completed(settings, job.id, video_id=video.id)


def validate_import_request(
    settings: Settings,
    *,
    source_path: str,
    title: str | None = None,
    tags: list[str] | None = None,
) -> tuple[Path, str | None, list[str]]:
    source = Path(source_path)
    if not source.exists() or not source.is_file():
        raise ImportValidationError(f"Source file does not exist: {source_path}")

    requested_title = title.strip() if title else None
    return source, requested_title, normalize_tags(tags)


def discover_video_files(source_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in source_dir.rglob("*")
            if path.is_file() and path.suffix.casefold() in VIDEO_FILE_EXTENSIONS
        ],
        key=lambda path: str(path).casefold(),
    )


def _create_video_from_probe(
    settings: Settings,
    *,
    title: str,
    source_path: str,
    mime_type: str,
    size: int,
    duration_seconds: float | None,
    tags: list[str],
) -> Video:
    return create_video(
        settings,
        title=title,
        mime_type=mime_type,
        size=size,
        duration_seconds=duration_seconds,
        manifest_path=None,
        source_path=source_path,
        tags=tags,
        content_fingerprint=None,
    )


def _maybe_extract_cover(
    settings: Settings,
    *,
    source: Path,
    video: Video,
    duration_seconds: float | None,
) -> Video:
    poster_file_name = build_poster_file_name(video.id)
    try:
        with TemporaryDirectory() as temp_dir_name:
            poster_output_path = Path(temp_dir_name) / poster_file_name
            extract_poster_at_ratio(
                source,
                poster_output_path,
                duration_seconds=duration_seconds,
                position_ratio=1 / 3,
                ffmpeg_binary=settings.ffmpeg_binary,
            )
            poster_web_path = store_encrypted_artwork_file(
                settings,
                file_name=poster_file_name,
                source_path=poster_output_path,
            )
    except CoverExtractionError:
        return video

    return update_video_artwork_paths(
        settings,
        video.id,
        cover_path=None,
        poster_path=poster_web_path,
    )


def _materialize_encrypted_segments(
    settings: Settings,
    *,
    source: Path,
    video: Video,
    job_id: int,
) -> list[VideoSegment]:
    content_key = load_or_create_content_key(settings)
    video_segment_dir = local_segment_path(
        settings,
        video_id=video.id,
        segment_index=0,
    ).parent
    video_segment_dir.mkdir(parents=True, exist_ok=True)

    segments_to_insert: list[NewVideoSegment] = []
    for chunk in iter_file_chunks(source, segment_size=settings.segment_size_bytes):
        throw_if_cancel_requested(settings, job_id)
        encrypted = encrypt_segment(chunk.payload, content_key)
        segment_path = local_segment_path(settings, video_id=video.id, segment_index=chunk.index)
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
                    key=content_key,
                ),
                local_staging_path=serialize_local_staging_path(settings, segment_path),
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
) -> tuple[Video, Path]:
    content_key = load_content_key(settings)
    remote_manifest_path = build_remote_manifest_path(settings, video_id=video.id, key=content_key)
    write_local_manifest(
        settings,
        video=video,
        segments=segments,
    )
    remote_manifest_upload_path = write_encrypted_remote_manifest(
        settings,
        video=video,
        segments=segments,
        key=content_key,
    )
    updated_video = update_video_manifest_path(
        settings,
        video.id,
        manifest_path=remote_manifest_path,
    )
    return updated_video, remote_manifest_upload_path


def _upload_remote_artifacts(
    settings: Settings,
    *,
    video: Video,
    segments: list[VideoSegment],
    manifest_path: Path,
    job_id: int,
) -> None:
    storage = build_storage_backend(settings)
    remote_artifacts: list[_UploadArtifact] = []
    for segment in segments:
        if not segment.local_staging_path:
            raise ValueError("Segment staging path is missing.")
        if not segment.cloud_path:
            raise ValueError("Segment cloud path is missing.")
        local_path = resolve_segment_local_staging_path(
            settings,
            video_id=segment.video_id,
            segment_index=segment.segment_index,
            local_staging_path=segment.local_staging_path,
        )
        remote_artifacts.append(
            _UploadArtifact(
                local_path=local_path,
                remote_path=segment.cloud_path,
                video_id=segment.video_id,
                segment_index=segment.segment_index,
                progress_percent=None,
            )
        )

    if not video.manifest_path:
        raise ValueError("Video manifest path is missing.")
    manifest_artifact = _UploadArtifact(
        local_path=manifest_path,
        remote_path=video.manifest_path,
        video_id=video.id,
        segment_index=None,
        progress_percent=95,
    )

    try:
        completed_segment_count = 0

        def upload_artifact(task: _UploadArtifact) -> TransferResult[_UploadArtifact]:
            expected_size = task.local_path.stat().st_size
            if _remote_artifact_matches_size(storage, task, expected_size=expected_size):
                return measure_transfer(
                    task,
                    byte_count=0,
                    started_at=perf_counter(),
                )
            started_at = perf_counter()
            storage.upload_file(task.local_path, task.remote_path)
            _assert_remote_artifact_uploaded(storage, task, expected_size=expected_size)
            return measure_transfer(
                task,
                byte_count=expected_size,
                started_at=started_at,
            )

        def on_result(result: TransferResult[_UploadArtifact], _completed: int, _total: int) -> None:
            nonlocal completed_segment_count
            if result.task.progress_percent is not None:
                update_import_job_progress(settings, job_id, progress_percent=result.task.progress_percent)
                return
            completed_segment_count += 1
            progress_span = 95 - 85
            if segments:
                progress_percent = 85 + int((completed_segment_count / len(segments)) * progress_span)
            else:
                progress_percent = 95
            update_import_job_progress(settings, job_id, progress_percent=min(94, max(85, progress_percent)))

        def on_exception(
            task: _UploadArtifact,
            exc: Exception,
        ) -> DeferredTransferRetry[_UploadArtifact] | None:
            if not isinstance(exc, BaiduFrequencyControlError):
                return None
            return DeferredTransferRetry(
                task=task,
                wait_seconds=float(settings.baidu_upload_resume_poll_interval_seconds),
            )

        if remote_artifacts:
            run_bounded_transfers(
                settings,
                job_id=job_id,
                tasks=remote_artifacts,
                transfer_func=upload_artifact,
                concurrency=get_upload_transfer_concurrency(settings),
                on_result=on_result,
                on_exception=on_exception,
            )

        manifest_result = upload_artifact(manifest_artifact)
        update_import_job_progress(settings, job_id, progress_percent=manifest_artifact.progress_percent or 95)
        from app.repositories.import_jobs import record_import_job_transfer

        record_import_job_transfer(
            settings,
            job_id,
            byte_count=manifest_result.byte_count,
            elapsed_seconds=manifest_result.elapsed_seconds,
        )
    finally:
        close = getattr(storage, "close", None)
        if callable(close):
            close()


class _UploadArtifact:
    __slots__ = ("local_path", "remote_path", "video_id", "segment_index", "progress_percent")

    def __init__(
        self,
        *,
        local_path: Path,
        remote_path: str,
        video_id: int,
        segment_index: int | None,
        progress_percent: int | None,
    ) -> None:
        self.local_path = local_path
        self.remote_path = remote_path
        self.video_id = video_id
        self.segment_index = segment_index
        self.progress_percent = progress_percent


def _remote_artifact_matches_size(storage, task: _UploadArtifact, *, expected_size: int) -> bool:
    if task.progress_percent is not None:
        return False
    local_path_for = getattr(storage, "local_path_for", None)
    if not callable(local_path_for):
        get_file_size = getattr(storage, "get_file_size", None)
        if not callable(get_file_size):
            return False
        try:
            remote_size = get_file_size(task.remote_path)
        except Exception:
            return False
        return remote_size is not None and int(remote_size) == expected_size
    try:
        remote_path = local_path_for(task.remote_path)
    except Exception:
        return False
    return remote_path.exists() and remote_path.is_file() and remote_path.stat().st_size == expected_size


def _assert_remote_artifact_uploaded(storage, task: _UploadArtifact, *, expected_size: int) -> None:
    local_path_for = getattr(storage, "local_path_for", None)
    if callable(local_path_for):
        remote_path = local_path_for(task.remote_path)
        if not remote_path.exists() or not remote_path.is_file():
            raise ValueError(f"Uploaded artifact is missing on remote: {task.remote_path}")
        if remote_path.stat().st_size != expected_size:
            raise ValueError(
                "Uploaded artifact size mismatch: "
                f"video_id={task.video_id}, segment_index={task.segment_index}, "
                f"expected={expected_size}, actual={remote_path.stat().st_size}, remote_path={task.remote_path}"
            )
        return
    get_file_size = getattr(storage, "get_file_size", None)
    if callable(get_file_size):
        remote_size = get_file_size(task.remote_path)
        if remote_size is None:
            raise ValueError(f"Uploaded artifact is missing on remote: {task.remote_path}")
        if int(remote_size) != expected_size:
            raise ValueError(
                "Uploaded artifact size mismatch: "
                f"video_id={task.video_id}, segment_index={task.segment_index}, "
                f"expected={expected_size}, actual={remote_size}, remote_path={task.remote_path}"
            )
        return
    if not storage.exists(task.remote_path):
        raise ValueError(f"Uploaded artifact is missing on remote: {task.remote_path}")


def _enforce_post_import_cache_limit(settings: Settings, *, current_video_id: int) -> None:
    enforce_cache_limit(
        settings,
        protect_video_ids={current_video_id},
    )
