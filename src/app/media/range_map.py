from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


class RangeNotSatisfiableError(ValueError):
    """Raised when a requested HTTP byte range cannot be served."""


@dataclass(slots=True)
class ByteRange:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


class SegmentLike(Protocol):
    segment_index: int
    original_offset: int
    original_length: int


@dataclass(slots=True)
class SegmentSlice:
    segment_index: int
    segment_offset: int
    read_start: int
    read_end: int

    @property
    def length(self) -> int:
        return self.read_end - self.read_start + 1


def parse_range_header(range_header: str | None, *, size: int) -> ByteRange | None:
    if range_header is None:
        return None

    value = range_header.strip()
    if not value.startswith("bytes="):
        raise RangeNotSatisfiableError("Only bytes ranges are supported.")

    spec = value[6:].strip()
    if "," in spec or "-" not in spec:
        raise RangeNotSatisfiableError("Multiple or malformed ranges are not supported.")

    start_token, end_token = spec.split("-", 1)
    start_token = start_token.strip()
    end_token = end_token.strip()

    if not start_token and not end_token:
        raise RangeNotSatisfiableError("Empty range is not valid.")

    if start_token:
        try:
            start = int(start_token)
        except ValueError as exc:
            raise RangeNotSatisfiableError("Range start must be an integer.") from exc
        if start < 0 or start >= size:
            raise RangeNotSatisfiableError("Range start is outside the file.")

        if end_token:
            try:
                end = int(end_token)
            except ValueError as exc:
                raise RangeNotSatisfiableError("Range end must be an integer.") from exc
            if end < start:
                raise RangeNotSatisfiableError("Range end must not be smaller than start.")
            end = min(end, size - 1)
        else:
            end = size - 1

        return ByteRange(start=start, end=end)

    try:
        suffix_length = int(end_token)
    except ValueError as exc:
        raise RangeNotSatisfiableError("Suffix range must be an integer.") from exc
    if suffix_length <= 0:
        raise RangeNotSatisfiableError("Suffix range must be greater than zero.")

    if suffix_length >= size:
        return ByteRange(start=0, end=size - 1)

    return ByteRange(start=size - suffix_length, end=size - 1)


def map_byte_range_to_segments(
    byte_range: ByteRange,
    *,
    segments: Sequence[SegmentLike],
) -> list[SegmentSlice]:
    slices: list[SegmentSlice] = []
    for segment in segments:
        segment_start = segment.original_offset
        segment_end = segment.original_offset + segment.original_length - 1
        if segment_end < byte_range.start or segment_start > byte_range.end:
            continue

        read_start = max(byte_range.start, segment_start) - segment_start
        read_end = min(byte_range.end, segment_end) - segment_start
        slices.append(
            SegmentSlice(
                segment_index=segment.segment_index,
                segment_offset=segment.original_offset,
                read_start=read_start,
                read_end=read_end,
            )
        )

    if not slices:
        raise RangeNotSatisfiableError("Requested range did not match any stored segment.")

    return slices
