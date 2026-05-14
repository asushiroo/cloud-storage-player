from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.repositories.videos import list_videos
from app.services.manifests import local_manifest_path
from app.services.settings import get_public_settings


@dataclass(slots=True)
class CacheEntry:
    video_id: int
    created_at: str
    cache_priority: float
    total_size_bytes: int
    segment_dir: Path
    keep_segments: bool


@dataclass(slots=True)
class CacheEvictionResult:
    evicted_video_ids: list[int]
    total_size_before_bytes: int
    total_size_after_bytes: int
    cache_limit_bytes: int

    @property
    def reclaimed_bytes(self) -> int:
        return max(self.total_size_before_bytes - self.total_size_after_bytes, 0)


def enforce_cache_limit(
    settings: Settings,
    *,
    protect_video_ids: set[int] | None = None,
) -> CacheEvictionResult:
    cache_limit_bytes = get_public_settings(settings).cache_limit_bytes
    protected_ids = protect_video_ids or set()
    entries = _collect_cache_entries(settings, protected_ids=protected_ids)
    total_size_before = sum(entry.total_size_bytes for entry in entries)
    if total_size_before <= cache_limit_bytes:
        return CacheEvictionResult(
            evicted_video_ids=[],
            total_size_before_bytes=total_size_before,
            total_size_after_bytes=total_size_before,
            cache_limit_bytes=cache_limit_bytes,
        )

    evicted_ids: list[int] = []
    total_size_after = total_size_before
    for entry in _iter_eviction_candidates(entries):
        if total_size_after <= cache_limit_bytes:
            break
        reclaimed = _evict_cache_entry(entry)
        if reclaimed <= 0:
            continue
        total_size_after -= reclaimed
        evicted_ids.append(entry.video_id)
        _refresh_cache_entry(settings, video_id=entry.video_id)

    return CacheEvictionResult(
        evicted_video_ids=evicted_ids,
        total_size_before_bytes=total_size_before,
        total_size_after_bytes=max(total_size_after, 0),
        cache_limit_bytes=cache_limit_bytes,
    )


def _collect_cache_entries(
    settings: Settings,
    *,
    protected_ids: set[int],
) -> list[CacheEntry]:
    entries: list[CacheEntry] = []
    videos_by_id = {video.id: video for video in list_videos(settings)}
    for video_id, video in videos_by_id.items():
        segment_dir = _segment_dir_for_video(settings, video_id=video_id)
        if not segment_dir.exists():
            continue
        total_size = _directory_size_bytes(segment_dir)
        if total_size <= 0:
            continue
        entries.append(
            CacheEntry(
                video_id=video_id,
                created_at=video.created_at,
                cache_priority=video.cache_priority,
                total_size_bytes=total_size,
                segment_dir=segment_dir,
                keep_segments=video_id in protected_ids,
            )
        )
    return entries


def _iter_eviction_candidates(entries: list[CacheEntry]) -> list[CacheEntry]:
    # Rule 1: never evict currently importing/newly uploaded entries first.
    # Rule 2: among existing cache, evict lower-priority entries first.
    # Rule 3: if priority ties, older uploads are evicted before newer uploads.
    return sorted(
        (entry for entry in entries if not entry.keep_segments),
        key=lambda entry: (entry.cache_priority, entry.created_at, entry.video_id),
    )


def _evict_cache_entry(entry: CacheEntry) -> int:
    reclaimed = _directory_size_bytes(entry.segment_dir)
    if reclaimed <= 0:
        return 0
    shutil.rmtree(entry.segment_dir, ignore_errors=True)
    return reclaimed


def _segment_dir_for_video(settings: Settings, *, video_id: int) -> Path:
    return local_manifest_path(settings, video_id=video_id).parent / "segments"


def _directory_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        total += file_path.stat().st_size
    return total


def _refresh_cache_entry(settings: Settings, *, video_id: int) -> None:
    from app.services.cache import refresh_video_cache_entry

    refresh_video_cache_entry(settings, video_id=video_id)
