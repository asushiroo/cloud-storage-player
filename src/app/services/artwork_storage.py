from __future__ import annotations

from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.core.keys import load_content_key, load_or_create_content_key
from app.media.artwork_crypto import crypt_artwork_bytes

ARTWORK_ROUTE_PREFIX = "/api/artwork"
_POSTER_EXTENSION = "avif"
_ENCRYPTED_SUFFIX = ".enc"
_SUPPORTED_MEDIA_TYPES = {
    ".avif": "image/avif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
_LEGACY_ARTWORK_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "avif")


def build_poster_file_name(video_id: int) -> str:
    return f"{video_id}-poster.{_POSTER_EXTENSION}"


def build_artwork_web_path(file_name: str) -> str:
    _validate_artwork_name(file_name)
    return f"{ARTWORK_ROUTE_PREFIX}/{file_name}"


def store_encrypted_artwork_bytes(
    settings: Settings,
    *,
    file_name: str,
    payload: bytes,
) -> str:
    settings.covers_dir.mkdir(parents=True, exist_ok=True)
    encrypted_path = encrypted_artwork_path(settings, file_name=file_name)
    encrypted_path.write_bytes(
        crypt_artwork_bytes(
            payload,
            load_or_create_content_key(settings),
            artwork_name=file_name,
        )
    )
    return build_artwork_web_path(file_name)


def store_encrypted_artwork_file(
    settings: Settings,
    *,
    file_name: str,
    source_path: Path,
) -> str:
    return store_encrypted_artwork_bytes(
        settings,
        file_name=file_name,
        payload=source_path.read_bytes(),
    )


def read_artwork_bytes(settings: Settings, *, artwork_name: str) -> tuple[bytes, str]:
    file_name = _validate_artwork_name(artwork_name)
    resolved_file_name = _resolve_existing_artwork_file_name(settings, file_name=file_name)
    media_type = guess_artwork_media_type(resolved_file_name)
    encrypted_path = encrypted_artwork_path(settings, file_name=resolved_file_name)
    if encrypted_path.exists():
        encrypted_bytes = encrypted_path.read_bytes()
        return (
            crypt_artwork_bytes(
                encrypted_bytes,
                load_content_key(settings),
                artwork_name=resolved_file_name,
            ),
            media_type,
        )

    plain_path = settings.covers_dir / resolved_file_name
    if plain_path.exists():
        return plain_path.read_bytes(), media_type

    raise FileNotFoundError(resolved_file_name)


def encrypted_artwork_path(settings: Settings, *, file_name: str) -> Path:
    safe_name = _validate_artwork_name(file_name)
    return settings.covers_dir / f"{safe_name}{_ENCRYPTED_SUFFIX}"


def resolve_artwork_storage_paths(settings: Settings, *, artwork_path: str) -> list[Path]:
    if artwork_path.startswith(f"{ARTWORK_ROUTE_PREFIX}/"):
        file_name = artwork_path[len(f"{ARTWORK_ROUTE_PREFIX}/") :]
        return [encrypted_artwork_path(settings, file_name=file_name)]

    file_name = Path(artwork_path).name
    if not file_name:
        return []
    return [settings.covers_dir / file_name]


def delete_video_artwork_files(settings: Settings, *, video_id: int, kind: str) -> None:
    for extension in _LEGACY_ARTWORK_EXTENSIONS:
        plain_candidate = settings.covers_dir / f"{video_id}-{kind}.{extension}"
        plain_candidate.unlink(missing_ok=True)
        encrypted_candidate = settings.covers_dir / f"{video_id}-{kind}.{extension}{_ENCRYPTED_SUFFIX}"
        encrypted_candidate.unlink(missing_ok=True)


def guess_artwork_media_type(file_name: str) -> str:
    media_type = _SUPPORTED_MEDIA_TYPES.get(Path(file_name).suffix.casefold())
    if media_type is None:
        raise FileNotFoundError(file_name)
    return media_type


def _resolve_existing_artwork_file_name(settings: Settings, *, file_name: str) -> str:
    encrypted = encrypted_artwork_path(settings, file_name=file_name)
    plain = settings.covers_dir / file_name
    if encrypted.exists() or plain.exists():
        return file_name

    # Backward-compatibility: legacy poster URLs may still reference *.jpg while storage is AVIF.
    if file_name.endswith("-poster.jpg"):
        candidate = f"{Path(file_name).stem}.avif"
        candidate_encrypted = encrypted_artwork_path(settings, file_name=candidate)
        candidate_plain = settings.covers_dir / candidate
        if candidate_encrypted.exists() or candidate_plain.exists():
            return candidate

    return file_name


def _validate_artwork_name(file_name: str) -> str:
    normalized_name = file_name.strip()
    if (
        not normalized_name
        or PurePosixPath(normalized_name).name != normalized_name
        or "\\" in normalized_name
    ):
        raise FileNotFoundError(file_name)
    return normalized_name
