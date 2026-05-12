from __future__ import annotations

from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.services.settings import get_segment_cache_root


def serialize_local_staging_path(settings: Settings, path: Path) -> str:
    cache_root = get_segment_cache_root(settings).resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    try:
        suffix = resolved_path.relative_to(cache_root)
    except ValueError as exc:
        raise ValueError(f"Segment path is outside cache root: {resolved_path}") from exc
    return suffix.as_posix()


def resolve_segment_local_staging_path(
    settings: Settings,
    *,
    video_id: int,
    segment_index: int,
    local_staging_path: str | None,
) -> Path:
    if local_staging_path:
        return resolve_local_staging_path(settings, local_staging_path)
    return build_segment_local_staging_path(
        settings,
        video_id=video_id,
        segment_index=segment_index,
    )


def resolve_local_staging_path(settings: Settings, local_staging_path: str) -> Path:
    suffix = normalize_local_staging_suffix(local_staging_path)
    cache_root = get_segment_cache_root(settings)
    return cache_root / Path(*PurePosixPath(suffix).parts)


def build_segment_local_staging_path(
    settings: Settings,
    *,
    video_id: int,
    segment_index: int,
) -> Path:
    cache_root = get_segment_cache_root(settings)
    suffix = build_segment_local_staging_suffix(video_id=video_id, segment_index=segment_index)
    return cache_root / Path(*PurePosixPath(suffix).parts)


def build_segment_local_staging_suffix(*, video_id: int, segment_index: int) -> str:
    return f"{video_id}/segments/{segment_index:06d}.cspseg"


def coerce_local_staging_suffix(
    path_value: str | None,
    *,
    video_id: int,
    segment_index: int,
) -> str:
    if path_value:
        stripped = path_value.strip()
        if stripped:
            try:
                return normalize_local_staging_suffix(stripped)
            except ValueError:
                pass

            normalized = stripped.replace("\\", "/")
            lowered = normalized.casefold()
            token = f"/segments/{video_id}/".casefold()
            token_index = lowered.rfind(token)
            if token_index >= 0:
                suffix_candidate = normalized[token_index + len("/segments/") :]
                return normalize_local_staging_suffix(suffix_candidate)

            fallback_token = f"/{video_id}/segments/".casefold()
            fallback_index = lowered.rfind(fallback_token)
            if fallback_index >= 0:
                suffix_candidate = normalized[fallback_index + 1 :]
                return normalize_local_staging_suffix(suffix_candidate)

            file_name = Path(stripped).name.strip()
            if file_name:
                return normalize_local_staging_suffix(f"{video_id}/segments/{file_name}")

    return build_segment_local_staging_suffix(video_id=video_id, segment_index=segment_index)


def normalize_local_staging_suffix(path_value: str) -> str:
    normalized = path_value.strip().replace("\\", "/")
    if not normalized:
        raise ValueError("local_staging_path must not be empty.")

    suffix = PurePosixPath(normalized)
    if suffix.is_absolute():
        raise ValueError("local_staging_path must be cache-root-relative.")
    if suffix.parts and suffix.parts[0].endswith(":"):
        raise ValueError("local_staging_path must be cache-root-relative.")
    if any(part in {"", ".", ".."} for part in suffix.parts):
        raise ValueError("local_staging_path contains unsupported path segments.")

    return suffix.as_posix()
