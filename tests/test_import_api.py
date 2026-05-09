import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.repositories.folders import create_folder
from app.repositories.video_segments import list_video_segments


def build_client(
    tmp_path: Path,
    password: str = "shared-secret",
    *,
    ffmpeg_binary: str = "ffmpeg",
) -> tuple[TestClient, Settings, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "import.db",
        ffmpeg_binary=ffmpeg_binary,
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        segment_size_bytes=512,
    )
    return TestClient(create_app(settings)), settings, password


def login(client: TestClient, password: str) -> None:
    response = client.post(
        "/auth/login",
        data={"password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303


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


def test_import_api_requires_authentication(tmp_path: Path) -> None:
    client, _, _ = build_client(tmp_path)

    response = client.get("/api/imports")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_import_video_creates_completed_job_and_video(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "demo.mp4")
    folder = create_folder(settings, name="Movies")
    login(client, password)

    response = client.post(
        "/api/imports",
        json={
            "source_path": str(source_path),
            "folder_id": folder.id,
            "title": "Imported Demo",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["progress_percent"] == 100
    assert payload["video_id"] is not None

    video_response = client.get(f"/api/videos/{payload['video_id']}")
    assert video_response.status_code == 200
    video_payload = video_response.json()
    assert video_payload["title"] == "Imported Demo"
    assert video_payload["folder_id"] == folder.id
    assert video_payload["mime_type"] == "video/mp4"
    assert video_payload["size"] > 0
    assert video_payload["duration_seconds"] is not None
    assert video_payload["source_path"] == str(source_path)
    assert video_payload["cover_path"] is not None
    assert video_payload["segment_count"] >= 1

    segments = list_video_segments(settings, video_id=payload["video_id"])
    assert len(segments) == video_payload["segment_count"]
    assert all(Path(segment.local_staging_path).exists() for segment in segments)

    cover_response = client.get(video_payload["cover_path"])
    assert cover_response.status_code == 200
    assert cover_response.headers["content-type"] == "image/jpeg"


def test_import_job_list_and_detail_endpoints_work(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "list-demo.mp4")
    login(client, password)

    create_response = client.post("/api/imports", json={"source_path": str(source_path)})
    job_id = create_response.json()["id"]

    list_response = client.get("/api/imports")
    detail_response = client.get(f"/api/imports/{job_id}")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == job_id
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == job_id
    assert detail_response.json()["status"] == "completed"


def test_import_rejects_missing_source_file(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.post("/api/imports", json={"source_path": str(tmp_path / "missing.mp4")})

    assert response.status_code == 400
    assert "Source file does not exist" in response.json()["detail"]


def test_import_of_non_video_file_returns_failed_job(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    source_path = tmp_path / "not-video.txt"
    source_path.write_text("hello", encoding="utf-8")
    login(client, password)

    response = client.post("/api/imports", json={"source_path": str(source_path)})

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["video_id"] is None
    assert payload["error_message"] is not None


def test_import_still_succeeds_when_cover_extraction_fails(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path, ffmpeg_binary="missing-ffmpeg-for-test")
    source_path = create_sample_video(tmp_path / "no-cover.mp4")
    login(client, password)

    response = client.post("/api/imports", json={"source_path": str(source_path)})

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["video_id"] is not None

    video_response = client.get(f"/api/videos/{payload['video_id']}")
    assert video_response.status_code == 200
    assert video_response.json()["cover_path"] is None
