from __future__ import annotations

from app.core.config import Settings
from app.repositories.settings import get_setting

BAIDU_APP_KEY_SETTING_KEY = "baidu_app_key"
BAIDU_SECRET_KEY_SETTING_KEY = "baidu_secret_key"
BAIDU_SIGN_KEY_SETTING_KEY = "baidu_sign_key"
BAIDU_OAUTH_REDIRECT_URI_SETTING_KEY = "baidu_oauth_redirect_uri"
SESSION_SECRET_SETTING_KEY = "session_secret"


def get_baidu_app_key(settings: Settings) -> str:
    stored = get_setting(settings, BAIDU_APP_KEY_SETTING_KEY)
    if stored is not None:
        return stored.value.strip()
    return settings.baidu_app_key or ""


def get_baidu_secret_key(settings: Settings) -> str:
    stored = get_setting(settings, BAIDU_SECRET_KEY_SETTING_KEY)
    if stored is not None:
        return stored.value.strip()
    return settings.baidu_secret_key or ""


def get_baidu_sign_key(settings: Settings) -> str:
    stored = get_setting(settings, BAIDU_SIGN_KEY_SETTING_KEY)
    if stored is not None:
        return stored.value.strip()
    return settings.baidu_sign_key or ""


def get_baidu_oauth_redirect_uri(settings: Settings) -> str:
    stored = get_setting(settings, BAIDU_OAUTH_REDIRECT_URI_SETTING_KEY)
    if stored is not None:
        normalized = stored.value.strip()
        if normalized:
            return normalized
    return settings.baidu_oauth_redirect_uri


def get_session_secret(settings: Settings) -> str:
    stored = get_setting(settings, SESSION_SECRET_SETTING_KEY)
    if stored is not None:
        normalized = stored.value.strip()
        if normalized:
            return normalized
    return settings.session_secret
