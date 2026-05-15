from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from app.core.config import Settings
from app.services.cache import refresh_video_cache_entry
from app.services.cache_eviction import enforce_cache_limit


@dataclass(slots=True)
class _PlaybackCacheSession:
    video_id: int
    cached_segment_indexes: set[int] = field(default_factory=set)


class PlaybackCacheFlushRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = Lock()
        self._sessions: dict[int, _PlaybackCacheSession] = {}

    def note_cached_segment(self, *, video_id: int, segment_index: int) -> None:
        with self._lock:
            session = self._sessions.get(video_id)
            if session is None:
                session = _PlaybackCacheSession(video_id=video_id)
                self._sessions[video_id] = session
            session.cached_segment_indexes.add(segment_index)

    def flush_video(self, *, video_id: int, segment_indexes: list[int] | None = None) -> None:
        with self._lock:
            session = self._sessions.get(video_id)
            if session is None:
                if not segment_indexes:
                    return
                session = _PlaybackCacheSession(video_id=video_id, cached_segment_indexes=set(segment_indexes))
                self._sessions[video_id] = session
            elif segment_indexes:
                session.cached_segment_indexes.update(segment_indexes)

            should_flush = bool(session.cached_segment_indexes)
            if should_flush:
                self._sessions.pop(video_id, None)

        if not should_flush:
            return
        refresh_video_cache_entry(self._settings, video_id=video_id)
        enforce_cache_limit(self._settings, protect_video_ids={video_id})
