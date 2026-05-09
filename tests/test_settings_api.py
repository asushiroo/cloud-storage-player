from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app


def build_client(tmp_path: Path, password: str = "shared-secret") -> tuple[TestClient, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "settings.db",
    )
    return TestClient(create_app(settings)), password


def login(client: TestClient, password: str) -> None:
    response = client.post(
        "/auth/login",
        data={"password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_settings_api_requires_authentication(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)

    response = client.get("/api/settings")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_settings_api_returns_defaults(tmp_path: Path) -> None:
    client, password = build_client(tmp_path)
    login(client, password)

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {
        "baidu_root_path": "/CloudStoragePlayer",
        "cache_limit_bytes": 2147483648,
    }


def test_settings_api_updates_values(tmp_path: Path) -> None:
    client, password = build_client(tmp_path)
    login(client, password)

    response = client.post(
        "/api/settings",
        json={
            "baidu_root_path": "/CloudStoragePlayer-dev",
            "cache_limit_bytes": 1048576,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "baidu_root_path": "/CloudStoragePlayer-dev",
        "cache_limit_bytes": 1048576,
    }

    read_back = client.get("/api/settings")
    assert read_back.status_code == 200
    assert read_back.json() == {
        "baidu_root_path": "/CloudStoragePlayer-dev",
        "cache_limit_bytes": 1048576,
    }
