from __future__ import annotations

from app.core.tags import normalize_tags
from app.models.library import Video
from app.repositories.videos import (
    get_video,
    get_video_by_title,
    update_video_fields,
    update_video_metadata,
)
from app.services.video_manifest_sync import can_rewrite_video_manifests, rewrite_local_video_manifests


class VideoMetadataValidationError(ValueError):
    """Raised when a video metadata update request is invalid."""


def update_video_metadata_and_rewrite_manifest(
    settings,
    video_id: int,
    *,
    title: str,
    tags: list[str] | None,
) -> Video:
    video = get_video(settings, video_id)
    if video is None:
        raise VideoMetadataValidationError(f"Video not found: {video_id}")

    normalized_title = title.strip()
    if not normalized_title:
        raise VideoMetadataValidationError("Video title must not be empty.")

    existing_with_title = get_video_by_title(settings, normalized_title)
    if existing_with_title is not None and existing_with_title.id != video_id:
        raise VideoMetadataValidationError("Video title already exists.")

    normalized_tags = normalize_tags(tags)
    if not can_rewrite_video_manifests(settings, video_id):
        return update_video_fields(
            settings,
            video_id,
            title=normalized_title,
            tags=normalized_tags,
        )

    updated_video = update_video_metadata(settings, video_id, title=normalized_title, tags=normalized_tags)
    return rewrite_local_video_manifests(settings, updated_video.id)
