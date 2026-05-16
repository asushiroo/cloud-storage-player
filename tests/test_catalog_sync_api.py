import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.services.video_artwork import replace_video_artwork
from app.services.imports import import_local_video
from app.services.video_manifest_sync import sync_due_video_manifests
from app.storage.mock import MockStorageBackend


def build_client(
    tmp_path: Path,
    password: str = "shared-secret",
    *,
    database_name: str,
    mock_storage_path: Path,
    content_key_path: Path,
    segment_staging_path: Path,
    covers_path: Path,
) -> tuple[TestClient, Settings, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / database_name,
        mock_storage_path=mock_storage_path,
        content_key_path=content_key_path,
        segment_staging_path=segment_staging_path,
        covers_path=covers_path,
        segment_size_bytes=512,
    )
    return TestClient(create_app(settings)), settings, password


def login(client: TestClient, password: str) -> None:
    response = client.post("/api/auth/login", json={"password": password})
    assert response.status_code == 200


def create_sample_video(output_path: Path) -> Path:
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


def test_catalog_sync_requires_authentication(tmp_path: Path) -> None:
    shared_remote = tmp_path / "mock-remote"
    shared_key = tmp_path / "keys" / "content.key"
    client, _, _ = build_client(
        tmp_path,
        database_name="catalog-sync.db",
        mock_storage_path=shared_remote,
        content_key_path=shared_key,
        segment_staging_path=tmp_path / "segments",
        covers_path=tmp_path / "covers",
    )

    response = client.post("/api/videos/sync")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_catalog_sync_rebuilds_videos_and_segments_from_remote_manifest(tmp_path: Path) -> None:
    shared_remote = tmp_path / "mock-remote"
    shared_key = tmp_path / "keys" / "content.key"
    source_path = create_sample_video(tmp_path / "remote-sync.mp4")
    file_bytes = source_path.read_bytes()

    _, writer_settings, _ = build_client(
        tmp_path,
        database_name="writer.db",
        mock_storage_path=shared_remote,
        content_key_path=shared_key,
        segment_staging_path=tmp_path / "writer-segments",
        covers_path=tmp_path / "writer-covers",
    )
    import_local_video(
        writer_settings,
        source_path=str(source_path),
        title="Remote Demo",
        tags=["远端", "演示"],
    )
    source_path.unlink()

    client, _, password = build_client(
        tmp_path,
        database_name="reader.db",
        mock_storage_path=shared_remote,
        content_key_path=shared_key,
        segment_staging_path=tmp_path / "reader-segments",
        covers_path=tmp_path / "reader-covers",
    )
    login(client, password)

    sync_response = client.post("/api/videos/sync")

    assert sync_response.status_code == 200
    assert sync_response.json() == {
        "discovered_manifest_count": 1,
        "created_video_count": 1,
        "updated_video_count": 0,
        "failed_manifest_count": 0,
        "errors": [],
    }

    videos_response = client.get("/api/videos")
    assert videos_response.status_code == 200
    videos_payload = videos_response.json()
    assert len(videos_payload) == 1
    assert videos_payload[0]["title"] == "Remote Demo"
    assert videos_payload[0]["tags"] == ["远端", "演示"]
    assert videos_payload[0]["manifest_path"].startswith("/apps/CloudStoragePlayer/")
    assert "/videos/" not in videos_payload[0]["manifest_path"]
    assert "manifest.json" not in videos_payload[0]["manifest_path"]
    assert videos_payload[0]["segment_count"] >= 1

    storage = MockStorageBackend(shared_remote)
    assert storage.local_path_for(videos_payload[0]["manifest_path"]).exists()

    stream_response = client.get(f"/api/videos/{videos_payload[0]['id']}/stream")
    assert stream_response.status_code == 200
    assert stream_response.content == file_bytes

    second_sync_response = client.post("/api/videos/sync")
    assert second_sync_response.status_code == 200
    assert second_sync_response.json() == {
        "discovered_manifest_count": 1,
        "created_video_count": 0,
        "updated_video_count": 1,
        "failed_manifest_count": 0,
        "errors": [],
    }

    second_videos_response = client.get("/api/videos")
    assert second_videos_response.status_code == 200
    assert len(second_videos_response.json()) == 1


def test_catalog_sync_restores_remote_custom_poster(tmp_path: Path) -> None:
    shared_remote = tmp_path / "mock-remote"
    shared_key = tmp_path / "keys" / "content.key"
    source_path = create_sample_video(tmp_path / "remote-custom-poster.mp4")

    _, writer_settings, _ = build_client(
        tmp_path,
        database_name="writer-custom.db",
        mock_storage_path=shared_remote,
        content_key_path=shared_key,
        segment_staging_path=tmp_path / "writer-custom-segments",
        covers_path=tmp_path / "writer-custom-covers",
    )
    job = import_local_video(
        writer_settings,
        source_path=str(source_path),
        title="Remote Custom Poster Demo",
        tags=["远端", "封面"],
    )
    assert job.video_id is not None
    png_data_url = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
    )
    replace_video_artwork(
        writer_settings,
        job.video_id,
        poster_data_url=png_data_url,
    )

    from datetime import UTC, datetime, timedelta

    synced_count = sync_due_video_manifests(
        writer_settings,
        now=datetime.now(UTC) + timedelta(minutes=11),
    )
    assert synced_count == 1

    client, _, password = build_client(
        tmp_path,
        database_name="reader-custom.db",
        mock_storage_path=shared_remote,
        content_key_path=shared_key,
        segment_staging_path=tmp_path / "reader-custom-segments",
        covers_path=tmp_path / "reader-custom-covers",
    )
    login(client, password)

    sync_response = client.post("/api/videos/sync")
    assert sync_response.status_code == 200
    assert sync_response.json()["created_video_count"] == 1

    videos_response = client.get("/api/videos")
    assert videos_response.status_code == 200
    payload = videos_response.json()
    assert len(payload) == 1
    assert payload[0]["has_custom_poster"] is True
    assert payload[0]["poster_path"] is not None

    poster_response = client.get(payload[0]["poster_path"])
    assert poster_response.status_code == 200
    assert poster_response.headers["content-type"] == "image/avif"
