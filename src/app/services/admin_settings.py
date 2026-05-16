from __future__ import annotations

from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.models.settings import AdminSettings
from app.repositories.settings import get_setting, set_setting
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
        )
    )


def update_admin_settings(
    settings: Settings,
    *,
    playback_download_transfer_concurrency: int | None = None,
) -> AdminSettings:
    current = get_admin_settings(settings)
    next_playback_download_transfer_concurrency = (
        playback_download_transfer_concurrency
        if playback_download_transfer_concurrency is not None
        else current.playback_download_transfer_concurrency
    )
    if next_playback_download_transfer_concurrency < 1 or next_playback_download_transfer_concurrency > 32:
        raise ValueError("playback_download_transfer_concurrency must be between 1 and 32.")
    set_setting(
        settings,
        key=PLAYBACK_DOWNLOAD_TRANSFER_CONCURRENCY_KEY,
        value=str(next_playback_download_transfer_concurrency),
    )
    return AdminSettings(
        playback_download_transfer_concurrency=next_playback_download_transfer_concurrency
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
