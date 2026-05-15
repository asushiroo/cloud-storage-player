from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread
from time import perf_counter, time_ns
from typing import Callable
from uuid import uuid4

from app.core.config import Settings
from app.models.segments import VideoSegment
from app.repositories.video_segments import update_video_segment_local_staging_path
from app.services.manifests import local_segment_path
from app.services.remote_transfers import TransferResult, run_bounded_transfers
from app.services.segment_local_paths import (
    resolve_segment_local_staging_path,
    serialize_local_staging_path,
)
from app.services.settings import get_download_transfer_concurrency
from app.storage.base import StorageBackend
from app.storage.factory import build_storage_backend

logger = logging.getLogger(__name__)

_PREFETCH_WINDOW_SIZE = 5
_CACHE_WRITE_WORKER_COUNT = 4
_sessions_lock = Lock()
_prefetch_sessions: dict[int, "SegmentPrefetchSession"] = {}
_cache_write_executor = ThreadPoolExecutor(
    max_workers=_CACHE_WRITE_WORKER_COUNT,
    thread_name_prefix="cloud-storage-player-cache-write",
)
_playback_cache_registry = None


@dataclass(slots=True)
class DownloadedSegmentPayload:
    segment: VideoSegment
    payload: bytes
    transfer_result: TransferResult[VideoSegment]


@dataclass(slots=True)
class SegmentPrefetchSession:
    settings: Settings
    video_id: int
    ordered_segments: list[VideoSegment]
    storage_backend_factory: Callable[[], StorageBackend] | None = None
    stop_event: Event = field(default_factory=Event)
    lock: Lock = field(default_factory=Lock)
    thread: Thread | None = None
    active_segment_index: int = -1
    next_segment_index: int = 0
    consumer_count: int = 0
    completed_segment_indexes: set[int] = field(default_factory=set)
    inflight_segment_indexes: set[int] = field(default_factory=set)

    def start(self) -> None:
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                return
            self.thread = Thread(
                target=self._run,
                name=f"cloud-storage-player-prefetch-{self.video_id}",
                daemon=True,
            )
            self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def request_prefetch(self, *, current_segment_index: int) -> None:
        with self.lock:
            self.active_segment_index = max(self.active_segment_index, current_segment_index)
            self.next_segment_index = max(self.next_segment_index, self.active_segment_index + 1)
        self.start()

    def acquire(self) -> None:
        with self.lock:
            self.consumer_count += 1

    def release(self) -> None:
        with self.lock:
            self.consumer_count = max(0, self.consumer_count - 1)
            if self.consumer_count == 0:
                self.stop_event.set()

    def _run(self) -> None:
        storage = (
            self.storage_backend_factory()
            if self.storage_backend_factory is not None
            else build_storage_backend(self.settings)
        )
        try:
            while not self.stop_event.is_set():
                batch = self._next_batch()
                if not batch:
                    if self._is_finished():
                        return
                    self.stop_event.wait(0.1)
                    continue
                try:
                    run_bounded_transfers(
                        self.settings,
                        job_id=None,
                        tasks=batch,
                        transfer_func=lambda segment: cache_remote_segment(
                            self.settings,
                            segment,
                            storage_backend=storage,
                        ),
                        concurrency=min(
                            get_download_transfer_concurrency(self.settings),
                            _PREFETCH_WINDOW_SIZE,
                        ),
                        stop_event=self.stop_event,
                        on_result=self._mark_completed,
                    )
                except Exception as exc:
                    logger.warning(
                        "Background segment prefetch failed for video %s: %s",
                        self.video_id,
                        exc,
                    )
                    return
        finally:
            close = getattr(storage, "close", None)
            if callable(close):
                close()
            with _sessions_lock:
                current = _prefetch_sessions.get(self.video_id)
                if current is self:
                    _prefetch_sessions.pop(self.video_id, None)

    def _next_batch(self) -> list[VideoSegment]:
        with self.lock:
            if self.active_segment_index < 0:
                return []
            if self.inflight_segment_indexes:
                return []
            remaining_capacity = _PREFETCH_WINDOW_SIZE - len(self.inflight_segment_indexes)
            if remaining_capacity <= 0:
                return []

            window_start = max(self.next_segment_index, self.active_segment_index + 1)
            batch: list[VideoSegment] = []
            for segment in self.ordered_segments:
                if segment.segment_index < window_start:
                    continue
                if segment.segment_index in self.completed_segment_indexes:
                    continue
                if segment.segment_index in self.inflight_segment_indexes:
                    continue
                if not segment.cloud_path:
                    continue
                if _resolve_segment_cache_path(self.settings, segment).exists():
                    self.completed_segment_indexes.add(segment.segment_index)
                    continue
                self.inflight_segment_indexes.add(segment.segment_index)
                batch.append(segment)
                if len(batch) >= remaining_capacity:
                    break
            if batch:
                self.next_segment_index = batch[-1].segment_index + 1
            return batch

    def _mark_completed(
        self,
        result: TransferResult[VideoSegment],
        _completed_count: int,
        _total_count: int,
    ) -> None:
        with self.lock:
            self.inflight_segment_indexes.discard(result.task.segment_index)
            self.completed_segment_indexes.add(result.task.segment_index)

    def _is_finished(self) -> bool:
        with self.lock:
            if self.active_segment_index < 0:
                return True
            if self.inflight_segment_indexes:
                return False
            window_start = max(self.next_segment_index, self.active_segment_index + 1)
            for segment in self.ordered_segments:
                if segment.segment_index < window_start:
                    continue
                if not segment.cloud_path:
                    continue
                if segment.segment_index in self.completed_segment_indexes:
                    continue
                if _resolve_segment_cache_path(self.settings, segment).exists():
                    self.completed_segment_indexes.add(segment.segment_index)
                    continue
                return False
            return True


