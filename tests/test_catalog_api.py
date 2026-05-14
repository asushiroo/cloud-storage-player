from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.repositories.settings import get_setting, set_setting
from app.repositories.videos import create_video
from app.services.artwork_storage import (
    build_poster_file_name,
    read_artwork_bytes,
    store_encrypted_artwork_bytes,
)


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

    response = client.get("/api/videos")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_empty_catalog_endpoints_return_empty_lists(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    login(client, password)

    videos_response = client.get("/api/videos")
    paged_videos_response = client.get("/api/videos/page")

    assert videos_response.status_code == 200
    assert videos_response.json() == []
    assert paged_videos_response.status_code == 200
    assert paged_videos_response.json() == {
        "items": [],
        "offset": 0,
        "limit": 12,
        "total": 0,
        "has_more": False,
    }


def test_catalog_endpoints_return_inserted_rows(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    create_video(
        settings,
        title="Demo Video",
        cover_path="covers/demo.jpg",
        mime_type="video/mp4",
        size=1024,
        duration_seconds=12.5,
        manifest_path="/apps/CloudStoragePlayer/videos/1/manifest.json",
        tags=["收藏", "示例"],
    )
    login(client, password)

    videos_response = client.get("/api/videos")

    assert videos_response.status_code == 200
    assert videos_response.json()[0]["title"] == "Demo Video"
    assert videos_response.json()[0]["mime_type"] == "video/mp4"
    assert videos_response.json()[0]["tags"] == ["收藏", "示例"]


def test_videos_endpoint_can_filter_by_exact_tag(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    create_video(
        settings,
        title="Family Movie",
        mime_type="video/mp4",
        size=100,
        tags=["Family", "Weekend"],
    )
    create_video(
        settings,
        title="Sci-Fi Movie",
        mime_type="video/mp4",
        size=200,
        tags=["Sci-Fi"],
    )
    login(client, password)

    response = client.get("/api/videos?tag=family")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Family Movie"]


def test_videos_endpoint_can_search_by_title_source_path_or_tag(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    create_video(
        settings,
        title="Ocean Documentary",
        mime_type="video/mp4",
        size=100,
        source_path="/media/docs/ocean-blue.mp4",
        tags=["Nature"],
    )
    create_video(
        settings,
        title="City Walk",
        mime_type="video/mp4",
        size=200,
        source_path="/media/travel/tokyo-night.mp4",
        tags=["Weekend"],
    )
    login(client, password)

    response = client.get("/api/videos?q=week")
    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["City Walk"]

    response = client.get("/api/videos?q=ocean-blue")
    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Ocean Documentary"]


def test_video_page_endpoint_paginates_results(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    for index in range(15):
        create_video(
            settings,
            title=f"Episode {index:02d}",
            mime_type="video/mp4",
            size=100 + index,
        )
    login(client, password)

    first_page = client.get("/api/videos/page?offset=0&limit=12")
    second_page = client.get("/api/videos/page?offset=12&limit=12")

    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert first_payload["offset"] == 0
    assert first_payload["limit"] == 12
    assert first_payload["total"] == 15
    assert first_payload["has_more"] is True
    assert len(first_payload["items"]) == 12
    assert first_payload["items"][0]["title"] == "Episode 00"

    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["offset"] == 12
    assert second_payload["limit"] == 12
    assert second_payload["total"] == 15
    assert second_payload["has_more"] is False
    assert [item["title"] for item in second_payload["items"]] == ["Episode 12", "Episode 13", "Episode 14"]


def test_artwork_api_returns_decrypted_avif_payload(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    login(client, password)

    artwork_name = build_poster_file_name(42)
    payload = b"fake-avif-payload"
    stored_path = store_encrypted_artwork_bytes(
        settings,
        file_name=artwork_name,
        payload=payload,
    )

    response = client.get(stored_path)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/avif"
    assert response.content == payload


def test_artwork_api_can_serve_legacy_jpg_poster_request_from_avif_storage(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    login(client, password)

    stored_path = store_encrypted_artwork_bytes(
        settings,
        file_name="9-poster.avif",
        payload=b"fake-avif-payload",
    )
    assert stored_path == "/api/artwork/9-poster.avif"

    response = client.get("/api/artwork/9-poster.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/avif"
    expected_payload, expected_type = read_artwork_bytes(settings, artwork_name="9-poster.avif")
    assert expected_type == "image/avif"
    assert response.content == expected_payload


def test_video_tags_endpoint_updates_saved_tags(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    video = create_video(
        settings,
        title="Tagged Video",
        mime_type="video/mp4",
        size=100,
    )
    login(client, password)

    response = client.patch(
        f"/api/videos/{video.id}/tags",
        json={"tags": ["家庭", "周末", "家庭", " "]},
    )

    assert response.status_code == 200
    assert response.json()["tags"] == ["家庭", "周末"]

    detail_response = client.get(f"/api/videos/{video.id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["tags"] == ["家庭", "周末"]


def test_settings_repository_round_trip(tmp_path: Path) -> None:
    _, settings, _ = build_client(tmp_path)

    assert get_setting(settings, "baidu_root") is None

    stored = set_setting(settings, key="baidu_root", value="/CloudStoragePlayer")

    assert stored.key == "baidu_root"
    assert stored.value == "/CloudStoragePlayer"
    loaded = get_setting(settings, "baidu_root")
    assert loaded is not None
    assert loaded.value == "/CloudStoragePlayer"


def test_video_watch_endpoint_updates_analytics_and_recommendation_shelves(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    watched = create_video(
        settings,
        title="Watched Video",
        mime_type="video/mp4",
        size=100,
        duration_seconds=100,
        tags=["Actor A", "secondary:Action"],
    )
    create_video(
        settings,
        title="Similar Video",
        mime_type="video/mp4",
        size=100,
        duration_seconds=120,
        tags=["Actor A", "secondary:Action"],
    )
    login(client, password)

    first = client.post(
        f"/api/videos/{watched.id}/watch",
        json={
            "position_seconds": 15,
            "watched_seconds_delta": 15,
            "completed": False,
        },
    )
    assert first.status_code == 200
    session_token = first.json()["session_token"]

    second = client.post(
        f"/api/videos/{watched.id}/watch",
        json={
            "session_token": session_token,
            "position_seconds": 55,
            "watched_seconds_delta": 40,
            "completed": True,
        },
    )
    assert second.status_code == 200
    payload = second.json()["video"]
    assert payload["valid_play_count"] == 1
    assert payload["total_session_count"] == 1
    assert payload["interest_score"] > 0
    assert payload["highlight_start_seconds"] is not None
    assert payload["highlight_end_seconds"] is not None

    detail = client.get(f"/api/videos/{watched.id}")
    assert detail.status_code == 200
    assert detail.json()["last_position_seconds"] == 55

    shelf = client.get("/api/videos/recommendations")
    assert shelf.status_code == 200
    shelf_payload = shelf.json()
    assert any(item["id"] == watched.id for item in shelf_payload["continue_watching"])
    assert any(item["title"] == "Similar Video" for item in shelf_payload["recommended"])


def test_video_like_endpoint_caps_at_99_and_updates_payload(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    video = create_video(
        settings,
        title="Liked Video",
        mime_type="video/mp4",
        size=100,
    )
    login(client, password)

    for _ in range(120):
        response = client.post(f"/api/videos/{video.id}/like")
        assert response.status_code == 200

    payload = client.get(f"/api/videos/{video.id}").json()
    assert payload["like_count"] == 99


def test_video_like_endpoint_supports_decrement_without_going_below_zero(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    video = create_video(
        settings,
        title="Like Toggle Video",
        mime_type="video/mp4",
        size=100,
    )
    login(client, password)

    increase = client.post(f"/api/videos/{video.id}/like", json={"delta": 1})
    assert increase.status_code == 200
    assert increase.json()["like_count"] == 1

    decrease = client.post(f"/api/videos/{video.id}/like", json={"delta": -1})
    assert decrease.status_code == 200
    assert decrease.json()["like_count"] == 0

    below_zero = client.post(f"/api/videos/{video.id}/like", json={"delta": -1})
    assert below_zero.status_code == 200
    assert below_zero.json()["like_count"] == 0
