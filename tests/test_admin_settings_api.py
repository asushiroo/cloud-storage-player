from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.repositories.settings import get_setting, set_setting
from app.services.admin_settings import (
    PASSWORD_HASH_KEY,
    PLAYBACK_DOWNLOAD_TRANSFER_CONCURRENCY_KEY,
)


def build_client(tmp_path: Path, password: str = "shared-secret") -> tuple[TestClient, Settings, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "admin-settings.db",
    )
    return TestClient(create_app(settings)), settings, password


def login(client: TestClient, password: str) -> None:
    response = client.post(
        "/auth/login",
        data={"password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_admin_settings_requires_authentication(tmp_path: Path) -> None:
    client, _, _ = build_client(tmp_path)

    response = client.get("/api/admin/settings")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_admin_settings_returns_default_playback_transfer_concurrency(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.get("/api/admin/settings")

    assert response.status_code == 200
    assert response.json() == {"playback_download_transfer_concurrency": 5}


def test_admin_settings_updates_playback_transfer_concurrency(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.post(
        "/api/admin/settings",
        json={"playback_download_transfer_concurrency": 7},
    )

    assert response.status_code == 200
    assert response.json() == {"playback_download_transfer_concurrency": 7}
    read_back = get_setting(
        client.app.state.settings,
        PLAYBACK_DOWNLOAD_TRANSFER_CONCURRENCY_KEY,
    )
    assert read_back is not None
    assert read_back.value == "7"


def test_admin_settings_uses_legacy_download_transfer_concurrency_as_fallback(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    login(client, password)
    set_setting(settings, key="download_transfer_concurrency", value="8")

    response = client.get("/api/admin/settings")

    assert response.status_code == 200
    assert response.json()["playback_download_transfer_concurrency"] == 8


def test_admin_settings_password_update_changes_login_password(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    login(client, password)

    response = client.post(
        "/api/admin/settings/password",
        json={
            "current_password": password,
            "new_password": "new-shared-secret",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"updated": True}

    stored_password_hash = get_setting(settings, PASSWORD_HASH_KEY)
    assert stored_password_hash is not None
    assert stored_password_hash.value

    client.post("/api/auth/logout")
    old_password_login = client.post("/api/auth/login", json={"password": password})
    assert old_password_login.status_code == 401
    new_password_login = client.post("/api/auth/login", json={"password": "new-shared-secret"})
    assert new_password_login.status_code == 200
    assert new_password_login.json() == {"authenticated": True}


def test_admin_settings_password_update_rejects_wrong_current_password(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.post(
        "/api/admin/settings/password",
        json={
            "current_password": "wrong-password",
            "new_password": "new-shared-secret",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid current password."}


def test_admin_settings_password_update_rejects_empty_new_password(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.post(
        "/api/admin/settings/password",
        json={
            "current_password": password,
            "new_password": "   ",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "new_password must not be empty."}


def test_admin_page_allows_password_update_via_form(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.post(
        "/admin/password",
        data={
            "current_password": password,
            "new_password": "new-shared-secret",
            "confirm_new_password": "new-shared-secret",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?message=Password%20updated.%20Please%20sign%20in%20again."

    old_password_response = client.post("/api/auth/login", json={"password": password})
    assert old_password_response.status_code == 401
    new_password_response = client.post("/api/auth/login", json={"password": "new-shared-secret"})
    assert new_password_response.status_code == 200
    assert new_password_response.json() == {"authenticated": True}


def test_admin_page_rejects_password_confirm_mismatch(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.post(
        "/admin/password",
        data={
            "current_password": password,
            "new_password": "new-shared-secret",
            "confirm_new_password": "other-secret",
        },
    )

    assert response.status_code == 400
    assert "must match" in response.text
