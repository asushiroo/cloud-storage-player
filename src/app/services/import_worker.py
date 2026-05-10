from __future__ import annotations

from queue import Empty, Queue
from threading import Event, Lock, Thread

from app.core.config import Settings
from app.repositories.import_jobs import (
    get_import_job,
    list_import_job_ids_by_status,
    mark_import_job_failed,
    mark_running_import_jobs_interrupted,
)
from app.services.background_jobs import process_background_job


class ImportWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._queue: Queue[int] = Queue()
        self._scheduled_job_ids: set[int] = set()
        self._processing_job_ids: set[int] = set()
        self._lock = Lock()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._started = False

    def ensure_started(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stop_event.clear()
            self._thread = Thread(
                target=self._run,
                name="cloud-storage-player-import-worker",
                daemon=True,
            )
            self._thread.start()
            mark_running_import_jobs_interrupted(self.settings)
            queued_job_ids = list_import_job_ids_by_status(self.settings, statuses=("queued",))
            for job_id in queued_job_ids:
                self._enqueue_unlocked(job_id)

    def enqueue(self, job_id: int) -> None:
        self.ensure_started()
        with self._lock:
            self._enqueue_unlocked(job_id)

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def _enqueue_unlocked(self, job_id: int) -> None:
        if job_id in self._scheduled_job_ids or job_id in self._processing_job_ids:
            return
        self._scheduled_job_ids.add(job_id)
        self._queue.put(job_id)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                job_id = self._queue.get(timeout=0.25)
            except Empty:
                continue

            with self._lock:
                self._scheduled_job_ids.discard(job_id)
                self._processing_job_ids.add(job_id)

            try:
                process_background_job(self.settings, job_id)
            except Exception as exc:
                if get_import_job(self.settings, job_id) is not None:
                    mark_import_job_failed(self.settings, job_id, error_message=str(exc))
            finally:
                with self._lock:
                    self._processing_job_ids.discard(job_id)
                self._queue.task_done()
