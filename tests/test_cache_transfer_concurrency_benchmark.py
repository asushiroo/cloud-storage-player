from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import perf_counter, sleep

import pytest

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.repositories.import_jobs import create_cache_job, get_import_job
from app.repositories.video_segments import NewVideoSegment, create_video_segments
from app.repositories.videos import create_video
from app.services.cache import process_cache_job
from app.storage.mock import MockStorageBackend


@dataclass(slots=True)
class CacheBenchmarkResult:
    concurrency: int
    process_seconds: float
    transfer_window_seconds: float
    effective_speed_bytes_per_second: float
    reported_speed_bytes_per_second: float
    reported_transfer_millis: int
    max_inflight: int
    total_bytes: int


def build_settings(tmp_path: Path, *, concurrency: int) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "cache-transfer-benchmark.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
        remote_transfer_concurrency=concurrency,
    )
    initialize_database(settings)
    return settings


def test_cache_job_single_vs_five_concurrency_benchmark(monkeypatch, tmp_path: Path) -> None:
    single = _run_cache_benchmark(monkeypatch, tmp_path / "single", concurrency=1)
    parallel = _run_cache_benchmark(monkeypatch, tmp_path / "parallel", concurrency=5)

    print(
        "single concurrency:",
        {
            "process_seconds": round(single.process_seconds, 3),
            "transfer_window_seconds": round(single.transfer_window_seconds, 3),
            "effective_speed_bytes_per_second": round(single.effective_speed_bytes_per_second, 2),
            "reported_speed_bytes_per_second": round(single.reported_speed_bytes_per_second, 2),
            "max_inflight": single.max_inflight,
            "total_bytes": single.total_bytes,
        },
    )
    print(
        "five concurrency:",
        {
            "process_seconds": round(parallel.process_seconds, 3),
            "transfer_window_seconds": round(parallel.transfer_window_seconds, 3),
            "effective_speed_bytes_per_second": round(parallel.effective_speed_bytes_per_second, 2),
            "reported_speed_bytes_per_second": round(parallel.reported_speed_bytes_per_second, 2),
            "max_inflight": parallel.max_inflight,
            "total_bytes": parallel.total_bytes,
        },
    )

    assert single.max_inflight == 1
    assert parallel.max_inflight >= 5
    assert parallel.transfer_window_seconds < single.transfer_window_seconds * 0.6
    assert parallel.effective_speed_bytes_per_second > single.effective_speed_bytes_per_second * 1.8


def _run_cache_benchmark(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    concurrency: int,
) -> CacheBenchmarkResult:
    settings = build_settings(tmp_path, concurrency=concurrency)
    video = create_video(
        settings,
        title=f"Concurrency {concurrency}",
        mime_type="video/mp4",
        size=10 * 256 * 1024,
        manifest_path="/apps/CloudStoragePlayer/mock/manifest.bin",
        source_path=str(tmp_path / f"concurrency-{concurrency}.mp4"),
    )

    remote_storage = MockStorageBackend(settings.mock_storage_dir)
    total_bytes = 0
    segments = []
    for index in range(10):
        payload = bytes([index % 251]) * (256 * 1024)
        total_bytes += len(payload)
        remote_path = f"/apps/CloudStoragePlayer/mock/{video.id}/{index}.bin"
        remote_storage.upload_bytes(payload, remote_path)
        segments.append(
            NewVideoSegment(
                segment_index=index,
                original_offset=index * len(payload),
                original_length=len(payload),
                ciphertext_size=len(payload),
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
        task_name=f"cache: {video.title}",
        target_video_id=video.id,
    )

    class TrackingStorage:
        def __init__(self, root_dir: Path) -> None:
            self._backend = MockStorageBackend(root_dir)
            self._lock = Lock()
            self._active = 0
            self.max_inflight = 0
            self.first_started_at: float | None = None
            self.last_completed_at: float | None = None

        def download_bytes(self, remote_path: str) -> bytes:
            started_at = perf_counter()
            with self._lock:
                self._active += 1
                self.max_inflight = max(self.max_inflight, self._active)
                if self.first_started_at is None or started_at < self.first_started_at:
                    self.first_started_at = started_at
            try:
                sleep(0.05)
                return self._backend.download_bytes(remote_path)
            finally:
                completed_at = perf_counter()
                with self._lock:
                    self._active -= 1
                    if self.last_completed_at is None or completed_at > self.last_completed_at:
                        self.last_completed_at = completed_at

        def close(self) -> None:
            return None

    tracking_storage = TrackingStorage(settings.mock_storage_dir)
    monkeypatch.setattr("app.services.cache.build_storage_backend", lambda _settings: tracking_storage)

    started_at = perf_counter()
    result = process_cache_job(settings, job.id)
    process_seconds = perf_counter() - started_at

    assert result.status == "completed"
    updated_job = get_import_job(settings, job.id)
    assert updated_job is not None
    assert updated_job.remote_bytes_transferred == total_bytes
    assert updated_job.transfer_speed_bytes_per_second is not None
    assert tracking_storage.first_started_at is not None
    assert tracking_storage.last_completed_at is not None

    transfer_window_seconds = tracking_storage.last_completed_at - tracking_storage.first_started_at
    effective_speed_bytes_per_second = total_bytes / transfer_window_seconds

    assert updated_job.remote_transfer_millis == pytest.approx(
        transfer_window_seconds * 1000,
        rel=0.1,
        abs=30.0,
    )
    assert updated_job.transfer_speed_bytes_per_second == pytest.approx(
        effective_speed_bytes_per_second,
        rel=0.1,
    )

    return CacheBenchmarkResult(
        concurrency=concurrency,
        process_seconds=process_seconds,
        transfer_window_seconds=transfer_window_seconds,
        effective_speed_bytes_per_second=effective_speed_bytes_per_second,
        reported_speed_bytes_per_second=updated_job.transfer_speed_bytes_per_second,
        reported_transfer_millis=updated_job.remote_transfer_millis,
        max_inflight=tracking_storage.max_inflight,
        total_bytes=total_bytes,
    )
