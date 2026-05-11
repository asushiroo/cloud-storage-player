from __future__ import annotations

from threading import Event, Thread

from app.core.config import Settings
from app.services.video_manifest_sync import sync_due_video_manifests


class ManifestSyncScheduler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=self._run,
            name="cloud-storage-player-manifest-sync",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop_event.wait(timeout=30.0):
            sync_due_video_manifests(self.settings)
