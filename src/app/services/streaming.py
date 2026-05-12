from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.keys import load_content_key
from app.media.crypto import TAG_SIZE_BYTES, decode_token, decrypt_segment
from app.media.range_map import (
    ByteRange,
    RangeNotSatisfiableError,
    map_byte_range_to_segments,
    parse_range_header,
)
from app.models.segments import VideoSegment
from app.repositories.video_segments import list_video_segments
from app.repositories.videos import get_video
from app.services.segment_prefetch import (
    acquire_prefetch_session,
    download_remote_segment_payload,
    persist_segment_payload,
    queue_segment_cache_write,
    release_prefetch_session,
)
from app.storage.baidu_api import BaiduApiError
from app.storage.base import StorageBackend
from app.storage.factory import build_storage_backend
from app.services.manifests import local_segment_path

logger = logging.getLogger(__name__)


class VideoStreamNotFoundError(FileNotFoundError):
    """Raised when the requested video or its source file is missing."""


@dataclass(slots=True)
class VideoStreamPayload:
    mime_type: str
    size: int
    byte_range: ByteRange | None
    settings: Settings | None = None
    source_path: Path | None = None
    segment_reads: list["PreparedSegmentRead"] | None = None
    content_key: bytes | None = None
    storage_backend: StorageBackend | None = None
    prefetch_session: object | None = None
    prefetched_remote_payloads: dict[int, bytes] | None = None


@dataclass(slots=True)
class PreparedSegmentRead:
    segment: VideoSegment
    read_start: int
    read_end: int

    @property
    def length(self) -> int:
        return self.read_end - self.read_start + 1


def prepare_video_stream(
    settings: Settings,
    *,
    video_id: int,
    range_header: str | None,
) -> VideoStreamPayload:
    video = get_video(settings, video_id)
    if video is None:
        raise VideoStreamNotFoundError("Video not found.")
    size = video.size
    byte_range = parse_range_header(range_header, size=size)
    effective_range = byte_range or ByteRange(start=0, end=size - 1)

    segments = list_video_segments(settings, video_id=video_id)
    if segments:
        segment_payload = _prepare_segment_stream(
            settings,
            size=size,
            mime_type=video.mime_type,
            byte_range=byte_range,
            effective_range=effective_range,
            segments=segments,
        )
        if segment_payload is not None:
            return segment_payload

    if not video.source_path:
        raise VideoStreamNotFoundError("Video source path is not available.")

    source_path = Path(video.source_path)
    if not source_path.exists() or not source_path.is_file():
        raise VideoStreamNotFoundError("Source file not found.")

    return VideoStreamPayload(
        mime_type=video.mime_type,
        size=size,
        byte_range=byte_range,
        source_path=source_path,
    )


def iter_video_stream(payload: VideoStreamPayload):
    try:
        if payload.segment_reads is not None and payload.content_key is not None:
            for segment_read in payload.segment_reads:
                try:
                    yield from iter_segment_slice(
                        segment_read,
                        key=payload.content_key,
                        settings=payload.settings,
                        storage_backend=payload.storage_backend,
                        prefetched_remote_payloads=payload.prefetched_remote_payloads,
                    )
                except VideoStreamNotFoundError:
                    return
                if payload.prefetch_session is not None:
                    payload.prefetch_session.request_prefetch(
                        current_segment_index=segment_read.segment.segment_index
                    )
            return

        if payload.source_path is None:
            raise VideoStreamNotFoundError("Prepared stream payload has no source.")

        start = payload.byte_range.start if payload.byte_range else 0
        end = payload.byte_range.end if payload.byte_range else payload.size - 1
        yield from iter_file_range(payload.source_path, start=start, end=end)
    finally:
        if payload.segment_reads and payload.prefetch_session is not None:
            first_segment = payload.segment_reads[0].segment
            release_prefetch_session(first_segment.video_id)
        close = getattr(payload.storage_backend, "close", None)
        if callable(close):
            close()


def _prepare_segment_stream(
    settings: Settings,
    *,
    size: int,
    mime_type: str,
    byte_range: ByteRange | None,
    effective_range: ByteRange,
    segments: list[VideoSegment],
) -> VideoStreamPayload | None:
    try:
        content_key = load_content_key(settings)
    except (FileNotFoundError, ValueError):
        return None

    segment_slices = map_byte_range_to_segments(
        effective_range,
        segments=segments,
    )
    segment_by_index = {segment.segment_index: segment for segment in segments}
    prepared_reads = [
        PreparedSegmentRead(
            segment=segment_by_index[segment_slice.segment_index],
            read_start=segment_slice.read_start,
            read_end=segment_slice.read_end,
        )
        for segment_slice in segment_slices
    ]

    if not all(_segment_is_addressable(settings, segment_read.segment) for segment_read in prepared_reads):
        return None

    storage_backend = _build_storage_backend_if_needed(settings, prepared_reads)
    if storage_backend is False:
        return None

    first_segment = prepared_reads[0].segment
    prefetched_payload = None
    if not _local_segment_exists(settings, first_segment):
        if not first_segment.cloud_path:
            return None
        if storage_backend is None:
            return None
        try:
            prefetched_payload = _read_segment_payload(
                first_segment,
                settings=settings,
                storage_backend=storage_backend,
                required=True,
                queue_cache_write=True,
            )
        except (FileNotFoundError, NotImplementedError, RuntimeError, ValueError) as exc:
            raise VideoStreamNotFoundError("Encrypted segment file is missing.") from exc

    return VideoStreamPayload(
        mime_type=mime_type,
        size=size,
        byte_range=byte_range,
        settings=settings,
        segment_reads=prepared_reads,
        content_key=content_key,
        storage_backend=storage_backend or None,
        prefetched_remote_payloads=(
            {first_segment.id: prefetched_payload}
            if prefetched_payload is not None
            else None
        ),
        prefetch_session=acquire_prefetch_session(
            settings,
            video_id=prepared_reads[0].segment.video_id,
            segments=segments,
            storage_backend_factory=(lambda: build_storage_backend(settings)),
        ),
    )