def acquire_prefetch_session(
    settings: Settings,
    *,
    video_id: int,
    segments: list[VideoSegment],
    storage_backend_factory: Callable[[], StorageBackend] | None = None,
) -> SegmentPrefetchSession | None:
    remote_segments = [segment for segment in segments if segment.cloud_path]
    if not remote_segments:
        return None

    with _sessions_lock:
        existing = _prefetch_sessions.get(video_id)
        if existing is not None:
            if existing.stop_event.is_set():
                _prefetch_sessions.pop(video_id, None)
            else:
                existing.acquire()
                return existing
        session = SegmentPrefetchSession(
            settings=settings,
            video_id=video_id,
            ordered_segments=sorted(remote_segments, key=lambda segment: segment.segment_index),
            storage_backend_factory=storage_backend_factory,
        )
        session.acquire()
        _prefetch_sessions[video_id] = session
        return session


def release_prefetch_session(video_id: int) -> None:
    with _sessions_lock:
        session = _prefetch_sessions.get(video_id)
    if session is not None:
        session.release()


def cache_remote_segment(
    settings: Settings,
    segment: VideoSegment,
    *,
    storage_backend: StorageBackend | None = None,
) -> TransferResult[VideoSegment]:
    segment_path = _resolve_segment_cache_path(settings, segment)
    if segment_path.exists() and segment_path.is_file():
        _ensure_segment_local_staging_path(settings, segment, segment_path)
        return TransferResult(task=segment, byte_count=0, elapsed_seconds=0.0)

    downloaded = download_remote_segment_payload(
        settings,
        segment,
        storage_backend=storage_backend,
    )
    persist_segment_payload(
        settings,
        segment,
        downloaded.payload,
    )
    return downloaded.transfer_result


def download_remote_segment_payload(
    settings: Settings,
    segment: VideoSegment,
    *,
    storage_backend: StorageBackend | None = None,
) -> DownloadedSegmentPayload:
    if not segment.cloud_path:
        raise FileNotFoundError("Segment cloud path is missing.")

    storage = storage_backend or build_storage_backend(settings)
    should_close = storage_backend is None
    started_at_millis = _current_time_millis()
    started_at = perf_counter()
    try:
        payload = storage.download_bytes(segment.cloud_path)
    except Exception:
        if should_close:
            close = getattr(storage, "close", None)
            if callable(close):
                close()
        raise

    completed_at_millis = _current_time_millis()
    elapsed_seconds = max(perf_counter() - started_at, 0.0)
    if should_close:
        close = getattr(storage, "close", None)
        if callable(close):
            close()

    return DownloadedSegmentPayload(
        segment=segment,
        payload=payload,
        transfer_result=TransferResult(
            task=segment,
            byte_count=len(payload),
            elapsed_seconds=elapsed_seconds,
            started_at_millis=started_at_millis,
            completed_at_millis=completed_at_millis,
        ),
    )


def persist_segment_payload(
    settings: Settings,
    segment: VideoSegment,
    payload: bytes,
) -> None:
    segment_path = _resolve_segment_cache_path(settings, segment)
    if segment_path.exists() and segment_path.is_file():
        _ensure_segment_local_staging_path(settings, segment, segment_path)
        _note_cached_segment(segment.video_id, segment.segment_index)
        return

    segment_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = segment_path.with_name(f"{segment_path.name}.{uuid4().hex}.tmp")
    try:
        temp_path.write_bytes(payload)
        temp_path.replace(segment_path)
    finally:
        temp_path.unlink(missing_ok=True)

    _ensure_segment_local_staging_path(settings, segment, segment_path)
    _note_cached_segment(segment.video_id, segment.segment_index)


def queue_segment_cache_write(
    settings: Settings,
    segment: VideoSegment,
    payload: bytes,
) -> None:
    _cache_write_executor.submit(_persist_segment_payload_background, settings, segment, payload)


def _persist_segment_payload_background(
    settings: Settings,
    segment: VideoSegment,
    payload: bytes,
) -> None:
    try:
        persist_segment_payload(settings, segment, payload)
    except Exception as exc:
        logger.warning(
            "Failed to persist streamed segment %s for video %s: %s",
            segment.segment_index,
            segment.video_id,
            exc,
        )


def _ensure_segment_local_staging_path(
    settings: Settings,
    segment: VideoSegment,
    segment_path: Path,
) -> None:
    stored_path = serialize_local_staging_path(settings, segment_path)
    if segment.local_staging_path == stored_path:
        return
    try:
        update_video_segment_local_staging_path(
            settings,
            segment.id,
            local_staging_path=stored_path,
        )
    except ValueError:
        segment.local_staging_path = stored_path
        return
    segment.local_staging_path = stored_path


def _resolve_segment_cache_path(settings: Settings, segment: VideoSegment) -> Path:
    return resolve_segment_local_staging_path(
        settings,
        video_id=segment.video_id,
        segment_index=segment.segment_index,
        local_staging_path=segment.local_staging_path,
    )


def _current_time_millis() -> int:
    return time_ns() // 1_000_000


def set_playback_cache_registry(registry) -> None:
    global _playback_cache_registry
    _playback_cache_registry = registry


def _note_cached_segment(video_id: int, segment_index: int) -> None:
    if _playback_cache_registry is None:
        return
    try:
        _playback_cache_registry.note_cached_segment(
            video_id=video_id,
            segment_index=segment_index,
        )
    except Exception as exc:
        logger.warning(
            "Failed to note streamed segment cache state for video %s segment %s: %s",
            video_id,
            segment_index,
            exc,
        )
