from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app


def build_client(
    tmp_path: Path,
    password: str = "shared-secret",
) -> tuple[TestClient, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "auth.db",
    )
    return TestClient(create_app(settings)), password


def test_login_page_is_available(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)

    response = client.get("/login")

    assert response.status_code == 200
    assert "Cloud Storage Player" in response.text


def test_root_redirects_when_logged_out(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_success_creates_session(tmp_path: Path) -> None:
    client, password = build_client(tmp_path)

    response = client.post(
        "/auth/login",
        data={"password": password},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"

    home_response = client.get("/")
    assert home_response.status_code == 200
    assert "Library" in home_response.text


def test_login_failure_returns_401(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)

    response = client.post("/auth/login", data={"password": "wrong-password"})

    assert response.status_code == 401
    assert "Invalid password." in response.text


def test_logout_clears_session(tmp_path: Path) -> None:
    client, password = build_client(tmp_path)
    client.post("/auth/login", data={"password": password})

    logout_response = client.post("/auth/logout", follow_redirects=False)

    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/login"

    home_response = client.get("/", follow_redirects=False)
    assert home_response.status_code == 303
    assert home_response.headers["location"] == "/login"
