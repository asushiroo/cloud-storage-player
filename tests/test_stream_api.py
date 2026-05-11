import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.models.segments import VideoSegment
from app.repositories.videos import get_video
from app.repositories.video_segments import list_video_segments
from app.services.imports import import_local_video
from app.storage.baidu_api import BaiduApiError
from app.storage.mock import MockStorageBackend


def build_client(tmp_path: Path, password: str = "shared-secret") -> tuple[TestClient, Settings, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "stream.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
        segment_size_bytes=512,
    )
    return TestClient(create_app(settings)), settings, password


def login(client: TestClient, password: str) -> None:
    response = client.post("/api/auth/login", json={"password": password})
    assert response.status_code == 200


def create_sample_video(output_path: Path) -> Path:
    import subprocess

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=160x90:d=1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output_path


def remove_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    root.rmdir()


def test_stream_requires_authentication(tmp_path: Path) -> None:
    client, settings, _ = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "stream.mp4")
    job = import_local_video(settings, source_path=str(source_path))

    response = client.get(f"/api/videos/{job.video_id}/stream")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_stream_returns_full_file(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "full.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    login(client, password)

    response = client.get(f"/api/videos/{job.video_id}/stream")

    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == str(len(file_bytes))
    assert response.content == file_bytes


def test_stream_returns_partial_content_for_range_request(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "range.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": "bytes=0-31"},
    )

    assert response.status_code == 206
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "32"
    assert response.headers["content-range"] == f"bytes 0-31/{len(file_bytes)}"
    assert response.content == file_bytes[:32]


def test_stream_supports_suffix_ranges(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "suffix.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": "bytes=-24"},
    )

    assert response.status_code == 206
    assert response.headers["content-length"] == "24"
    assert response.content == file_bytes[-24:]


def test_stream_rejects_unsatisfiable_ranges(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "invalid-range.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": f"bytes={len(file_bytes)}-{len(file_bytes) + 10}"},
    )

    assert response.status_code == 416
    assert response.headers["content-range"] == f"bytes */{len(file_bytes)}"


def test_stream_can_fallback_to_local_encrypted_segments_when_source_is_removed(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "removed.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    login(client, password)

    response = client.get(f"/api/videos/{job.video_id}/stream")

    assert response.status_code == 200
    assert response.content == file_bytes


def test_stream_can_fallback_to_mock_remote_when_source_and_local_segments_are_removed(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "remote-fallback.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    remove_tree(settings.segment_staging_dir / str(job.video_id))
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": "bytes=16-127"},
    )

    assert response.status_code == 206
    assert response.headers["content-length"] == str(127 - 16 + 1)
    assert response.content == file_bytes[16:128]


def test_stream_remote_fallback_caches_downloaded_segments_without_full_exists_scan(monkeypatch, tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "remote-cache-window.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    remove_tree(settings.segment_staging_dir / str(job.video_id))

    segments = list_video_segments(settings, video_id=job.video_id)
    assert len(segments) >= 1
    storage = MockStorageBackend(settings.mock_storage_dir)
    exists_calls: list[str] = []
    download_calls: list[str] = []

    class CountingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            download_calls.append(remote_path)
            return storage.download_bytes(remote_path)

        def exists(self, remote_path: str) -> bool:
            exists_calls.append(remote_path)
            return storage.exists(remote_path)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: CountingStorage())
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": "bytes=0-31"},
    )

    assert response.status_code == 206
    assert response.content == file_bytes[:32]
    assert len(exists_calls) == 0
    assert download_calls[0] == segments[0].cloud_path
    first_segment = segments[0]
    assert first_segment.local_staging_path is not None
    assert Path(first_segment.local_staging_path).exists()
    if len(segments) > 1:
        deadline = time.time() + 2
        while time.time() < deadline and len(download_calls) < 2:
            time.sleep(0.05)
        assert len(download_calls) >= 2


def test_stream_logs_warning_when_baidu_remote_segment_returns_404(
    monkeypatch,
    caplog,
    tmp_path: Path,
) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "missing-remote.mp4")
    job = import_local_video(settings, source_path=str(source_path))
    remove_tree(settings.segment_staging_dir / str(job.video_id))

    class FailingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            raise BaiduApiError("404 Not Found")

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: FailingStorage())
    login(client, password)

    with caplog.at_level("WARNING", logger="app.services.streaming"):
        response = client.get(
            f"/api/videos/{job.video_id}/stream",
            headers={"Range": "bytes=0-31"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Encrypted segment file is missing."}
    assert any(
        "Failed to fetch encrypted segment from Baidu remote storage" in record.message
        for record in caplog.records
    )


def test_stream_prefetch_continues_beyond_first_window(monkeypatch, tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    settings.segment_size_bytes = 64
    source_path = create_sample_video(tmp_path / "prefetch-rolling-window.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    remove_tree(settings.segment_staging_dir / str(job.video_id))

    segments = list_video_segments(settings, video_id=job.video_id)
    assert len(segments) >= 7
    storage = MockStorageBackend(settings.mock_storage_dir)
    download_calls: list[str] = []

    class TrackingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            download_calls.append(remote_path)
            time.sleep(0.03)
            return storage.download_bytes(remote_path)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: TrackingStorage())
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": "bytes=0-31"},
    )

    assert response.status_code == 206
    assert response.content == file_bytes[:32]

    deadline = time.time() + 3
    while time.time() < deadline and len(download_calls) < 6:
        time.sleep(0.05)

    assert len(download_calls) >= 6


def test_stream_returns_404_when_source_local_and_remote_segments_are_all_missing(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "missing-everywhere.mp4")
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    remove_tree(settings.segment_staging_dir / str(job.video_id))

    video = get_video(settings, job.video_id)
    assert video is not None
    assert video.manifest_path is not None
    storage = MockStorageBackend(settings.mock_storage_dir)
    remove_tree(storage.local_path_for(video.manifest_path).parent)
    login(client, password)

    response = client.get(f"/api/videos/{job.video_id}/stream")

    assert response.status_code == 404
    assert response.json() == {"detail": "Encrypted segment file is missing."}
