from dataclasses import dataclass

from app.media.range_map import ByteRange, map_byte_range_to_segments


@dataclass(slots=True)
class SegmentStub:
    segment_index: int
    original_offset: int
    original_length: int


def test_map_byte_range_to_segments_returns_overlapping_slices() -> None:
    segments = [
        SegmentStub(segment_index=0, original_offset=0, original_length=4),
        SegmentStub(segment_index=1, original_offset=4, original_length=4),
        SegmentStub(segment_index=2, original_offset=8, original_length=4),
    ]

    slices = map_byte_range_to_segments(
        ByteRange(start=2, end=9),
        segments=segments,
    )

    assert [(item.segment_index, item.read_start, item.read_end) for item in slices] == [
        (0, 2, 3),
        (1, 0, 3),
        (2, 0, 1),
    ]
