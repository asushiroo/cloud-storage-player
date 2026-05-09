from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.models.library import Video
from app.models.segments import VideoSegment
from app.services.settings import get_public_settings


def build_remote_manifest_path(settings: Settings, *, video_id: int) -> str:
    root_path = get_public_settings(settings).baidu_root_path.rstrip("/")
    return f"{root_path}/videos/{video_id}/manifest.json"


def build_remote_segment_path(settings: Settings, *, video_id: int, segment_index: int) -> str:
    root_path = get_public_settings(settings).baidu_root_path.rstrip("/")
    return f"{root_path}/videos/{video_id}/segments/{segment_index:06d}.cspseg"


def write_local_manifest(
    settings: Settings,
    *,
    video: Video,
    segments: list[VideoSegment],
) -> Path:
    manifest_path = local_manifest_path(settings, video_id=video.id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_manifest_payload(settings, video=video, segments=segments)
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def local_manifest_path(settings: Settings, *, video_id: int) -> Path:
    return settings.segment_staging_dir / str(video_id) / "manifest.json"


def build_manifest_payload(
    settings: Settings,
    *,
    video: Video,
    segments: list[VideoSegment],
) -> dict[str, Any]:
    return {
        "video_id": video.id,
        "title": video.title,
        "source": {
            "path": video.source_path,
            "size": video.size,
            "mime_type": video.mime_type,
            "duration_seconds": video.duration_seconds,
        },
        "segment_size_bytes": settings.segment_size_bytes,
        "segment_count": len(segments),
        "original_size": video.size,
        "mime_type": video.mime_type,
        "encryption": {
            "algorithm": "AES-256-GCM",
            "version": 1,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "segments": [
            {
                "index": segment.segment_index,
                "original_offset": segment.original_offset,
                "original_length": segment.original_length,
                "ciphertext_size": segment.ciphertext_size,
                "plaintext_sha256": segment.plaintext_sha256,
                "remote_path": segment.cloud_path,
                "local_staging_path": segment.local_staging_path,
                "nonce_b64": segment.nonce_b64,
                "tag_b64": segment.tag_b64,
            }
            for segment in segments
        ],
    }
