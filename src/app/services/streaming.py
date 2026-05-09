from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.media.range_map import ByteRange, RangeNotSatisfiableError, parse_range_header
from app.repositories.videos import get_video


class VideoStreamNotFoundError(FileNotFoundError):
    """Raised when the requested video or its source file is missing."""


@dataclass(slots=True)
class VideoStreamPayload:
    source_path: Path
    mime_type: str
    size: int
    byte_range: ByteRange | None


def prepare_video_stream(
    settings: Settings,
    *,
    video_id: int,
    range_header: str | None,
) -> VideoStreamPayload:
    video = get_video(settings, video_id)
    if video is None:
        raise VideoStreamNotFoundError("Video not found.")
    if not video.source_path:
        raise VideoStreamNotFoundError("Video source path is not available.")

    source_path = Path(video.source_path)
    if not source_path.exists() or not source_path.is_file():
        raise VideoStreamNotFoundError("Source file not found.")

    size = source_path.stat().st_size
    byte_range = parse_range_header(range_header, size=size)
    return VideoStreamPayload(
        source_path=source_path,
        mime_type=video.mime_type,
        size=size,
        byte_range=byte_range,
    )


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


__all__ = [
    "RangeNotSatisfiableError",
    "VideoStreamNotFoundError",
    "VideoStreamPayload",
    "iter_file_range",
    "prepare_video_stream",
]
