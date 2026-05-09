from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(slots=True)
class FileChunk:
    index: int
    original_offset: int
    payload: bytes

    @property
    def original_length(self) -> int:
        return len(self.payload)


def iter_file_chunks(source_path: Path, *, segment_size: int) -> Iterator[FileChunk]:
    if segment_size <= 0:
        raise ValueError("segment_size must be greater than 0.")

    with source_path.open("rb") as file_handle:
        index = 0
        offset = 0
        while True:
            payload = file_handle.read(segment_size)
            if not payload:
                break
            yield FileChunk(
                index=index,
                original_offset=offset,
                payload=payload,
            )
            index += 1
            offset += len(payload)
