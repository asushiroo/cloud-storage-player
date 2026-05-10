from pathlib import Path

from app.core.config import Settings
from app.core.keys import load_content_key, load_or_create_content_key
from app.db.schema import initialize_database
from app.models.library import Video
from app.models.segments import VideoSegment
from app.services.manifests import (
    build_encrypted_manifest_filename,
    build_encrypted_segment_filename,
    build_encrypted_video_dirname,
    build_manifest_payload,
    build_remote_manifest_path,
    build_remote_segment_path,
    decrypt_manifest_payload,
    encrypt_manifest_payload,
)


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        database_path=tmp_path / "manifest-encryption.db",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
        segment_size_bytes=512,
    )
    initialize_database(settings)
    return settings


def sample_video() -> Video:
    return Video(
        id=7,
        folder_id=None,
        title="Secret Demo",
        cover_path=None,
        mime_type="video/mp4",
        size=2048,
        duration_seconds=12.5,
        manifest_path=None,
        source_path="/root/cloud-storage-player/tmp/rieri.mp4",
        created_at="2026-05-10T00:00:00+00:00",
        segment_count=1,
        tags=["secret-tag"],
    )


def sample_segments(settings: Settings, key: bytes) -> list[VideoSegment]:
    return [
        VideoSegment(
            id=1,
            video_id=7,
            segment_index=0,
            original_offset=0,
            original_length=512,
            ciphertext_size=512,
            plaintext_sha256="deadbeef",
            nonce_b64="bm9uY2U",
            tag_b64="dGFn",
            cloud_path=build_remote_segment_path(
                settings,
                video_id=7,
                segment_index=0,
                key=key,
            ),
            local_staging_path="/tmp/segments/000000.cspseg",
            created_at="2026-05-10T00:00:00+00:00",
        )
    ]


def test_remote_metadata_names_are_obfuscated_deterministically(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    key = load_or_create_content_key(settings)

    first_video_dir = build_encrypted_video_dirname(video_id=7, key=key)
    second_video_dir = build_encrypted_video_dirname(video_id=7, key=key)
    manifest_name = build_encrypted_manifest_filename(key)
    segment_name = build_encrypted_segment_filename(video_id=7, segment_index=0, key=key)

    assert first_video_dir == second_video_dir
    assert first_video_dir != "7"
    assert manifest_name != "manifest.json"
    assert segment_name != "000000.cspseg"
    assert manifest_name.endswith(".bin")
    assert segment_name.endswith(".bin")

    remote_manifest_path = build_remote_manifest_path(settings, video_id=7, key=key)
    remote_segment_path = build_remote_segment_path(settings, video_id=7, segment_index=0, key=key)
    assert "/videos/" not in remote_manifest_path
    assert "manifest.json" not in remote_manifest_path
    assert "segments" not in remote_segment_path


def test_remote_manifest_payload_is_encrypted_and_can_round_trip(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    key = load_or_create_content_key(settings)
    video = sample_video()
    segments = sample_segments(settings, key)
    payload = build_manifest_payload(settings, video=video, segments=segments)

    encrypted = encrypt_manifest_payload(payload, key=key)

    assert b"Secret Demo" not in encrypted
    assert b"rieri.mp4" not in encrypted
    assert b"secret-tag" not in encrypted
    assert b"manifest.json" not in encrypted
    assert b"segments" not in encrypted

    decrypted = decrypt_manifest_payload(encrypted, key=load_content_key(settings))
    assert decrypted["video_id"] == video.id
    assert decrypted["title"] == video.title
    assert decrypted["tags"] == ["secret-tag"]
    assert decrypted["source"]["path"] == video.source_path
    assert decrypted["segments"][0]["remote_path"] == segments[0].cloud_path
