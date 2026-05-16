import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.repositories.import_jobs import create_cache_job
from app.repositories.videos import create_video, request_video_manifest_sync
from app.services.data_archive import load_local_data_archive, save_local_data_archive


def build_client(tmp_path: Path, *, use_frontend_dist: bool = False) -> tuple[TestClient, Settings]:
    frontend_dist = tmp_path / "frontend-dist"
    assets_dir = frontend_dist / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (frontend_dist / "index.html").write_text("<html><body>Frontend Dist</body></html>", encoding="utf-8")
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "runtime.db",
        content_key_path=tmp_path / "keys" / "content.key",
        frontend_dist_path=frontend_dist,
        use_frontend_dist=use_frontend_dist,
        control_token="runtime-control-token",
    )
    return TestClient(create_app(settings)), settings


def login(client: TestClient) -> None:
    response = client.post("/auth/login", data={"password": "shared-secret"}, follow_redirects=False)
    assert response.status_code == 303


def test_spa_routes_can_serve_frontend_dist_index(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path, use_frontend_dist=True)
    login(client)

    response = client.get("/library")

    assert response.status_code == 200
    assert "Frontend Dist" in response.text


def test_runtime_shutdown_state_reports_active_jobs_and_dirty_syncs(tmp_path: Path) -> None:
    client, settings = build_client(tmp_path)
    login(client)
    video = create_video(
        settings,
        title="Runtime Video",
        mime_type="video/mp4",
        size=100,
        manifest_path="/apps/CloudStoragePlayer/runtime/manifest.bin",
        has_custom_poster=True,
    )
    create_cache_job(
        settings,
        source_path="video:1",
        requested_title="Runtime Cache",
        task_name="Runtime Cache",
        target_video_id=video.id,
    )
    request_video_manifest_sync(settings, video.id)

    response = client.get(
        "/api/runtime/shutdown-state",
        headers={"x-csp-control-token": "runtime-control-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["has_pending_work"] is True
    assert any(item.startswith("cache:Runtime Cache ") for item in payload["active_jobs"])
    assert any(item.endswith(":Runtime Video") for item in payload["pending_manifest_sync_videos"])
    assert any(item.endswith(":Runtime Video") for item in payload["pending_custom_poster_sync_videos"])


def test_save_and_load_local_data_archive_round_trip(tmp_path: Path) -> None:
    _, settings = build_client(tmp_path)
    settings.database_file.parent.mkdir(parents=True, exist_ok=True)
    settings.database_file.write_text("database", encoding="utf-8")
    settings.content_key_file.parent.mkdir(parents=True, exist_ok=True)
    settings.content_key_file.write_text("secret-key", encoding="utf-8")
    (settings.runtime_root / ".env").write_text("CSP_PASSWORD=demo", encoding="utf-8")

    archive_path = tmp_path / "backup.zip"
    result = save_local_data_archive(settings, output_path=archive_path)

    assert archive_path.exists()
    assert "data/cloud_storage_player.db" in result.included_entries
    assert "data/keys/content.key" in result.included_entries
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    assert manifest["format"] == "cloud-storage-player-local-data"

    restore_root = tmp_path / "restore"
    import os

    previous_runtime_root = os.environ.get("CSP_RUNTIME_ROOT")
    os.environ["CSP_RUNTIME_ROOT"] = str(restore_root)
    try:
        restore_settings = Settings(
            session_secret="test-session-secret-123456",
            password_hash=hash_password("shared-secret"),
            database_path=Path("data/cloud_storage_player.db"),
            content_key_path=Path("data/keys/content.key"),
            frontend_dist_path=tmp_path / "frontend-dist",
        )
        loaded = load_local_data_archive(restore_settings, archive_path=archive_path)
    finally:
        if previous_runtime_root is None:
            os.environ.pop("CSP_RUNTIME_ROOT", None)
        else:
            os.environ["CSP_RUNTIME_ROOT"] = previous_runtime_root

    assert "data/cloud_storage_player.db" in loaded.included_entries
    assert (restore_root / "data" / "cloud_storage_player.db").read_text(encoding="utf-8") == "database"
    assert (restore_root / "data" / "keys" / "content.key").read_text(encoding="utf-8") == "secret-key"


def test_load_local_data_archive_rejects_existing_targets(tmp_path: Path) -> None:
    _, settings = build_client(tmp_path)
    archive_path = tmp_path / "backup.zip"
    settings.database_file.parent.mkdir(parents=True, exist_ok=True)
    settings.database_file.write_text("database", encoding="utf-8")
    save_local_data_archive(settings, output_path=archive_path)

    settings.database_file.write_text("already-there", encoding="utf-8")

    try:
        load_local_data_archive(settings, archive_path=archive_path)
    except ValueError as exc:
        assert "refusing to overwrite" in str(exc)
    else:
        raise AssertionError("Expected load_local_data_archive to reject existing targets.")
