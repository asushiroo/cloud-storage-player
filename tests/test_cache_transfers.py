import threading
import time
from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.repositories.import_jobs import create_cache_job
from app.repositories.video_segments import NewVideoSegment, create_video_segments
from app.repositories.videos import create_video
from app.services.cache import process_cache_job
from app.storage.mock import MockStorageBackend


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "cache-transfer.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
        remote_transfer_concurrency=3,
    )
    initialize_database(settings)
    return settings


def test_process_cache_job_downloads_multiple_segments_concurrently(monkeypatch, tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    video = create_video(
        settings,
        title="Concurrent Cache",
        mime_type="video/mp4",
        size=2048,
        manifest_path="/apps/CloudStoragePlayer/mock/manifest.bin",
        source_path=str(tmp_path / "concurrent-cache.mp4"),
    )

    remote_storage = MockStorageBackend(settings.mock_storage_dir)
    segment_count = 4
    segments = []
    for index in range(segment_count):
        remote_path = f"/apps/CloudStoragePlayer/mock/{video.id}/{index}.bin"
        remote_storage.upload_bytes(f"segment-{index}".encode("utf-8"), remote_path)
        segments.append(
            NewVideoSegment(
                segment_index=index,
                original_offset=index * 100,
                original_length=100,
                ciphertext_size=len(f"segment-{index}".encode("utf-8")),
                plaintext_sha256=f"sha-{index}",
                nonce_b64=f"nonce-{index}",
                tag_b64=f"tag-{index}",
                cloud_path=remote_path,
                local_staging_path=str(
                    settings.segment_staging_dir / str(video.id) / "segments" / f"{index:06d}.cspseg"
                ),
            )
        )
    create_video_segments(settings, video_id=video.id, segments=segments)

    job = create_cache_job(
        settings,
        source_path=video.source_path or f"video:{video.id}",
        requested_title=video.title,
        task_name=f"缓存：{video.title}",
        target_video_id=video.id,
    )

    max_inflight = {"value": 0}

    class TrackingStorage:
        def __init__(self, root_dir: Path) -> None:
            self._backend = MockStorageBackend(root_dir)
            self._active = 0
            self._lock = threading.Lock()

        def download_bytes(self, remote_path: str) -> bytes:
            with self._lock:
                self._active += 1
                if self._active > max_inflight["value"]:
                    max_inflight["value"] = self._active
            try:
                time.sleep(0.05)
                return self._backend.download_bytes(remote_path)
            finally:
                with self._lock:
                    self._active -= 1

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.cache.build_storage_backend", lambda _settings: TrackingStorage(settings.mock_storage_dir))

    result = process_cache_job(settings, job.id)

    assert result.status == "completed"
    assert max_inflight["value"] >= 2
