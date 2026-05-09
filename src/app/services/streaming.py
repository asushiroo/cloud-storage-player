from __future__ import annotations

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


class VideoStreamNotFoundError(FileNotFoundError):
    """Raised when the requested video or its source file is missing."""


@dataclass(slots=True)
class VideoStreamPayload:
    mime_type: str
    size: int
    byte_range: ByteRange | None
    source_path: Path | None = None
    segment_reads: list["PreparedSegmentRead"] | None = None
    content_key: bytes | None = None


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
    if payload.segment_reads is not None and payload.content_key is not None:
        for segment_read in payload.segment_reads:
            yield from iter_segment_slice(
                segment_read,
                key=payload.content_key,
            )
        return

    if payload.source_path is None:
        raise VideoStreamNotFoundError("Prepared stream payload has no source.")

    start = payload.byte_range.start if payload.byte_range else 0
    end = payload.byte_range.end if payload.byte_range else payload.size - 1
    yield from iter_file_range(payload.source_path, start=start, end=end)


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

    if not _segments_are_usable(segments):
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

    return VideoStreamPayload(
        mime_type=mime_type,
        size=size,
        byte_range=byte_range,
        segment_reads=prepared_reads,
        content_key=content_key,
    )


def _segments_are_usable(segments: list[VideoSegment]) -> bool:
    if not segments:
        return False

    for segment in segments:
        if not segment.local_staging_path:
            return False
        segment_path = Path(segment.local_staging_path)
        if not segment_path.exists() or not segment_path.is_file():
            return False
    return True


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


def iter_segment_slice(segment_read: PreparedSegmentRead, *, key: bytes):
    if not segment_read.segment.local_staging_path:
        raise VideoStreamNotFoundError("Segment staging path is missing.")

    segment_path = Path(segment_read.segment.local_staging_path)
    payload = segment_path.read_bytes()
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


__all__ = [
    "RangeNotSatisfiableError",
    "PreparedSegmentRead",
    "VideoStreamNotFoundError",
    "VideoStreamPayload",
    "iter_file_range",
    "iter_video_stream",
    "prepare_video_stream",
]
