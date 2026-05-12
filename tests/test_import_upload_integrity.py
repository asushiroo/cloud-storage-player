from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.repositories.import_jobs import create_import_job
from app.repositories.video_segments import NewVideoSegment, create_video_segments, list_video_segments
from app.repositories.videos import create_video
from app.services.imports import _upload_remote_artifacts
from app.services.manifests import encrypted_remote_manifest_upload_path


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "upload-integrity.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
    )
    initialize_database(settings)
    return settings


def test_upload_replaces_remote_segment_when_size_mismatch(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    job = create_import_job(settings, source_path=str(tmp_path / "demo.mp4"))
    video = create_video(
        settings,
        title="Upload Integrity",
        mime_type="video/mp4",
        size=128,
        source_path=str(tmp_path / "demo.mp4"),
        manifest_path="/apps/CloudStoragePlayer/mock/video-1/manifest.bin",
    )

    segment_path = settings.segment_staging_dir / str(video.id) / "segments" / "000000.cspseg"
    segment_path.parent.mkdir(parents=True, exist_ok=True)
    segment_path.write_bytes(b"expected-segment-payload")
    manifest_path = encrypted_remote_manifest_upload_path(settings, video_id=video.id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(b"manifest-payload-v2")

    remote_segment_path = "/apps/CloudStoragePlayer/mock/video-1/seg-0.bin"
    create_video_segments(
        settings,
        video_id=video.id,
        segments=[
            NewVideoSegment(
                segment_index=0,
                original_offset=0,
                original_length=128,
                ciphertext_size=segment_path.stat().st_size,
                plaintext_sha256="sha",
                nonce_b64="nonce",
                tag_b64="tag",
                cloud_path=remote_segment_path,
                local_staging_path=f"{video.id}/segments/000000.cspseg",
            )
        ],
    )

    from app.storage.mock import MockStorageBackend

    segments = list_video_segments(settings, video_id=video.id)
    storage = MockStorageBackend(settings.mock_storage_dir)

    # Pre-populate wrong-sized remote artifact to simulate interrupted upload.
    storage.upload_bytes(b"wrong", remote_segment_path)
    storage.upload_bytes(b"manifest-payload-v1", video.manifest_path or "")

    _upload_remote_artifacts(
        settings,
        video=video,
        segments=segments,
        manifest_path=manifest_path,
        job_id=job.id,
    )

    assert storage.download_bytes(remote_segment_path) == b"expected-segment-payload"
    assert storage.download_bytes(video.manifest_path or "") == b"manifest-payload-v2"


def test_upload_skips_segment_when_remote_size_already_matches(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    job = create_import_job(settings, source_path=str(tmp_path / "demo.mp4"))
    video = create_video(
        settings,
        title="Upload Skip",
        mime_type="video/mp4",
        size=128,
        source_path=str(tmp_path / "demo.mp4"),
        manifest_path="/apps/CloudStoragePlayer/mock/video-2/manifest.bin",
    )

    segment_path = settings.segment_staging_dir / str(video.id) / "segments" / "000000.cspseg"
    segment_path.parent.mkdir(parents=True, exist_ok=True)
    segment_path.write_bytes(b"segment-payload")
    manifest_path = encrypted_remote_manifest_upload_path(settings, video_id=video.id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(b"manifest-payload-v2")

    remote_segment_path = "/apps/CloudStoragePlayer/mock/video-2/seg-0.bin"
    create_video_segments(
        settings,
        video_id=video.id,
        segments=[
            NewVideoSegment(
                segment_index=0,
                original_offset=0,
                original_length=128,
                ciphertext_size=segment_path.stat().st_size,
                plaintext_sha256="sha",
                nonce_b64="nonce",
                tag_b64="tag",
                cloud_path=remote_segment_path,
                local_staging_path=f"{video.id}/segments/000000.cspseg",
            )
        ],
    )

    from app.storage.mock import MockStorageBackend

    storage = MockStorageBackend(settings.mock_storage_dir)
    storage.upload_bytes(segment_path.read_bytes(), remote_segment_path)
    storage.upload_bytes(b"manifest-payload-v1", video.manifest_path or "")

    _upload_remote_artifacts(
        settings,
        video=video,
        segments=list_video_segments(settings, video_id=video.id),
        manifest_path=manifest_path,
        job_id=job.id,
    )

    # Segment remains unchanged (skip upload on size match) while manifest is refreshed.
    assert storage.download_bytes(remote_segment_path) == b"segment-payload"
    assert storage.download_bytes(video.manifest_path or "") == b"manifest-payload-v2"
