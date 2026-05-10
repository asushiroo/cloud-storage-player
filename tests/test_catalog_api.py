from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.repositories.folders import create_folder
from app.repositories.settings import get_setting, set_setting
from app.repositories.videos import create_video


def build_client(tmp_path: Path, password: str = "shared-secret") -> tuple[TestClient, Settings, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "catalog.db",
    )
    return TestClient(create_app(settings)), settings, password


def login(client: TestClient, password: str) -> None:
    response = client.post(
        "/auth/login",
        data={"password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_catalog_api_requires_authentication(tmp_path: Path) -> None:
    client, _, _ = build_client(tmp_path)

    response = client.get("/api/folders")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_empty_catalog_endpoints_return_empty_lists(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    login(client, password)

    folders_response = client.get("/api/folders")
    videos_response = client.get("/api/videos")

    assert folders_response.status_code == 200
    assert folders_response.json() == []
    assert videos_response.status_code == 200
    assert videos_response.json() == []


def test_catalog_endpoints_return_inserted_rows(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    folder = create_folder(settings, name="Movies", cover_path="covers/movies.jpg")
    create_video(
        settings,
        folder_id=folder.id,
        title="Demo Video",
        cover_path="covers/demo.jpg",
        mime_type="video/mp4",
        size=1024,
        duration_seconds=12.5,
        manifest_path="/apps/CloudStoragePlayer/videos/1/manifest.json",
    )
    login(client, password)

    folders_response = client.get("/api/folders")
    videos_response = client.get("/api/videos")

    assert folders_response.status_code == 200
    assert folders_response.json()[0]["name"] == "Movies"
    assert folders_response.json()[0]["cover_path"] == "covers/movies.jpg"

    assert videos_response.status_code == 200
    assert videos_response.json()[0]["title"] == "Demo Video"
    assert videos_response.json()[0]["folder_id"] == folder.id
    assert videos_response.json()[0]["mime_type"] == "video/mp4"


def test_videos_endpoint_can_filter_by_folder(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    movies = create_folder(settings, name="Movies")
    anime = create_folder(settings, name="Anime")
    create_video(
        settings,
        folder_id=movies.id,
        title="Movie A",
        mime_type="video/mp4",
        size=100,
    )
    create_video(
        settings,
        folder_id=anime.id,
        title="Anime B",
        mime_type="video/mp4",
        size=200,
    )
    login(client, password)

    response = client.get(f"/api/videos?folder_id={anime.id}")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Anime B"]


def test_settings_repository_round_trip(tmp_path: Path) -> None:
    _, settings, _ = build_client(tmp_path)

    assert get_setting(settings, "baidu_root") is None

    stored = set_setting(settings, key="baidu_root", value="/CloudStoragePlayer")

    assert stored.key == "baidu_root"
    assert stored.value == "/CloudStoragePlayer"
    loaded = get_setting(settings, "baidu_root")
    assert loaded is not None
    assert loaded.value == "/CloudStoragePlayer"
