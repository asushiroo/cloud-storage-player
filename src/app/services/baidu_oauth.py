from __future__ import annotations

from urllib.parse import urlencode

from app.core.config import Settings
from app.repositories.settings import get_setting, set_setting
from app.storage.baidu_api import BaiduAuthorizationError, BaiduOpenApi

BAIDU_REFRESH_TOKEN_KEY = "baidu_refresh_token"
BAIDU_SCOPE = "basic,netdisk"
BAIDU_AUTHORIZE_URL = "https://openapi.baidu.com/oauth/2.0/authorize"


class BaiduOAuthConfigurationError(ValueError):
    """Raised when Baidu OAuth is not configured correctly."""


def build_baidu_authorize_url(settings: Settings) -> str | None:
    if not settings.baidu_app_key:
        return None

    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.baidu_app_key,
            "redirect_uri": settings.baidu_oauth_redirect_uri,
            "scope": BAIDU_SCOPE,
            "force_login": 1,
        }
    )
    return f"{BAIDU_AUTHORIZE_URL}?{query}"


def get_baidu_refresh_token(settings: Settings) -> str | None:
    token = get_setting(settings, BAIDU_REFRESH_TOKEN_KEY)
    if token is None:
        return None
    return token.value.strip() or None


def has_baidu_refresh_token(settings: Settings) -> bool:
    return get_baidu_refresh_token(settings) is not None


def set_baidu_refresh_token(settings: Settings, refresh_token: str) -> None:
    normalized = refresh_token.strip()
    if not normalized:
        raise ValueError("Baidu refresh token must not be empty.")
    set_setting(settings, key=BAIDU_REFRESH_TOKEN_KEY, value=normalized)


def authorize_baidu_with_code(
    settings: Settings,
    *,
    code: str,
    api: BaiduOpenApi | None = None,
) -> None:
    normalized_code = code.strip()
    if not normalized_code:
        raise ValueError("Baidu authorization code must not be empty.")
    if not settings.baidu_app_key:
        raise BaiduOAuthConfigurationError("BAIDU_APP_KEY is not configured.")
    if not settings.baidu_secret_key:
        raise BaiduOAuthConfigurationError("BAIDU_SECRET_KEY is not configured.")

    client = api or BaiduOpenApi()
    owns_client = api is None
    try:
        token = client.exchange_authorization_code(
            client_id=settings.baidu_app_key,
            client_secret=settings.baidu_secret_key,
            code=normalized_code,
            redirect_uri=settings.baidu_oauth_redirect_uri,
        )
    except BaiduAuthorizationError:
        raise
    finally:
        if owns_client:
            client.close()

    set_baidu_refresh_token(settings, token.refresh_token)
