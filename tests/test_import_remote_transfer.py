from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.media.probe import MediaProbeResult
from app.services.imports import import_local_video
from app.storage.baidu_api import BaiduFrequencyControlError


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "import-transfer.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
        segment_size_bytes=128,
        remote_transfer_concurrency=2,
        baidu_upload_resume_poll_interval_seconds=1,
    )
    initialize_database(settings)
    return settings

def test_import_retries_after_baidu_frequency_control(monkeypatch, tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    source_path = tmp_path / "frequency-control.mp4"
    source_path.write_bytes(b"x" * 1024)

    class FrequencyControlledStorage:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.failed_once = False

        def upload_file(self, local_path: Path, remote_path: str) -> None:
            self.calls.append(remote_path)
            if not self.failed_once:
                self.failed_once = True
                raise BaiduFrequencyControlError("Baidu API error 9013: hit frequence control")

        def close(self) -> None:
            return None

    storage = FrequencyControlledStorage()
    sleep_calls: list[float] = []

    monkeypatch.setattr("app.services.imports.build_storage_backend", lambda _settings: storage)
    monkeypatch.setattr(
        "app.services.imports.probe_video",
        lambda source, ffprobe_binary: MediaProbeResult(
            source_path=source,
            format_name="mp4",
            mime_type="video/mp4",
            size=source.stat().st_size,
            duration_seconds=1.0,
        ),
    )
    monkeypatch.setattr("app.services.remote_transfers.time.sleep", sleep_calls.append)

    job = import_local_video(settings, source_path=str(source_path))

    assert job.status == "completed"
    assert sum(sleep_calls) >= 1.0
    assert len(storage.calls) >= 2
