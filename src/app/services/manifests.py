from __future__ import annotations

import hmac
import json
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.config import Settings
from app.core.keys import load_content_key
from app.media.crypto import TAG_SIZE_BYTES, decrypt_segment, encrypt_segment
from app.models.library import Video
from app.models.segments import VideoSegment
from app.services.artwork_storage import encrypted_artwork_path
from app.services.segment_local_paths import build_segment_local_staging_path
from app.services.settings import get_public_settings, get_segment_cache_root

ENCRYPTED_MANIFEST_MAGIC = b"CSPMETA1"
VIDEO_DIR_LABEL_PREFIX = "video-dir"
SEGMENT_FILE_LABEL_PREFIX = "segment-file"
MANIFEST_FILE_LABEL = "manifest-file"
POSTER_FILE_LABEL = "poster-file"


def build_remote_manifest_path(settings: Settings, *, video_id: int, key: bytes) -> str:
    remote_video_dir = build_remote_video_dir_path(settings, video_id=video_id, key=key)
    return str(PurePosixPath(remote_video_dir) / build_encrypted_manifest_filename(key))


def build_remote_video_dir_path(settings: Settings, *, video_id: int, key: bytes) -> str:
    root_path = get_public_settings(settings).baidu_root_path.rstrip("/")
    return f"{root_path}/{build_encrypted_video_dirname(video_id=video_id, key=key)}"


def build_remote_segment_path(
    settings: Settings,
    *,
    video_id: int,
    segment_index: int,
    key: bytes,
) -> str:
    remote_video_dir = build_remote_video_dir_path(settings, video_id=video_id, key=key)
    return str(
        PurePosixPath(remote_video_dir)
        / build_encrypted_segment_filename(video_id=video_id, segment_index=segment_index, key=key)
    )


def build_remote_poster_path(settings: Settings, *, video_id: int, key: bytes) -> str:
    remote_video_dir = build_remote_video_dir_path(settings, video_id=video_id, key=key)
    return str(PurePosixPath(remote_video_dir) / build_encrypted_poster_filename(video_id=video_id, key=key))


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


def write_encrypted_remote_manifest(
    settings: Settings,
    *,
    video: Video,
    segments: list[VideoSegment],
    key: bytes,
) -> Path:
    manifest_path = encrypted_remote_manifest_upload_path(settings, video_id=video.id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_manifest_payload(settings, video=video, segments=segments)
    manifest_path.write_bytes(encrypt_manifest_payload(payload, key=key))
    return manifest_path


def local_manifest_path(settings: Settings, *, video_id: int) -> Path:
    return get_segment_cache_root(settings) / str(video_id) / "manifest.json"


def encrypted_remote_manifest_upload_path(settings: Settings, *, video_id: int) -> Path:
    return get_segment_cache_root(settings) / str(video_id) / "manifest.remote.bin"


def local_segment_path(settings: Settings, *, video_id: int, segment_index: int) -> Path:
    return build_segment_local_staging_path(
        settings,
        video_id=video_id,
        segment_index=segment_index,
    )


def local_custom_poster_path(settings: Settings, *, video: Video) -> Path | None:
    if not video.has_custom_poster or not video.poster_path:
        return None
    return encrypted_artwork_path(settings, file_name=Path(video.poster_path).name)


def build_manifest_payload(
    settings: Settings,
    *,
    video: Video,
    segments: list[VideoSegment],
) -> dict[str, Any]:
    return {
        "video_id": video.id,
        "title": video.title,
        "tags": video.tags,
        "source": {
            "path": video.source_path,
            "size": video.size,
            "mime_type": video.mime_type,
            "duration_seconds": video.duration_seconds,
        },
        "content_fingerprint": video.content_fingerprint,
        "custom_poster": {
            "enabled": video.has_custom_poster and bool(video.poster_path),
            "remote_path": (
                build_remote_poster_path(settings, video_id=video.id, key=load_content_key(settings))
                if video.has_custom_poster and video.poster_path
                else None
            ),
            "file_name": Path(video.poster_path).name if video.has_custom_poster and video.poster_path else None,
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


def encrypt_manifest_payload(payload: dict[str, Any], *, key: bytes) -> bytes:
    plaintext = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encrypted = encrypt_segment(plaintext, key)
    return ENCRYPTED_MANIFEST_MAGIC + encrypted.nonce + encrypted.tag + encrypted.ciphertext


def decrypt_manifest_payload(payload: bytes, *, key: bytes | None = None) -> dict[str, Any]:
    normalized = payload.lstrip()
    if normalized.startswith(b"{"):
        return json.loads(payload.decode("utf-8"))
    if not payload.startswith(ENCRYPTED_MANIFEST_MAGIC):
        raise ValueError("Unsupported manifest payload format.")
    if key is None:
        raise ValueError("Content key is required to decrypt remote manifest metadata.")

    raw = payload[len(ENCRYPTED_MANIFEST_MAGIC) :]
    if len(raw) < 12 + TAG_SIZE_BYTES:
        raise ValueError("Encrypted manifest payload is incomplete.")
    nonce = raw[:12]
    tag = raw[12 : 12 + TAG_SIZE_BYTES]
    ciphertext = raw[12 + TAG_SIZE_BYTES :]
    plaintext = decrypt_segment(ciphertext, key, nonce=nonce, tag=tag)
    return json.loads(plaintext.decode("utf-8"))


def build_encrypted_video_dirname(*, video_id: int, key: bytes) -> str:
    return _build_obfuscated_name(key, f"{VIDEO_DIR_LABEL_PREFIX}:{video_id}")


def build_encrypted_segment_filename(*, video_id: int, segment_index: int, key: bytes) -> str:
    return _build_obfuscated_name(key, f"{SEGMENT_FILE_LABEL_PREFIX}:{video_id}:{segment_index}") + ".bin"


def build_encrypted_manifest_filename(key: bytes) -> str:
    return _build_obfuscated_name(key, MANIFEST_FILE_LABEL) + ".bin"


def build_encrypted_poster_filename(*, video_id: int, key: bytes) -> str:
    return _build_obfuscated_name(key, f"{POSTER_FILE_LABEL}:{video_id}") + ".bin"


def _build_obfuscated_name(key: bytes, label: str) -> str:
    digest = hmac.new(key, label.encode("utf-8"), sha256).hexdigest()
    return digest[:32]
