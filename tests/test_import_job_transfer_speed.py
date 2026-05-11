from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.repositories.import_jobs import create_cache_job, record_import_job_transfer
from app.repositories.videos import create_video


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "job-transfer-speed.db",
    )
    initialize_database(settings)
    return settings


def test_transfer_speed_uses_wall_clock_time_for_overlapping_transfers(monkeypatch, tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    video = create_video(
        settings,
        title="Wall Clock Speed",
        mime_type="video/mp4",
        size=100,
    )
    job = create_cache_job(
        settings,
        source_path=f"video:{video.id}",
        requested_title="Wall Clock Speed",
        task_name="cache: Wall Clock Speed",
        target_video_id=video.id,
    )

    time_points = iter([1100, 1150])
    monkeypatch.setattr(
        "app.repositories.import_jobs._current_time_millis",
        lambda: next(time_points),
    )

    record_import_job_transfer(settings, job.id, byte_count=100, elapsed_seconds=0.1)
    updated_job = record_import_job_transfer(settings, job.id, byte_count=100, elapsed_seconds=0.1)

    assert updated_job.remote_bytes_transferred == 200
    assert updated_job.remote_transfer_millis == 150
    assert updated_job.transfer_speed_bytes_per_second is not None
    assert round(updated_job.transfer_speed_bytes_per_second, 2) == round(200 / 0.15, 2)
