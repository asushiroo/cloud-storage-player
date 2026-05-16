from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.config import Settings
from app.media.covers import CoverExtractionError, extract_poster_at_ratio
from app.media.probe import MediaProbeError, probe_video
from app.repositories.videos import list_videos, update_video_artwork_paths
from app.services.artwork_storage import (
    build_poster_file_name,
    delete_video_artwork_files,
    store_encrypted_artwork_file,
)


@dataclass(slots=True)
class PosterRebuildResult:
    rebuilt_count: int
    skipped_count: int
    failed_count: int
    failed_video_ids: list[int]


def rebuild_all_video_posters(settings: Settings) -> PosterRebuildResult:
    rebuilt_count = 0
    skipped_count = 0
    failed_count = 0
    failed_video_ids: list[int] = []

    for video in list_videos(settings):
        if not video.source_path:
            skipped_count += 1
            continue
        source = Path(video.source_path)
        if not source.exists() or not source.is_file():
            skipped_count += 1
            continue
        try:
            metadata = probe_video(source, ffprobe_binary=settings.ffprobe_binary)
            poster_file_name = build_poster_file_name(video.id)
            delete_video_artwork_files(settings, video_id=video.id, kind="poster")
            with TemporaryDirectory() as temp_dir_name:
                temp_output = Path(temp_dir_name) / poster_file_name
                extract_poster_at_ratio(
                    source,
                    temp_output,
                    duration_seconds=metadata.duration_seconds,
                    position_ratio=1 / 3,
                    ffmpeg_binary=settings.ffmpeg_binary,
                )
                poster_path = store_encrypted_artwork_file(
                    settings,
                    file_name=poster_file_name,
                    source_path=temp_output,
                )
            update_video_artwork_paths(
                settings,
                video.id,
                cover_path=None,
                poster_path=poster_path,
                has_custom_poster=False,
            )
            rebuilt_count += 1
        except (MediaProbeError, CoverExtractionError, OSError):
            failed_count += 1
            failed_video_ids.append(video.id)

    return PosterRebuildResult(
        rebuilt_count=rebuilt_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        failed_video_ids=failed_video_ids,
    )
