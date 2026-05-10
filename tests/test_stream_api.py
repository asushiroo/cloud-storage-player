from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.imports import import_local_video
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


def test_stream_returns_404_when_source_local_and_remote_segments_are_all_missing(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "missing-everywhere.mp4")
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    remove_tree(settings.segment_staging_dir / str(job.video_id))

    storage = MockStorageBackend(settings.mock_storage_dir)
    remove_tree(storage.local_path_for(f"/apps/CloudStoragePlayer/videos/{job.video_id}"))
    login(client, password)

    response = client.get(f"/api/videos/{job.video_id}/stream")

    assert response.status_code == 404
    assert response.json() == {"detail": "Source file not found."}
