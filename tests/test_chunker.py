from pathlib import Path

from app.media.chunker import iter_file_chunks


def test_iter_file_chunks_splits_file_by_fixed_segment_size(tmp_path: Path) -> None:
    source_path = tmp_path / "payload.bin"
    source_path.write_bytes(b"abcdefghij")

    chunks = list(iter_file_chunks(source_path, segment_size=4))

    assert [chunk.index for chunk in chunks] == [0, 1, 2]
    assert [chunk.original_offset for chunk in chunks] == [0, 4, 8]
    assert [chunk.payload for chunk in chunks] == [b"abcd", b"efgh", b"ij"]


def test_iter_file_chunks_rejects_non_positive_segment_size(tmp_path: Path) -> None:
    source_path = tmp_path / "payload.bin"
    source_path.write_bytes(b"abc")

    try:
        list(iter_file_chunks(source_path, segment_size=0))
    except ValueError as exc:
        assert str(exc) == "segment_size must be greater than 0."
    else:
        raise AssertionError("Expected ValueError for invalid segment size.")
