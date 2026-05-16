from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings
from app.repositories.import_jobs import ACTIVE_JOB_STATUSES, list_import_jobs
from app.repositories.videos import list_dirty_manifest_videos


@dataclass(slots=True)
class ShutdownState:
    active_job_descriptions: list[str] = field(default_factory=list)
    pending_manifest_sync_videos: list[str] = field(default_factory=list)
    pending_custom_poster_sync_videos: list[str] = field(default_factory=list)

    @property
    def has_pending_work(self) -> bool:
        return bool(
            self.active_job_descriptions
            or self.pending_manifest_sync_videos
            or self.pending_custom_poster_sync_videos
        )


def collect_shutdown_state(settings: Settings) -> ShutdownState:
    active_jobs = [
        f"{job.job_kind}:{job.task_name} [{job.status}]"
        for job in list_import_jobs(settings)
        if job.status in ACTIVE_JOB_STATUSES
    ]
    dirty_videos = list_dirty_manifest_videos(settings)
    pending_manifest_sync_videos = [f"{video.id}:{video.title}" for video in dirty_videos]
    pending_custom_poster_sync_videos = [
        f"{video.id}:{video.title}"
        for video in dirty_videos
        if video.has_custom_poster
    ]
    return ShutdownState(
        active_job_descriptions=active_jobs,
        pending_manifest_sync_videos=pending_manifest_sync_videos,
        pending_custom_poster_sync_videos=pending_custom_poster_sync_videos,
    )
