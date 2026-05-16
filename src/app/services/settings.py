from __future__ import annotations

from pathlib import Path

from app.core.config import PROJECT_ROOT, Settings
from app.models.settings import PublicSettings
from app.repositories.settings import get_setting, set_setting
from app.services.baidu_oauth import build_baidu_authorize_url, has_baidu_refresh_token

BAIDU_ROOT_PATH_KEY = "baidu_root_path"
CACHE_LIMIT_BYTES_KEY = "cache_limit_bytes"
SEGMENT_CACHE_ROOT_PATH_KEY = "segment_cache_root_path"
STORAGE_BACKEND_KEY = "storage_backend"
REMOTE_TRANSFER_CONCURRENCY_KEY = "remote_transfer_concurrency"
UPLOAD_TRANSFER_CONCURRENCY_KEY = "upload_transfer_concurrency"
DOWNLOAD_TRANSFER_CONCURRENCY_KEY = "download_transfer_concurrency"
DEFAULT_BAIDU_ROOT_PATH = "/apps/CloudStoragePlayer"
DEFAULT_CACHE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
SUPPORTED_STORAGE_BACKENDS = {"mock", "baidu"}


def get_public_settings(settings: Settings) -> PublicSettings:
    baidu_root = get_setting(settings, BAIDU_ROOT_PATH_KEY)
    cache_limit = get_setting(settings, CACHE_LIMIT_BYTES_KEY)
    storage_backend = get_setting(settings, STORAGE_BACKEND_KEY)
    upload_transfer_concurrency = get_setting(settings, UPLOAD_TRANSFER_CONCURRENCY_KEY)
    download_transfer_concurrency = get_setting(settings, DOWNLOAD_TRANSFER_CONCURRENCY_KEY)
    return PublicSettings(
        baidu_root_path=baidu_root.value if baidu_root else DEFAULT_BAIDU_ROOT_PATH,
        cache_limit_bytes=_parse_cache_limit(cache_limit.value) if cache_limit else DEFAULT_CACHE_LIMIT_BYTES,
        segment_cache_root_path=str(get_segment_cache_root(settings)),
        storage_backend=(storage_backend.value if storage_backend else settings.storage_backend).strip().lower(),
        upload_transfer_concurrency=_resolve_upload_transfer_concurrency(
            settings,
            stored_value=upload_transfer_concurrency.value if upload_transfer_concurrency else None,
        ),
        download_transfer_concurrency=_resolve_download_transfer_concurrency(
            settings,
            stored_value=download_transfer_concurrency.value if download_transfer_concurrency else None,
        ),
        baidu_authorize_url=build_baidu_authorize_url(settings),
        baidu_has_refresh_token=has_baidu_refresh_token(settings),
    )


