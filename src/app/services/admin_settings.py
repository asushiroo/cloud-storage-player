from __future__ import annotations

from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.models.settings import AdminSettings
from app.repositories.settings import get_setting, set_setting
from app.services.admin_runtime_config import (
    BAIDU_APP_KEY_SETTING_KEY,
    BAIDU_OAUTH_REDIRECT_URI_SETTING_KEY,
    BAIDU_SECRET_KEY_SETTING_KEY,
    BAIDU_SIGN_KEY_SETTING_KEY,
    SESSION_SECRET_SETTING_KEY,
    get_baidu_app_key,
    get_baidu_oauth_redirect_uri,
    get_baidu_secret_key,
    get_baidu_sign_key,
    get_session_secret,
)
from app.services.settings import REMOTE_TRANSFER_CONCURRENCY_KEY

PLAYBACK_DOWNLOAD_TRANSFER_CONCURRENCY_KEY = "playback_download_transfer_concurrency"
DOWNLOAD_TRANSFER_CONCURRENCY_KEY = "download_transfer_concurrency"
PASSWORD_HASH_KEY = "password_hash"


def get_admin_settings(settings: Settings) -> AdminSettings:
    stored = get_setting(settings, PLAYBACK_DOWNLOAD_TRANSFER_CONCURRENCY_KEY)
    return AdminSettings(
        playback_download_transfer_concurrency=_resolve_playback_download_transfer_concurrency(
            settings,
            stored_value=stored.value if stored else None,
        ),
        baidu_app_key=get_baidu_app_key(settings),
        baidu_secret_key=get_baidu_secret_key(settings),
        baidu_sign_key=get_baidu_sign_key(settings),
        baidu_oauth_redirect_uri=get_baidu_oauth_redirect_uri(settings),
        session_secret=get_session_secret(settings),
    )


def update_admin_settings(
    settings: Settings,
    *,
    playback_download_transfer_concurrency: int | None = None,
    baidu_app_key: str | None = None,
    baidu_secret_key: str | None = None,
    baidu_sign_key: str | None = None,
    baidu_oauth_redirect_uri: str | None = None,
    session_secret: str | None = None,
) -> AdminSettings:
    current = get_admin_settings(settings)
    next_playback_download_transfer_concurrency = (
        playback_download_transfer_concurrency
        if playback_download_transfer_concurrency is not None
        else current.playback_download_transfer_concurrency
    )
    next_baidu_app_key = baidu_app_key.strip() if baidu_app_key is not None else current.baidu_app_key
    next_baidu_secret_key = (
        baidu_secret_key.strip() if baidu_secret_key is not None else current.baidu_secret_key
    )
    next_baidu_sign_key = baidu_sign_key.strip() if baidu_sign_key is not None else current.baidu_sign_key
    next_baidu_oauth_redirect_uri = (
        baidu_oauth_redirect_uri.strip()
        if baidu_oauth_redirect_uri is not None
        else current.baidu_oauth_redirect_uri
    )
    next_session_secret = session_secret.strip() if session_secret is not None else current.session_secret
    if next_playback_download_transfer_concurrency < 1 or next_playback_download_transfer_concurrency > 32:
        raise ValueError("playback_download_transfer_concurrency must be between 1 and 32.")
    if not next_baidu_oauth_redirect_uri:
        raise ValueError("baidu_oauth_redirect_uri must not be empty.")
    if len(next_session_secret) < 16:
        raise ValueError("session_secret must be at least 16 characters.")
    set_setting(
        settings,
        key=PLAYBACK_DOWNLOAD_TRANSFER_CONCURRENCY_KEY,
        value=str(next_playback_download_transfer_concurrency),
    )
    set_setting(settings, key=BAIDU_APP_KEY_SETTING_KEY, value=next_baidu_app_key)
    set_setting(settings, key=BAIDU_SECRET_KEY_SETTING_KEY, value=next_baidu_secret_key)
    set_setting(settings, key=BAIDU_SIGN_KEY_SETTING_KEY, value=next_baidu_sign_key)
    set_setting(
        settings,
        key=BAIDU_OAUTH_REDIRECT_URI_SETTING_KEY,
        value=next_baidu_oauth_redirect_uri,
    )
    set_setting(settings, key=SESSION_SECRET_SETTING_KEY, value=next_session_secret)
    settings.baidu_oauth_redirect_uri = next_baidu_oauth_redirect_uri
    settings.session_secret = next_session_secret
    return AdminSettings(
        playback_download_transfer_concurrency=next_playback_download_transfer_concurrency,
        baidu_app_key=next_baidu_app_key,
        baidu_secret_key=next_baidu_secret_key,
        baidu_sign_key=next_baidu_sign_key,
        baidu_oauth_redirect_uri=next_baidu_oauth_redirect_uri,
        session_secret=next_session_secret,
    )


def get_playback_download_transfer_concurrency(settings: Settings) -> int:
    stored = get_setting(settings, PLAYBACK_DOWNLOAD_TRANSFER_CONCURRENCY_KEY)
    return _resolve_playback_download_transfer_concurrency(
        settings,
        stored_value=stored.value if stored else None,
    )


def update_login_password(
    settings: Settings,
    *,
    current_password: str,
    new_password: str,
) -> None:
    normalized_new_password = new_password.strip()
    if not normalized_new_password:
        raise ValueError("new_password must not be empty.")
    current_password_hash = get_login_password_hash(settings)
    if not verify_password(current_password, current_password_hash):
        raise ValueError("Invalid current password.")
    next_password_hash = hash_password(normalized_new_password)
    set_setting(
        settings,
        key=PASSWORD_HASH_KEY,
        value=next_password_hash,
    )
    settings.password_hash = next_password_hash
    settings.password = ""
    settings.__dict__.pop("effective_password_hash", None)


def _resolve_playback_download_transfer_concurrency(
    settings: Settings,
    *,
    stored_value: str | None,
) -> int:
    if stored_value is not None:
        return _parse_named_transfer_concurrency(
            stored_value,
            setting_name="playback_download_transfer_concurrency",
        )
    legacy_download = get_setting(settings, DOWNLOAD_TRANSFER_CONCURRENCY_KEY)
    if legacy_download is not None:
        return _parse_named_transfer_concurrency(
            legacy_download.value,
            setting_name="download_transfer_concurrency",
        )
    legacy_remote = get_setting(settings, REMOTE_TRANSFER_CONCURRENCY_KEY)
    if legacy_remote is not None:
        return _parse_remote_transfer_concurrency(legacy_remote.value)
    return settings.effective_download_transfer_concurrency


def get_login_password_hash(settings: Settings) -> str:
    stored = get_setting(settings, PASSWORD_HASH_KEY)
    if stored is not None:
        return stored.value
    return settings.effective_password_hash


def _parse_remote_transfer_concurrency(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError("remote_transfer_concurrency must be stored as an integer.") from exc
    if parsed < 1 or parsed > 32:
        raise ValueError("remote_transfer_concurrency must be between 1 and 32.")
    return parsed


def _parse_named_transfer_concurrency(value: str, *, setting_name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{setting_name} must be stored as an integer.") from exc
    if parsed < 1 or parsed > 32:
        raise ValueError(f"{setting_name} must be between 1 and 32.")
    return parsed
