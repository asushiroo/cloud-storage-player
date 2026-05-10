from pathlib import Path

from app.core.config import Settings
from app.main import create_app
from app.repositories.settings import get_setting
from app.services.baidu_oauth import (
    BAIDU_REFRESH_TOKEN_KEY,
    authorize_baidu_with_code,
    build_baidu_authorize_url,
)
from app.storage.baidu_api import BaiduToken


class FakeBaiduApi:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def exchange_authorization_code(
        self,
        *,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> BaiduToken:
        self.calls.append((client_id, client_secret, code, redirect_uri))
        return BaiduToken(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=3600,
            scope="basic,netdisk",
        )


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        database_path=tmp_path / "oauth.db",
    )
    create_app(settings)
    return settings


def test_build_baidu_authorize_url_uses_configured_app_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BAIDU_APP_KEY", "demo-app-key")
    settings = build_settings(tmp_path)

    authorize_url = build_baidu_authorize_url(settings)

    assert authorize_url is not None
    assert "client_id=demo-app-key" in authorize_url
    assert "scope=basic%2Cnetdisk" in authorize_url
    assert "redirect_uri=oob" in authorize_url


def test_authorize_baidu_with_code_persists_refresh_token(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BAIDU_APP_KEY", "demo-app-key")
    monkeypatch.setenv("BAIDU_SECRET_KEY", "demo-secret-key")
    settings = build_settings(tmp_path)
    api = FakeBaiduApi()

    authorize_baidu_with_code(settings, code="demo-code", api=api)

    stored = get_setting(settings, BAIDU_REFRESH_TOKEN_KEY)
    assert stored is not None
    assert stored.value == "refresh-token"
    assert api.calls == [
        ("demo-app-key", "demo-secret-key", "demo-code", settings.baidu_oauth_redirect_uri)
    ]
