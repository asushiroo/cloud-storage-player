from __future__ import annotations

from app.core.config import Settings
from app.models.settings import PublicSettings
from app.repositories.settings import get_setting, set_setting
from app.services.baidu_oauth import build_baidu_authorize_url, has_baidu_refresh_token

BAIDU_ROOT_PATH_KEY = "baidu_root_path"
CACHE_LIMIT_BYTES_KEY = "cache_limit_bytes"
STORAGE_BACKEND_KEY = "storage_backend"
REMOTE_TRANSFER_CONCURRENCY_KEY = "remote_transfer_concurrency"
DEFAULT_BAIDU_ROOT_PATH = "/apps/CloudStoragePlayer"
DEFAULT_CACHE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
SUPPORTED_STORAGE_BACKENDS = {"mock", "baidu"}


def get_public_settings(settings: Settings) -> PublicSettings:
    baidu_root = get_setting(settings, BAIDU_ROOT_PATH_KEY)
    cache_limit = get_setting(settings, CACHE_LIMIT_BYTES_KEY)
    storage_backend = get_setting(settings, STORAGE_BACKEND_KEY)
    remote_transfer_concurrency = get_setting(settings, REMOTE_TRANSFER_CONCURRENCY_KEY)
    return PublicSettings(
        baidu_root_path=baidu_root.value if baidu_root else DEFAULT_BAIDU_ROOT_PATH,
        cache_limit_bytes=_parse_cache_limit(cache_limit.value) if cache_limit else DEFAULT_CACHE_LIMIT_BYTES,
        storage_backend=(storage_backend.value if storage_backend else settings.storage_backend).strip().lower(),
        remote_transfer_concurrency=(
            _parse_remote_transfer_concurrency(remote_transfer_concurrency.value)
            if remote_transfer_concurrency
            else settings.remote_transfer_concurrency
        ),
        baidu_authorize_url=build_baidu_authorize_url(settings),
        baidu_has_refresh_token=has_baidu_refresh_token(settings),
    )


def update_public_settings(
    settings: Settings,
    *,
    baidu_root_path: str | None = None,
    cache_limit_bytes: int | None = None,
    storage_backend: str | None = None,
    remote_transfer_concurrency: int | None = None,
) -> PublicSettings:
    current = get_public_settings(settings)
    next_storage_backend = (
        storage_backend.strip().lower() if storage_backend is not None else current.storage_backend
    )
    next_baidu_root_path = (
        baidu_root_path.strip() if baidu_root_path is not None else current.baidu_root_path
    )
    next_cache_limit_bytes = (
        cache_limit_bytes if cache_limit_bytes is not None else current.cache_limit_bytes
    )
    next_remote_transfer_concurrency = (
        remote_transfer_concurrency
        if remote_transfer_concurrency is not None
        else current.remote_transfer_concurrency
    )

    if next_storage_backend not in SUPPORTED_STORAGE_BACKENDS:
        raise ValueError(
            f"storage_backend must be one of: {', '.join(sorted(SUPPORTED_STORAGE_BACKENDS))}."
        )
    if not next_baidu_root_path:
        raise ValueError("baidu_root_path must not be empty.")
    if not next_baidu_root_path.startswith("/"):
        raise ValueError("baidu_root_path must start with '/'.")
    if next_storage_backend == "baidu" and not next_baidu_root_path.startswith("/apps/"):
        raise ValueError("baidu_root_path must start with '/apps/' when storage_backend is baidu.")
    if next_cache_limit_bytes <= 0:
        raise ValueError("cache_limit_bytes must be greater than 0.")
    if next_remote_transfer_concurrency < 1 or next_remote_transfer_concurrency > 32:
        raise ValueError("remote_transfer_concurrency must be between 1 and 32.")

    set_setting(settings, key=BAIDU_ROOT_PATH_KEY, value=next_baidu_root_path)
    set_setting(settings, key=CACHE_LIMIT_BYTES_KEY, value=str(next_cache_limit_bytes))
    set_setting(settings, key=STORAGE_BACKEND_KEY, value=next_storage_backend)
    set_setting(
        settings,
        key=REMOTE_TRANSFER_CONCURRENCY_KEY,
        value=str(next_remote_transfer_concurrency),
    )
    return PublicSettings(
        baidu_root_path=next_baidu_root_path,
        cache_limit_bytes=next_cache_limit_bytes,
        storage_backend=next_storage_backend,
        remote_transfer_concurrency=next_remote_transfer_concurrency,
        baidu_authorize_url=build_baidu_authorize_url(settings),
        baidu_has_refresh_token=has_baidu_refresh_token(settings),
    )


def get_remote_transfer_concurrency(settings: Settings) -> int:
    stored = get_setting(settings, REMOTE_TRANSFER_CONCURRENCY_KEY)
    if stored is None:
        return settings.remote_transfer_concurrency
    return _parse_remote_transfer_concurrency(stored.value)


def _parse_cache_limit(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError("cache_limit_bytes must be stored as an integer.") from exc
    if parsed <= 0:
        raise ValueError("cache_limit_bytes must be greater than 0.")
    return parsed


def _parse_remote_transfer_concurrency(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError("remote_transfer_concurrency must be stored as an integer.") from exc
    if parsed < 1 or parsed > 32:
        raise ValueError("remote_transfer_concurrency must be between 1 and 32.")
    return parsed
