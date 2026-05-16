from __future__ import annotations

import base64
import binascii
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.config import Settings
from app.models.library import Video
from app.media.covers import CoverExtractionError, transcode_image_to_avif
from app.repositories.videos import get_video, request_video_manifest_sync, update_video_artwork_paths
from app.services.artwork_storage import (
    build_poster_file_name,
    delete_video_artwork_files,
    store_encrypted_artwork_file,
)
from app.services.video_manifest_sync import can_rewrite_video_manifests, rewrite_local_video_manifests

_IMAGE_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/avif": "avif",
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

    delete_video_artwork_files(settings, video_id=video_id, kind="cover")
    updated_video = update_video_artwork_paths(
        settings,
        video_id,
        cover_path=None,
        poster_path=_write_poster_artwork_file(settings, video_id=video_id, data_url=poster_source),
        has_custom_poster=True,
    )
    if not can_rewrite_video_manifests(settings, video_id):
        return updated_video
    request_video_manifest_sync(settings, video_id)
    return rewrite_local_video_manifests(settings, video_id)


def _write_poster_artwork_file(settings: Settings, *, video_id: int, data_url: str) -> str:
    media_type, payload = _parse_data_url(data_url)
    extension = _IMAGE_EXTENSIONS.get(media_type)
    if extension is None:
        raise VideoArtworkValidationError(f"Unsupported artwork mime type: {media_type}")

    delete_video_artwork_files(settings, video_id=video_id, kind="poster")
    try:
        decoded_bytes = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VideoArtworkValidationError("Artwork payload is not valid base64 data.") from exc

    poster_file_name = build_poster_file_name(video_id)
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        source_path = temp_dir / f"source.{extension}"
        source_path.write_bytes(decoded_bytes)
        transcoded_path = temp_dir / poster_file_name
        if extension == "avif":
            transcoded_path.write_bytes(decoded_bytes)
        else:
            try:
                transcode_image_to_avif(
                    source_path,
                    transcoded_path,
                    ffmpeg_binary=settings.ffmpeg_binary,
                )
            except CoverExtractionError as exc:
                raise VideoArtworkValidationError(str(exc)) from exc
        return store_encrypted_artwork_file(
            settings,
            file_name=poster_file_name,
            source_path=transcoded_path,
        )


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
