from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.repositories.settings import set_setting
from app.services.admin_settings import PASSWORD_HASH_KEY


def build_client(tmp_path: Path, password: str = "shared-secret") -> tuple[TestClient, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "auth-api.db",
    )
    return TestClient(create_app(settings)), password


def test_auth_api_session_reports_logged_out_by_default(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)

    response = client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_auth_api_login_and_logout_round_trip(tmp_path: Path) -> None:
    client, password = build_client(tmp_path)

    login_response = client.post("/api/auth/login", json={"password": password})

    assert login_response.status_code == 200
    assert login_response.json() == {"authenticated": True}

    session_response = client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json() == {"authenticated": True}

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json() == {"authenticated": False}

    session_after_logout = client.get("/api/auth/session")
    assert session_after_logout.status_code == 200
    assert session_after_logout.json() == {"authenticated": False}


def test_auth_api_rejects_invalid_password(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)

    response = client.post("/api/auth/login", json={"password": "wrong-password"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid password."}


def test_auth_api_uses_password_hash_from_settings_table(tmp_path: Path) -> None:
    client, password = build_client(tmp_path)
    app_settings = client.app.state.settings
    set_setting(
        app_settings,
        key=PASSWORD_HASH_KEY,
        value=hash_password("new-shared-secret"),
    )

    old_password_response = client.post("/api/auth/login", json={"password": password})
    assert old_password_response.status_code == 401
    assert old_password_response.json() == {"detail": "Invalid password."}

    new_password_response = client.post("/api/auth/login", json={"password": "new-shared-secret"})
    assert new_password_response.status_code == 200
    assert new_password_response.json() == {"authenticated": True}
