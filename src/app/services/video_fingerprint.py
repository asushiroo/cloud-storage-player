from __future__ import annotations

import hashlib

from app.models.segments import VideoSegment


def build_video_content_fingerprint(segments: list[VideoSegment], *, size: int) -> str:
    digest = hashlib.sha256()
    digest.update(str(size).encode("ascii"))
    digest.update(b":")
    for segment in segments:
        digest.update(segment.plaintext_sha256.encode("ascii"))
        digest.update(b":")
        digest.update(str(segment.original_length).encode("ascii"))
        digest.update(b";")
    return digest.hexdigest()
