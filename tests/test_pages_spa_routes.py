from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app


def build_client(tmp_path: Path, password: str = "shared-secret") -> tuple[TestClient, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "pages-spa.db",
    )
    return TestClient(create_app(settings)), password


def login(client: TestClient, password: str) -> None:
    response = client.post("/auth/login", data={"password": password}, follow_redirects=False)
    assert response.status_code == 303


def test_protected_spa_routes_redirect_to_login_when_logged_out(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)

    for path in ("/manage", "/settings", "/videos/1", "/videos/1/play"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_protected_spa_routes_render_shell_when_logged_in(tmp_path: Path) -> None:
    client, password = build_client(tmp_path)
    login(client, password)

    for path in ("/manage", "/settings", "/videos/1", "/videos/1/play"):
        response = client.get(path)
        assert response.status_code == 200
        assert "Library" in response.text
