from __future__ import annotations

import time
from pathlib import Path
from threading import Event

from app.core.config import Settings
from app.core.keys import load_or_create_content_key
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.media.crypto import encrypt_segment
from app.repositories.video_segments import NewVideoSegment, create_video_segments
from app.repositories.videos import create_video
import app.services.segment_prefetch as segment_prefetch_service
from app.services.streaming import iter_video_stream, prepare_video_stream
from app.storage.mock import MockStorageBackend


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "streaming-remote-payload.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
        segment_size_bytes=64,
    )
    initialize_database(settings)
    return settings


def test_stream_uses_remote_payload_without_waiting_for_cache_write(monkeypatch, tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    plaintext = b"0123456789abcdefghijklmnopqrstuvwxyz"
    video = _create_remote_only_segment_video(settings, plaintext=plaintext)
    storage = MockStorageBackend(settings.mock_storage_dir)

    class TrackingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            return storage.download_bytes(remote_path)

        def close(self) -> None:
            return None

    background_started = Event()
    background_finished = Event()
    real_background_persist = segment_prefetch_service._persist_segment_payload_background

    def delayed_background_persist(_settings, _segment, payload: bytes) -> None:
        background_started.set()
        time.sleep(0.2)
        real_background_persist(_settings, _segment, payload)
        background_finished.set()

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: TrackingStorage())
    monkeypatch.setattr("app.services.segment_prefetch._persist_segment_payload_background", delayed_background_persist)

    payload = prepare_video_stream(settings, video_id=video.id, range_header="bytes=0-15")

    started_at = time.perf_counter()
    streamed = b"".join(iter_video_stream(payload))
    elapsed = time.perf_counter() - started_at

    assert streamed == plaintext[:16]
    assert elapsed < 0.2
    assert background_started.wait(1.0)
    assert background_finished.wait(1.0)


def test_stream_reuses_prefetched_first_remote_segment_without_double_download(monkeypatch, tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    plaintext = b"0123456789abcdefghijklmnopqrstuvwxyz"
    video = _create_remote_only_segment_video(settings, plaintext=plaintext)
    storage = MockStorageBackend(settings.mock_storage_dir)
    download_calls: list[str] = []

    class TrackingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            download_calls.append(remote_path)
            return storage.download_bytes(remote_path)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: TrackingStorage())
    monkeypatch.setattr("app.services.streaming.queue_segment_cache_write", lambda _settings, _segment, _payload: None)

    payload = prepare_video_stream(settings, video_id=video.id, range_header="bytes=0-15")
    streamed = b"".join(iter_video_stream(payload))

    assert streamed == plaintext[:16]
    assert len(download_calls) == 1


def _create_remote_only_segment_video(settings: Settings, *, plaintext: bytes):
    key = load_or_create_content_key(settings)
    encrypted = encrypt_segment(plaintext, key, nonce=b"123456789012")
    video = create_video(
        settings,
        title="Remote Only Segment",
        mime_type="video/mp4",
        size=len(plaintext),
        manifest_path="/apps/CloudStoragePlayer/mock/manifest.bin",
        source_path=None,
    )

    remote_path = f"/apps/CloudStoragePlayer/mock/{video.id}/0.bin"
    storage = MockStorageBackend(settings.mock_storage_dir)
    storage.upload_bytes(encrypted.ciphertext + encrypted.tag, remote_path)

    create_video_segments(
        settings,
        video_id=video.id,
        segments=[
            NewVideoSegment(
                segment_index=0,
                original_offset=0,
                original_length=len(plaintext),
                ciphertext_size=encrypted.ciphertext_size,
                plaintext_sha256=encrypted.plaintext_sha256,
                nonce_b64=encrypted.nonce_b64,
                tag_b64=encrypted.tag_b64,
                cloud_path=remote_path,
                local_staging_path=str(
                    settings.segment_staging_dir / str(video.id) / "segments" / "000000.cspseg"
                ),
            )
        ],
    )
    return video
