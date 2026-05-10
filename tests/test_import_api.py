import subprocess
import time
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.keys import load_content_key
from app.core.security import hash_password
from app.main import create_app
from app.repositories.folders import create_folder
from app.repositories.videos import create_video
from app.repositories.import_jobs import create_import_job
from app.repositories.settings import set_setting
from app.repositories.video_segments import list_video_segments
from app.services.manifests import decrypt_manifest_payload
from app.storage.mock import MockStorageBackend


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
        mock_storage_path=tmp_path / "mock-remote",
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


def wait_for_job_status(
    client: TestClient,
    job_id: int,
    *,
    expected_status: str,
    timeout_seconds: float = 15.0,
) -> dict:
    deadline = time.time() + timeout_seconds
    last_payload: dict | None = None
    while time.time() < deadline:
        response = client.get(f"/api/imports/{job_id}")
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload["status"] == expected_status:
            return last_payload
        time.sleep(0.1)
    raise AssertionError(
        f"Timed out waiting for job {job_id} to reach {expected_status}. Last payload: {last_payload}"
    )


def wait_for_job_statuses(
    client: TestClient,
    job_id: int,
    *,
    expected_statuses: set[str],
    timeout_seconds: float = 15.0,
) -> dict:
    deadline = time.time() + timeout_seconds
    last_payload: dict | None = None
    while time.time() < deadline:
        response = client.get(f"/api/imports/{job_id}")
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload["status"] in expected_statuses:
            return last_payload
        time.sleep(0.1)
    raise AssertionError(
        f"Timed out waiting for job {job_id} to reach one of {sorted(expected_statuses)}. Last payload: {last_payload}"
    )


