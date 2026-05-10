from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.repositories.settings import set_setting
from app.services.baidu_oauth import BAIDU_REFRESH_TOKEN_KEY


def build_client(tmp_path: Path, password: str = "shared-secret") -> tuple[TestClient, Settings, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "settings.db",
    )
    return TestClient(create_app(settings)), settings, password


def login(client: TestClient, password: str) -> None:
    response = client.post(
        "/auth/login",
        data={"password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_settings_api_requires_authentication(tmp_path: Path) -> None:
    client, _, _ = build_client(tmp_path)

    response = client.get("/api/settings")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_settings_api_returns_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BAIDU_APP_KEY", raising=False)
    monkeypatch.delenv("BAIDU_SECRET_KEY", raising=False)
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {
        "baidu_root_path": "/apps/CloudStoragePlayer",
        "cache_limit_bytes": 2147483648,
        "storage_backend": "mock",
        "baidu_authorize_url": None,
        "baidu_has_refresh_token": False,
    }


def test_settings_api_returns_authorize_url_when_baidu_app_key_is_present(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BAIDU_APP_KEY", "demo-app-key")
    monkeypatch.setenv("BAIDU_SECRET_KEY", "demo-secret-key")
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.get("/api/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["storage_backend"] == "mock"
    assert payload["baidu_has_refresh_token"] is False
    assert payload["baidu_authorize_url"] is not None
    assert "client_id=demo-app-key" in payload["baidu_authorize_url"]
    assert "scope=basic%2Cnetdisk" in payload["baidu_authorize_url"]


def test_settings_api_updates_values(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BAIDU_APP_KEY", raising=False)
    monkeypatch.delenv("BAIDU_SECRET_KEY", raising=False)
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.post(
        "/api/settings",
        json={
            "baidu_root_path": "/apps/CloudStoragePlayer-dev",
            "cache_limit_bytes": 1048576,
            "storage_backend": "mock",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "baidu_root_path": "/apps/CloudStoragePlayer-dev",
        "cache_limit_bytes": 1048576,
        "storage_backend": "mock",
        "baidu_authorize_url": None,
        "baidu_has_refresh_token": False,
    }

    read_back = client.get("/api/settings")
    assert read_back.status_code == 200
    assert read_back.json() == {
        "baidu_root_path": "/apps/CloudStoragePlayer-dev",
        "cache_limit_bytes": 1048576,
        "storage_backend": "mock",
        "baidu_authorize_url": None,
        "baidu_has_refresh_token": False,
    }


def test_settings_api_rejects_non_apps_root_for_baidu_backend(tmp_path: Path) -> None:
    client, _, password = build_client(tmp_path)
    login(client, password)

    response = client.post(
        "/api/settings",
        json={
            "storage_backend": "baidu",
            "baidu_root_path": "/CloudStoragePlayer",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "baidu_root_path must start with '/apps/' when storage_backend is baidu."
    }


def test_settings_baidu_oauth_endpoint_marks_refresh_token_as_present(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BAIDU_APP_KEY", "demo-app-key")
    monkeypatch.setenv("BAIDU_SECRET_KEY", "demo-secret-key")
    client, settings, password = build_client(tmp_path)
    login(client, password)

    def fake_authorize_baidu_with_code(app_settings: Settings, *, code: str) -> None:
        assert code == "demo-code"
        set_setting(app_settings, key=BAIDU_REFRESH_TOKEN_KEY, value="refresh-token")

    monkeypatch.setattr(
        "app.api.routes.settings.authorize_baidu_with_code",
        fake_authorize_baidu_with_code,
    )

    response = client.post("/api/settings/baidu/oauth", json={"code": "demo-code"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["baidu_has_refresh_token"] is True
    assert payload["baidu_authorize_url"] is not None
