from __future__ import annotations

from app.core.config import Settings
from app.models.settings import PublicSettings
from app.repositories.settings import get_setting, set_setting

BAIDU_ROOT_PATH_KEY = "baidu_root_path"
CACHE_LIMIT_BYTES_KEY = "cache_limit_bytes"
DEFAULT_BAIDU_ROOT_PATH = "/CloudStoragePlayer"
DEFAULT_CACHE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024


def get_public_settings(settings: Settings) -> PublicSettings:
    baidu_root = get_setting(settings, BAIDU_ROOT_PATH_KEY)
    cache_limit = get_setting(settings, CACHE_LIMIT_BYTES_KEY)
    return PublicSettings(
        baidu_root_path=baidu_root.value if baidu_root else DEFAULT_BAIDU_ROOT_PATH,
        cache_limit_bytes=_parse_cache_limit(cache_limit.value) if cache_limit else DEFAULT_CACHE_LIMIT_BYTES,
    )


def update_public_settings(
    settings: Settings,
    *,
    baidu_root_path: str | None = None,
    cache_limit_bytes: int | None = None,
) -> PublicSettings:
    current = get_public_settings(settings)
    next_baidu_root_path = (
        baidu_root_path.strip() if baidu_root_path is not None else current.baidu_root_path
    )
    next_cache_limit_bytes = (
        cache_limit_bytes if cache_limit_bytes is not None else current.cache_limit_bytes
    )

    if not next_baidu_root_path:
        raise ValueError("baidu_root_path must not be empty.")
    if next_cache_limit_bytes <= 0:
        raise ValueError("cache_limit_bytes must be greater than 0.")

    set_setting(settings, key=BAIDU_ROOT_PATH_KEY, value=next_baidu_root_path)
    set_setting(settings, key=CACHE_LIMIT_BYTES_KEY, value=str(next_cache_limit_bytes))
    return PublicSettings(
        baidu_root_path=next_baidu_root_path,
        cache_limit_bytes=next_cache_limit_bytes,
    )


def _parse_cache_limit(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError("cache_limit_bytes must be stored as an integer.") from exc
    if parsed <= 0:
        raise ValueError("cache_limit_bytes must be greater than 0.")
    return parsed
