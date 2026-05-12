import time
from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.models.segments import VideoSegment
from app.repositories.settings import set_setting
from app.services.segment_prefetch import acquire_prefetch_session, release_prefetch_session
from app.services.settings import DOWNLOAD_TRANSFER_CONCURRENCY_KEY
from app.storage.mock import MockStorageBackend


def build_settings(tmp_path: Path, *, remote_transfer_concurrency: int = 5) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "prefetch.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
        remote_transfer_concurrency=remote_transfer_concurrency,
    )
    initialize_database(settings)
    return settings


def build_segment(settings: Settings, *, video_id: int, segment_index: int) -> VideoSegment:
    remote_path = f"/apps/CloudStoragePlayer/mock/{video_id}/{segment_index}.bin"
    local_path = settings.segment_staging_dir / str(video_id) / "segments" / f"{segment_index:06d}.cspseg"
    return VideoSegment(
        id=segment_index + 1,
        video_id=video_id,
        segment_index=segment_index,
        original_offset=segment_index * 100,
        original_length=100,
        ciphertext_size=10,
        plaintext_sha256=f"sha-{segment_index}",
        nonce_b64=f"nonce-{segment_index}",
        tag_b64=f"tag-{segment_index}",
        cloud_path=remote_path,
        local_staging_path=str(local_path),
        created_at="2026-05-11 00:00:00",
    )


def test_prefetch_session_continues_beyond_first_window(monkeypatch, tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    video_id = 42
    storage = MockStorageBackend(settings.mock_storage_dir)
    segments = [build_segment(settings, video_id=video_id, segment_index=index) for index in range(8)]
    download_calls: list[str] = []

    for segment in segments:
        storage.upload_bytes(f"segment-{segment.segment_index}".encode("utf-8"), segment.cloud_path or "")

    class TrackingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            download_calls.append(remote_path)
            time.sleep(0.03)
            return storage.download_bytes(remote_path)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.segment_prefetch.build_storage_backend", lambda _settings: TrackingStorage())
    session = acquire_prefetch_session(settings, video_id=video_id, segments=segments)
    assert session is not None

    try:
        session.request_prefetch(current_segment_index=0)
        deadline = time.time() + 3
        while time.time() < deadline and len(download_calls) < 7:
            time.sleep(0.05)
    finally:
        release_prefetch_session(video_id)

    assert len(download_calls) >= 7


def test_prefetch_session_uses_runtime_configured_transfer_concurrency(monkeypatch, tmp_path: Path) -> None:
    settings = build_settings(tmp_path, remote_transfer_concurrency=1)
    video_id = 64
    storage = MockStorageBackend(settings.mock_storage_dir)
    segments = [build_segment(settings, video_id=video_id, segment_index=index) for index in range(6)]
    max_inflight = {"value": 0}
    active_downloads = {"value": 0}

    for segment in segments:
        storage.upload_bytes(f"segment-{segment.segment_index}".encode("utf-8"), segment.cloud_path or "")

    set_setting(settings, key=DOWNLOAD_TRANSFER_CONCURRENCY_KEY, value="4")

    class TrackingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            active_downloads["value"] += 1
            if active_downloads["value"] > max_inflight["value"]:
                max_inflight["value"] = active_downloads["value"]
            try:
                time.sleep(0.03)
                return storage.download_bytes(remote_path)
            finally:
                active_downloads["value"] -= 1

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.segment_prefetch.build_storage_backend", lambda _settings: TrackingStorage())
    session = acquire_prefetch_session(settings, video_id=video_id, segments=segments)
    assert session is not None

    try:
        session.request_prefetch(current_segment_index=0)
        deadline = time.time() + 3
        while time.time() < deadline and max_inflight["value"] < 4:
            time.sleep(0.05)
    finally:
        release_prefetch_session(video_id)

    assert max_inflight["value"] >= 4
