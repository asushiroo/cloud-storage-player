from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class RuntimeShutdownStatePayload:
    active_jobs: list[str]
    pending_manifest_sync_videos: list[str]
    pending_custom_poster_sync_videos: list[str]
    has_pending_work: bool


def fetch_shutdown_state(*, port: int, control_token: str) -> RuntimeShutdownStatePayload:
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5.0) as client:
        response = client.get(
            "/api/runtime/shutdown-state",
            headers={"x-csp-control-token": control_token},
        )
        response.raise_for_status()
    payload = response.json()
    return RuntimeShutdownStatePayload(
        active_jobs=list(payload.get("active_jobs", [])),
        pending_manifest_sync_videos=list(payload.get("pending_manifest_sync_videos", [])),
        pending_custom_poster_sync_videos=list(payload.get("pending_custom_poster_sync_videos", [])),
        has_pending_work=bool(payload.get("has_pending_work", False)),
    )


def request_shutdown(*, port: int, control_token: str) -> None:
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5.0) as client:
        response = client.post(
            "/api/runtime/shutdown",
            headers={"x-csp-control-token": control_token},
        )
        response.raise_for_status()
