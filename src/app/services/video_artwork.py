from __future__ import annotations

import base64

from app.core.config import Settings
from app.models.library import Video
from app.repositories.videos import get_video, update_video_artwork_paths

_IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class VideoArtworkNotFoundError(RuntimeError):
    """Raised when the target video does not exist."""


class VideoArtworkValidationError(ValueError):
    """Raised when the artwork payload is invalid."""


def replace_video_artwork(
    settings: Settings,
    video_id: int,
    *,
    cover_data_url: str | None = None,
    poster_data_url: str | None = None,
) -> Video:
    if cover_data_url is None and poster_data_url is None:
        raise VideoArtworkValidationError("At least one artwork image is required.")

    video = get_video(settings, video_id)
    if video is None:
        raise VideoArtworkNotFoundError(f"Video not found: {video_id}")

    poster_source = poster_data_url or cover_data_url
    if poster_source is None:
        raise VideoArtworkValidationError("At least one artwork image is required.")

    _delete_existing_artwork_files(settings, video_id=video_id, kind="cover")
    return update_video_artwork_paths(
        settings,
        video_id,
        cover_path=None,
        poster_path=_write_artwork_file(settings, video_id=video_id, kind="poster", data_url=poster_source),
    )


def _write_artwork_file(settings: Settings, *, video_id: int, kind: str, data_url: str) -> str:
    media_type, payload = _parse_data_url(data_url)
    extension = _IMAGE_EXTENSIONS.get(media_type)
    if extension is None:
        raise VideoArtworkValidationError(f"Unsupported artwork mime type: {media_type}")

    _delete_existing_artwork_files(settings, video_id=video_id, kind=kind)
    file_name = f"{video_id}-{kind}.{extension}"
    output_path = settings.covers_dir / file_name
    output_path.write_bytes(base64.b64decode(payload, validate=True))
    return f"/covers/{file_name}"


def _parse_data_url(data_url: str) -> tuple[str, str]:
    prefix = "data:"
    if not data_url.startswith(prefix):
        raise VideoArtworkValidationError("Artwork payload must be a data URL.")
    header, _, payload = data_url.partition(",")
    if not payload:
        raise VideoArtworkValidationError("Artwork payload is missing image data.")
    if ";base64" not in header:
        raise VideoArtworkValidationError("Artwork payload must be base64 encoded.")
    media_type = header[len(prefix) : header.index(";")]
    return media_type, payload


def _delete_existing_artwork_files(settings: Settings, *, video_id: int, kind: str) -> None:
    for extension in _IMAGE_EXTENSIONS.values():
        candidate = settings.covers_dir / f"{video_id}-{kind}.{extension}"
        candidate.unlink(missing_ok=True)
