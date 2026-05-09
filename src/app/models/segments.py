from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VideoSegment:
    id: int
    video_id: int
    segment_index: int
    original_offset: int
    original_length: int
    ciphertext_size: int
    plaintext_sha256: str
    nonce_b64: str
    tag_b64: str
    cloud_path: str | None
    local_staging_path: str | None
    created_at: str