def test_import_api_requires_authentication(tmp_path: Path) -> None:
    client, _, _ = build_client(tmp_path)

    response = client.get("/api/imports")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_import_video_creates_queued_job_and_completes_in_background(tmp_path: Path) -> None:
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
            "tags": ["动画", "治愈", "动画"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_kind"] == "import"
    assert payload["task_name"] == "Imported Demo"
    assert payload["status"] == "queued"
    assert payload["progress_percent"] == 0
    assert payload["video_id"] is None
    assert payload["requested_tags"] == ["动画", "治愈"]

    completed_payload = wait_for_job_status(
        client,
        payload["id"],
        expected_status="completed",
    )
    assert completed_payload["progress_percent"] == 100
    assert completed_payload["video_id"] is not None

    video_response = client.get(f"/api/videos/{completed_payload['video_id']}")
    assert video_response.status_code == 200
    video_payload = video_response.json()
    assert video_payload["title"] == "Imported Demo"
    assert video_payload["folder_id"] == folder.id
    assert video_payload["mime_type"] == "video/mp4"
    assert video_payload["size"] > 0
    assert video_payload["duration_seconds"] is not None
    assert video_payload["source_path"] == str(source_path)
    assert video_payload["cover_path"] is not None
    assert video_payload["poster_path"] == video_payload["cover_path"]
    assert video_payload["segment_count"] >= 1
    assert video_payload["tags"] == ["动画", "治愈"]
    assert video_payload["manifest_path"] is not None
    assert video_payload["manifest_path"].startswith("/apps/CloudStoragePlayer/")
    assert "manifest.json" not in video_payload["manifest_path"]
    assert "/videos/" not in video_payload["manifest_path"]

    segments = list_video_segments(settings, video_id=completed_payload["video_id"])
    assert len(segments) == video_payload["segment_count"]
    assert all(Path(segment.local_staging_path).exists() for segment in segments)
    manifest_file = settings.segment_staging_dir / str(completed_payload["video_id"]) / "manifest.json"
    assert manifest_file.exists()

    storage = MockStorageBackend(settings.mock_storage_dir)
    remote_manifest_path = storage.local_path_for(video_payload["manifest_path"])
    assert remote_manifest_path.exists()
    remote_manifest_bytes = remote_manifest_path.read_bytes()
    assert b"Imported Demo" not in remote_manifest_bytes
    assert b"manifest.json" not in remote_manifest_bytes
    assert str(source_path).encode("utf-8") not in remote_manifest_bytes
    assert "动画".encode("utf-8") not in remote_manifest_bytes
    remote_manifest = decrypt_manifest_payload(
        remote_manifest_bytes,
        key=load_content_key(settings),
    )
    assert remote_manifest["video_id"] == completed_payload["video_id"]
    assert remote_manifest["segment_count"] == len(segments)
    assert remote_manifest["title"] == "Imported Demo"
    assert remote_manifest["tags"] == ["动画", "治愈"]
    for segment in segments:
        assert segment.cloud_path is not None
        assert storage.local_path_for(segment.cloud_path).exists()
        assert "segments" not in segment.cloud_path
        assert segment.cloud_path.endswith(".bin")

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
    assert detail_response.json()["status"] in {"queued", "running", "completed"}

    completed_payload = wait_for_job_status(client, job_id, expected_status="completed")
    assert completed_payload["video_id"] is not None


def test_import_job_list_endpoint_recovers_preexisting_queued_jobs(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "recovered-demo.mp4")
    job = create_import_job(settings, source_path=str(source_path))
    login(client, password)

    response = client.get("/api/imports")

    assert response.status_code == 200
    assert response.json()[0]["id"] == job.id

    completed_payload = wait_for_job_status(client, job.id, expected_status="completed")
    assert completed_payload["video_id"] is not None


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
    assert payload["status"] == "queued"
    failed_payload = wait_for_job_status(client, payload["id"], expected_status="failed")
    assert failed_payload["video_id"] is None
    assert failed_payload["error_message"] is not None


def test_import_still_succeeds_when_cover_extraction_fails(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path, ffmpeg_binary="missing-ffmpeg-for-test")
    source_path = create_sample_video(tmp_path / "no-cover.mp4")
    login(client, password)

    response = client.post("/api/imports", json={"source_path": str(source_path)})

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "queued"
    completed_payload = wait_for_job_status(client, payload["id"], expected_status="completed")
    assert completed_payload["video_id"] is not None

    video_response = client.get(f"/api/videos/{completed_payload['video_id']}")
    assert video_response.status_code == 200
    assert video_response.json()["cover_path"] is None


def test_delete_video_removes_catalog_row_and_local_and_mock_remote_artifacts(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "delete-demo.mp4")
    login(client, password)

    create_response = client.post("/api/imports", json={"source_path": str(source_path)})
    job_id = create_response.json()["id"]
    completed_payload = wait_for_job_status(client, job_id, expected_status="completed")
    video_id = completed_payload["video_id"]
    assert video_id is not None

    video_response = client.get(f"/api/videos/{video_id}")
    assert video_response.status_code == 200
    video_payload = video_response.json()
    stage_dir = settings.segment_staging_dir / str(video_id)
    assert stage_dir.exists()

    storage = MockStorageBackend(settings.mock_storage_dir)
    assert video_payload["manifest_path"] is not None
    remote_manifest_path = storage.local_path_for(video_payload["manifest_path"])
    assert remote_manifest_path.exists()

    delete_response = client.delete(f"/api/videos/{video_id}")

    assert delete_response.status_code == 202
    delete_job = delete_response.json()
    assert delete_job["job_kind"] == "delete"
    completed_delete_job = wait_for_job_status(client, delete_job["id"], expected_status="completed")
    assert completed_delete_job["target_video_id"] == video_id
    assert client.get(f"/api/videos/{video_id}").status_code == 404
    assert client.get("/api/videos").json() == []
    assert not stage_dir.exists()
    assert not remote_manifest_path.exists()

    if video_payload["cover_path"] is not None:
        cover_response = client.get(video_payload["cover_path"])
        assert cover_response.status_code == 404


def test_delete_video_still_cleans_local_catalog_after_switching_active_backend(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "switch-backend-delete.mp4")
    login(client, password)

    create_response = client.post("/api/imports", json={"source_path": str(source_path)})
    job_id = create_response.json()["id"]
    completed_payload = wait_for_job_status(client, job_id, expected_status="completed")
    video_id = completed_payload["video_id"]
    assert video_id is not None

    set_setting(settings, key="storage_backend", value="baidu")

    delete_response = client.delete(f"/api/videos/{video_id}")

    assert delete_response.status_code == 202
    delete_job = delete_response.json()
    assert delete_job["job_kind"] == "delete"
    wait_for_job_status(client, delete_job["id"], expected_status="completed")
    assert client.get(f"/api/videos/{video_id}").status_code == 404
    assert client.get("/api/videos").json() == []


def test_folder_import_creates_one_job_per_video_file_recursively(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    source_dir = tmp_path / "batch-folder"
    nested_dir = source_dir / "nested"
    nested_dir.mkdir(parents=True)
    create_sample_video(source_dir / "episode-01.mp4")
    create_sample_video(nested_dir / "episode-02.mkv")
    (nested_dir / "readme.txt").write_text("ignore me", encoding="utf-8")
    login(client, password)

    response = client.post(
        "/api/imports/folder",
        json={"source_path": str(source_dir), "tags": ["批量", "导入"]},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["created_job_count"] == 2
    assert len(payload["created_job_ids"]) == 2

    jobs_response = client.get("/api/imports")
    assert jobs_response.status_code == 200
    listed = jobs_response.json()
    assert len(listed) >= 2
    assert all(job["requested_tags"] == ["批量", "导入"] for job in listed[:2])


def test_clear_finished_import_jobs_keeps_active_jobs_and_removes_finished_ones(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    queued_source = create_sample_video(tmp_path / "queued.mp4")
    failed_source = create_sample_video(tmp_path / "failed.mp4")
    completed_source = create_sample_video(tmp_path / "completed.mp4")
    queued_job = create_import_job(settings, source_path=str(queued_source))
    failed_job = create_import_job(settings, source_path=str(failed_source))
    completed_job = create_import_job(settings, source_path=str(completed_source))

    from app.repositories.import_jobs import mark_import_job_completed, mark_import_job_failed

    completed_video = create_video(settings, title="Completed", mime_type="video/mp4", size=123)
    mark_import_job_failed(settings, failed_job.id, error_message="boom")
    mark_import_job_completed(settings, completed_job.id, video_id=completed_video.id)
    login(client, password)

    response = client.delete("/api/imports")

    assert response.status_code == 200
    assert response.json()["deleted_job_count"] == 2

    list_response = client.get("/api/imports")
    assert list_response.status_code == 200
    remaining_jobs = list_response.json()
    assert len(remaining_jobs) == 1
    assert remaining_jobs[0]["id"] == queued_job.id


def test_cancel_running_import_job_marks_it_cancelled_and_cleans_partial_video(monkeypatch, tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "cancel-running.mp4")
    login(client, password)

    from app.media.chunker import iter_file_chunks as real_iter_file_chunks

    def slow_iter_file_chunks(*args, **kwargs):
        for chunk in real_iter_file_chunks(*args, **kwargs):
            time.sleep(0.05)
            yield chunk

    monkeypatch.setattr("app.services.imports.iter_file_chunks", slow_iter_file_chunks)

    response = client.post("/api/imports", json={"source_path": str(source_path)})

    assert response.status_code == 201
    job_id = response.json()["id"]
    wait_for_job_statuses(client, job_id, expected_statuses={"running", "cancelling", "completed"})

    cancel_response = client.post(f"/api/imports/{job_id}/cancel")
    assert cancel_response.status_code == 200

    final_payload = wait_for_job_statuses(client, job_id, expected_statuses={"cancelled", "completed"})
    if final_payload["status"] == "completed":
        pytest.skip("Background import completed before cancellation request could be observed.")

    assert final_payload["status"] == "cancelled"
    assert client.get("/api/videos").json() == []


def test_update_video_artwork_replaces_cover_and_poster(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "artwork.mp4")
    login(client, password)

    create_response = client.post("/api/imports", json={"source_path": str(source_path)})
    job_id = create_response.json()["id"]
    completed_payload = wait_for_job_status(client, job_id, expected_status="completed")
    video_id = completed_payload["video_id"]
    assert video_id is not None

    png_data_url = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y2fW1kAAAAASUVORK5CYII="
    )
    response = client.post(
        f"/api/videos/{video_id}/artwork",
        json={"cover_data_url": png_data_url, "poster_data_url": png_data_url},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cover_path"].endswith("-cover.png")
    assert payload["poster_path"].endswith("-poster.png")
    assert client.get(payload["cover_path"]).status_code == 200
    assert client.get(payload["poster_path"]).status_code == 200
