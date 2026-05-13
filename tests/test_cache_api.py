import subprocess
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.repositories.video_segments import NewVideoSegment, create_video_segments
from app.repositories.videos import create_video
from app.services.manifests import (
    encrypted_remote_manifest_upload_path,
    local_manifest_path,
    local_segment_path,
)
from app.services.segment_local_paths import serialize_local_staging_path


def build_client(tmp_path: Path, password: str = "shared-secret") -> tuple[TestClient, Settings, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "cache.db",
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


def wait_for_job_status(client: TestClient, job_id: int, *, expected_status: str) -> dict:
    deadline = time.time() + 15
    while time.time() < deadline:
        response = client.get(f"/api/imports/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] == expected_status:
            return payload
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for job {job_id} to reach {expected_status}.")


def test_cache_summary_lists_and_clears_local_segments(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "cached.mp4")
    login(client, password)

    create_response = client.post("/api/imports", json={"source_path": str(source_path)})
    completed_job = wait_for_job_status(client, create_response.json()["id"], expected_status="completed")
    video_id = completed_job["video_id"]
    assert video_id is not None
    stage_dir = local_manifest_path(settings, video_id=video_id).parent
    assert stage_dir.exists()
    assert local_manifest_path(settings, video_id=video_id).exists()
    assert encrypted_remote_manifest_upload_path(settings, video_id=video_id).exists()

    summary_response = client.get("/api/cache")
    assert summary_response.status_code == 200
    assert summary_response.json()["video_count"] == 1
    assert summary_response.json()["total_size_bytes"] > 0

    list_response = client.get("/api/cache/videos")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == video_id
    assert payload[0]["cached_segment_count"] >= 1

    clear_response = client.delete(f"/api/cache/videos/{video_id}")
    assert clear_response.status_code == 200
    assert clear_response.json() == {"cleared_video_count": 1}
    assert not local_segment_path(settings, video_id=video_id, segment_index=0).parent.exists()
    assert local_manifest_path(settings, video_id=video_id).exists()
    assert encrypted_remote_manifest_upload_path(settings, video_id=video_id).exists()

    summary_after_clear = client.get("/api/cache")
    assert summary_after_clear.status_code == 200
    assert summary_after_clear.json() == {"total_size_bytes": 0, "video_count": 0}


def test_manual_cache_job_restores_local_cache_and_reports_transfer_speed(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "remote-cache.mp4")
    login(client, password)

    create_response = client.post("/api/imports", json={"source_path": str(source_path)})
    completed_import = wait_for_job_status(client, create_response.json()["id"], expected_status="completed")
    video_id = completed_import["video_id"]
    assert video_id is not None

    stage_dir = local_manifest_path(settings, video_id=video_id).parent
    segments_dir = stage_dir / "segments"
    for path in sorted(segments_dir.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    segments_dir.rmdir()
    assert not segments_dir.exists()
    assert stage_dir.exists()

    cache_response = client.post(f"/api/videos/{video_id}/cache")
    assert cache_response.status_code == 202
    assert cache_response.json()["job_kind"] == "cache"

    completed_cache = wait_for_job_status(client, cache_response.json()["id"], expected_status="completed")
    assert completed_cache["video_id"] == video_id
    assert completed_cache["remote_bytes_transferred"] > 0
    assert completed_cache["transfer_speed_bytes_per_second"] is not None
    assert completed_cache["transfer_speed_bytes_per_second"] > 0
    assert (stage_dir / "segments").exists()

    cache_summary = client.get("/api/cache")
    assert cache_summary.status_code == 200
    assert cache_summary.json()["video_count"] == 1


def test_video_detail_includes_cache_status_and_cache_endpoint_rejects_fully_cached_video(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    login(client, password)

    video = create_video(
        settings,
        title="Cached Detail",
        mime_type="video/mp4",
        size=1024,
        manifest_path="/apps/CloudStoragePlayer/mock/manifest.bin",
        source_path=str(tmp_path / "cached-detail.mp4"),
    )
    segment_paths = [
        local_segment_path(settings, video_id=video.id, segment_index=0).with_name("0.cspseg"),
        local_segment_path(settings, video_id=video.id, segment_index=1).with_name("1.cspseg"),
    ]
    for index, segment_path in enumerate(segment_paths):
        segment_path.parent.mkdir(parents=True, exist_ok=True)
        segment_path.write_bytes(f"segment-{index}".encode("utf-8"))

    create_video_segments(
        settings,
        video_id=video.id,
        segments=[
            NewVideoSegment(
                segment_index=index,
                original_offset=index * 100,
                original_length=100,
                ciphertext_size=segment_path.stat().st_size,
                plaintext_sha256=f"sha-{index}",
                nonce_b64=f"nonce-{index}",
                tag_b64=f"tag-{index}",
                cloud_path=f"/apps/CloudStoragePlayer/mock/{video.id}/{index}.bin",
                local_staging_path=serialize_local_staging_path(settings, segment_path),
            )
            for index, segment_path in enumerate(segment_paths)
        ],
    )

    detail_response = client.get(f"/api/videos/{video.id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["segment_count"] == 2
    assert detail_payload["cached_segment_count"] == detail_payload["segment_count"]
    assert detail_payload["cached_size_bytes"] > 0

    cache_response = client.post(f"/api/videos/{video.id}/cache")
    assert cache_response.status_code == 409
    assert cache_response.json() == {"detail": "Video is already fully cached."}


def test_cache_videos_api_normalizes_legacy_artwork_paths(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    login(client, password)

    video = create_video(
        settings,
        title="Legacy cache artwork",
        mime_type="video/mp4",
        size=456,
        cover_path="/covers/cache-cover.jpg",
        poster_path="/covers/cache-poster.avif",
    )
    segment_path = local_segment_path(settings, video_id=video.id, segment_index=0).with_name("0.cspseg")
    segment_path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"cache-segment"
    segment_path.write_bytes(payload)
    create_video_segments(
        settings,
        video_id=video.id,
        segments=[
            NewVideoSegment(
                segment_index=0,
                original_offset=0,
                original_length=len(payload),
                ciphertext_size=len(payload),
                plaintext_sha256="sha-cache",
                nonce_b64="nonce-cache",
                tag_b64="tag-cache",
                cloud_path=f"/apps/CloudStoragePlayer/mock/{video.id}/0.bin",
                local_staging_path=serialize_local_staging_path(settings, segment_path),
            )
        ],
    )

    response = client.get("/api/cache/videos")

    assert response.status_code == 200
    payload_json = response.json()
    assert len(payload_json) == 1
    assert payload_json[0]["id"] == video.id
    assert payload_json[0]["cover_path"] == "/api/artwork/cache-cover.jpg"
    assert payload_json[0]["poster_path"] == "/api/artwork/cache-poster.avif"


def test_cache_videos_api_normalizes_legacy_jpg_poster_path_to_avif(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    login(client, password)

    video = create_video(
        settings,
        title="Legacy cache jpg poster",
        mime_type="video/mp4",
        size=456,
        poster_path="/covers/cache-poster.jpg",
    )
    segment_path = local_segment_path(settings, video_id=video.id, segment_index=0).with_name("0.cspseg")
    segment_path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"cache-segment"
    segment_path.write_bytes(payload)
    create_video_segments(
        settings,
        video_id=video.id,
        segments=[
            NewVideoSegment(
                segment_index=0,
                original_offset=0,
                original_length=len(payload),
                ciphertext_size=len(payload),
                plaintext_sha256="sha-cache",
                nonce_b64="nonce-cache",
                tag_b64="tag-cache",
                cloud_path=f"/apps/CloudStoragePlayer/mock/{video.id}/0.bin",
                local_staging_path=serialize_local_staging_path(settings, segment_path),
            )
        ],
    )

    response = client.get("/api/cache/videos")

    assert response.status_code == 200
    payload_json = response.json()
    assert len(payload_json) == 1
    assert payload_json[0]["poster_path"] == "/api/artwork/cache-poster.avif"
