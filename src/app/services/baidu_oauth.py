from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from app.core.config import Settings
from app.repositories.settings import get_setting, set_setting
from app.services.admin_runtime_config import (
    get_baidu_app_key,
    get_baidu_oauth_redirect_uri,
    get_baidu_secret_key,
)
from app.storage.baidu_api import BaiduAuthorizationError, BaiduOpenApi, BaiduToken

BAIDU_ACCESS_TOKEN_KEY = "baidu_access_token"
BAIDU_ACCESS_TOKEN_EXPIRES_AT_KEY = "baidu_access_token_expires_at"
BAIDU_REFRESH_TOKEN_KEY = "baidu_refresh_token"
BAIDU_SCOPE = "basic,netdisk"
BAIDU_AUTHORIZE_URL = "https://openapi.baidu.com/oauth/2.0/authorize"


class BaiduOAuthConfigurationError(ValueError):
    """Raised when Baidu OAuth is not configured correctly."""


def build_baidu_authorize_url(settings: Settings) -> str | None:
    baidu_app_key = get_baidu_app_key(settings)
    if not baidu_app_key:
        return None

    query = urlencode(
        {
            "response_type": "code",
            "client_id": baidu_app_key,
            "redirect_uri": get_baidu_oauth_redirect_uri(settings),
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


def get_baidu_access_token(settings: Settings) -> str | None:
    token = get_setting(settings, BAIDU_ACCESS_TOKEN_KEY)
    expires_at = get_setting(settings, BAIDU_ACCESS_TOKEN_EXPIRES_AT_KEY)
    if token is None or expires_at is None:
        return None

    normalized_token = token.value.strip()
    if not normalized_token:
        return None

    try:
        expires_at_value = datetime.fromisoformat(expires_at.value)
    except ValueError:
        return None

    if expires_at_value.tzinfo is None:
        expires_at_value = expires_at_value.replace(tzinfo=timezone.utc)
    if expires_at_value <= datetime.now(timezone.utc):
        return None
    return normalized_token


def set_baidu_access_token(
    settings: Settings,
    access_token: str,
    *,
    expires_in: int,
) -> None:
    normalized_token = access_token.strip()
    if not normalized_token:
        raise ValueError("Baidu access token must not be empty.")
    if expires_in <= 0:
        raise ValueError("Baidu access token expires_in must be greater than 0.")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(expires_in - 60, 1))
    set_setting(settings, key=BAIDU_ACCESS_TOKEN_KEY, value=normalized_token)
    set_setting(
        settings,
        key=BAIDU_ACCESS_TOKEN_EXPIRES_AT_KEY,
        value=expires_at.isoformat(),
    )


def persist_baidu_token(settings: Settings, token: BaiduToken) -> None:
    set_baidu_refresh_token(settings, token.refresh_token)
    set_baidu_access_token(settings, token.access_token, expires_in=token.expires_in)


def authorize_baidu_with_code(
    settings: Settings,
    *,
    code: str,
    api: BaiduOpenApi | None = None,
) -> BaiduToken:
    normalized_code = code.strip()
    if not normalized_code:
        raise ValueError("Baidu authorization code must not be empty.")
    baidu_app_key = get_baidu_app_key(settings)
    if not baidu_app_key:
        raise BaiduOAuthConfigurationError("BAIDU_APP_KEY is not configured.")
    baidu_secret_key = get_baidu_secret_key(settings)
    if not baidu_secret_key:
        raise BaiduOAuthConfigurationError("BAIDU_SECRET_KEY is not configured.")

    client = api or BaiduOpenApi()
    owns_client = api is None
    try:
        token = client.exchange_authorization_code(
            client_id=baidu_app_key,
            client_secret=baidu_secret_key,
            code=normalized_code,
            redirect_uri=get_baidu_oauth_redirect_uri(settings),
        )
    except BaiduAuthorizationError:
        raise
    finally:
        if owns_client:
            client.close()

    persist_baidu_token(settings, token)
    return token