def update_public_settings(
    settings: Settings,
    *,
    baidu_root_path: str | None = None,
    cache_limit_bytes: int | None = None,
    segment_cache_root_path: str | None = None,
    storage_backend: str | None = None,
    upload_transfer_concurrency: int | None = None,
    download_transfer_concurrency: int | None = None,
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
    next_segment_cache_root_path = (
        segment_cache_root_path.strip()
        if segment_cache_root_path is not None
        else current.segment_cache_root_path
    )
    next_upload_transfer_concurrency = (
        upload_transfer_concurrency
        if upload_transfer_concurrency is not None
        else current.upload_transfer_concurrency
    )
    next_download_transfer_concurrency = (
        download_transfer_concurrency
        if download_transfer_concurrency is not None
        else current.download_transfer_concurrency
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
    if not next_segment_cache_root_path:
        raise ValueError("segment_cache_root_path must not be empty.")
    resolved_segment_cache_root = resolve_segment_cache_root_path(next_segment_cache_root_path)
    if resolved_segment_cache_root.exists() and not resolved_segment_cache_root.is_dir():
        raise ValueError("segment_cache_root_path must point to a directory.")
    if next_upload_transfer_concurrency < 1 or next_upload_transfer_concurrency > 32:
        raise ValueError("upload_transfer_concurrency must be between 1 and 32.")
    if next_download_transfer_concurrency < 1 or next_download_transfer_concurrency > 32:
        raise ValueError("download_transfer_concurrency must be between 1 and 32.")

    set_setting(settings, key=BAIDU_ROOT_PATH_KEY, value=next_baidu_root_path)
    set_setting(settings, key=CACHE_LIMIT_BYTES_KEY, value=str(next_cache_limit_bytes))
    set_setting(
        settings,
        key=SEGMENT_CACHE_ROOT_PATH_KEY,
        value=serialize_segment_cache_root_path(resolved_segment_cache_root),
    )
    set_setting(settings, key=STORAGE_BACKEND_KEY, value=next_storage_backend)
    set_setting(
        settings,
        key=UPLOAD_TRANSFER_CONCURRENCY_KEY,
        value=str(next_upload_transfer_concurrency),
    )
    set_setting(
        settings,
        key=DOWNLOAD_TRANSFER_CONCURRENCY_KEY,
        value=str(next_download_transfer_concurrency),
    )
    return PublicSettings(
        baidu_root_path=next_baidu_root_path,
        cache_limit_bytes=next_cache_limit_bytes,
        segment_cache_root_path=str(resolved_segment_cache_root),
        storage_backend=next_storage_backend,
        upload_transfer_concurrency=next_upload_transfer_concurrency,
        download_transfer_concurrency=next_download_transfer_concurrency,
        baidu_authorize_url=build_baidu_authorize_url(settings),
        baidu_has_refresh_token=has_baidu_refresh_token(settings),
    )


def get_segment_cache_root(settings: Settings) -> Path:
    stored = get_setting(settings, SEGMENT_CACHE_ROOT_PATH_KEY)
    if stored is None:
        return settings.segment_staging_dir.resolve(strict=False)
    return resolve_segment_cache_root_path(stored.value)


def resolve_segment_cache_root_path(path_value: str) -> Path:
    normalized = path_value.strip()
    if not normalized:
        raise ValueError("segment_cache_root_path must not be empty.")

    configured = Path(normalized)
    if configured.is_absolute():
        return configured.resolve(strict=False)
    return (PROJECT_ROOT / configured).resolve(strict=False)


def serialize_segment_cache_root_path(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    project_root = PROJECT_ROOT.resolve(strict=False)
    try:
        return resolved_path.relative_to(project_root).as_posix()
    except ValueError:
        return str(resolved_path)


def get_upload_transfer_concurrency(settings: Settings) -> int:
    stored = get_setting(settings, UPLOAD_TRANSFER_CONCURRENCY_KEY)
    return _resolve_upload_transfer_concurrency(
        settings,
        stored_value=stored.value if stored else None,
    )


def get_download_transfer_concurrency(settings: Settings) -> int:
    stored = get_setting(settings, DOWNLOAD_TRANSFER_CONCURRENCY_KEY)
    return _resolve_cache_download_transfer_concurrency(
        settings,
        stored_value=stored.value if stored else None,
    )


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


def _resolve_upload_transfer_concurrency(settings: Settings, *, stored_value: str | None) -> int:
    if stored_value is not None:
        return _parse_named_transfer_concurrency(
            stored_value,
            setting_name="upload_transfer_concurrency",
        )
    legacy = get_setting(settings, REMOTE_TRANSFER_CONCURRENCY_KEY)
    if legacy is not None:
        return _parse_remote_transfer_concurrency(legacy.value)
    return settings.effective_upload_transfer_concurrency


def _resolve_download_transfer_concurrency(settings: Settings, *, stored_value: str | None) -> int:
    return _resolve_cache_download_transfer_concurrency(
        settings,
        stored_value=stored_value,
    )


def _resolve_cache_download_transfer_concurrency(settings: Settings, *, stored_value: str | None) -> int:
    if stored_value is not None:
        return _parse_named_transfer_concurrency(
            stored_value,
            setting_name="download_transfer_concurrency",
        )
    legacy = get_setting(settings, REMOTE_TRANSFER_CONCURRENCY_KEY)
    if legacy is not None:
        return _parse_remote_transfer_concurrency(legacy.value)
    return settings.effective_download_transfer_concurrency


def _parse_named_transfer_concurrency(value: str, *, setting_name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{setting_name} must be stored as an integer.") from exc
    if parsed < 1 or parsed > 32:
        raise ValueError(f"{setting_name} must be between 1 and 32.")
    return parsed