def _build_storage_backend_if_needed(
    settings: Settings,
    segment_reads: list[PreparedSegmentRead],
) -> StorageBackend | bool | None:
    missing_local_segments = [
        segment_read.segment
        for segment_read in segment_reads
        if not _local_segment_exists(settings, segment_read.segment)
    ]
    if not missing_local_segments:
        return None

    try:
        storage_backend = build_storage_backend(settings)
    except (NotImplementedError, RuntimeError, ValueError):
        return False

    return storage_backend


def _segment_is_addressable(settings: Settings, segment: VideoSegment) -> bool:
    return _local_segment_exists(settings, segment) or bool(segment.cloud_path)


def _local_segment_exists(settings: Settings, segment: VideoSegment) -> bool:
    segment_path = _segment_cache_path(segment, settings=settings)
    return segment_path.exists() and segment_path.is_file()


def iter_file_range(
    source_path: Path,
    *,
    start: int,
    end: int,
    chunk_size: int = 64 * 1024,
):
    with source_path.open("rb") as file_handle:
        file_handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = file_handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def iter_segment_slice(
    segment_read: PreparedSegmentRead,
    *,
    key: bytes,
    settings: Settings | None,
    storage_backend: StorageBackend | None = None,
    prefetched_remote_payloads: dict[int, bytes] | None = None,
):
    prefetched_payload = None
    if prefetched_remote_payloads is not None:
        prefetched_payload = prefetched_remote_payloads.pop(segment_read.segment.id, None)
    payload = _read_segment_payload(
        segment_read.segment,
        settings=settings,
        storage_backend=storage_backend,
        prefetched_payload=prefetched_payload,
    )
    if payload is None:
        return
    if len(payload) < TAG_SIZE_BYTES:
        raise VideoStreamNotFoundError("Encrypted segment file is incomplete.")

    ciphertext = payload[:-TAG_SIZE_BYTES]
    plaintext = decrypt_segment(
        ciphertext,
        key,
        nonce=decode_token(segment_read.segment.nonce_b64),
        tag=decode_token(segment_read.segment.tag_b64),
    )
    yield plaintext[segment_read.read_start : segment_read.read_end + 1]


def _read_segment_payload(
    segment: VideoSegment,
    *,
    settings: Settings | None,
    storage_backend: StorageBackend | None,
    required: bool = False,
    prefetched_payload: bytes | None = None,
    queue_cache_write: bool = True,
) -> bytes | None:
    if settings is not None:
        segment_path = _segment_cache_path(segment, settings=settings)
        if segment_path.exists() and segment_path.is_file():
            return segment_path.read_bytes()

    if prefetched_payload is not None:
        if queue_cache_write and settings is not None:
            # The current response segment should be immediately available for reuse.
            if required:
                persist_segment_payload(settings, segment, prefetched_payload)
            else:
                queue_segment_cache_write(settings, segment, prefetched_payload)
        return prefetched_payload

    if storage_backend is not None and segment.cloud_path and settings is not None:
        try:
            downloaded = download_remote_segment_payload(
                settings,
                segment,
                storage_backend=storage_backend,
            )
            if queue_cache_write:
                if required:
                    persist_segment_payload(settings, segment, downloaded.payload)
                else:
                    queue_segment_cache_write(settings, segment, downloaded.payload)
            return downloaded.payload
        except BaiduApiError as exc:
            logger.warning(
                "Failed to fetch encrypted segment from Baidu remote storage: %s",
                exc,
            )
            if required:
                raise VideoStreamNotFoundError("Encrypted segment file is missing.") from exc
            return None
        except (FileNotFoundError, NotImplementedError, RuntimeError, ValueError) as exc:
            raise VideoStreamNotFoundError("Encrypted segment file is missing.") from exc

    raise VideoStreamNotFoundError("Encrypted segment file is missing.")


def _segment_cache_path(
    segment: VideoSegment,
    *,
    settings: Settings,
) -> Path:
    if segment.local_staging_path:
        return Path(segment.local_staging_path)
    return local_segment_path(
        settings,
        video_id=segment.video_id,
        segment_index=segment.segment_index,
    )


__all__ = [
    "RangeNotSatisfiableError",
    "PreparedSegmentRead",
    "VideoStreamNotFoundError",
    "VideoStreamPayload",
    "iter_file_range",
    "iter_video_stream",
    "prepare_video_stream",
]
