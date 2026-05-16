from __future__ import annotations

import sys
import time

import httpx

from app.core.config import get_settings
from app.services.runtime_control_client import fetch_shutdown_state, request_shutdown
from app.services.runtime_metadata import delete_runtime_metadata, read_runtime_metadata


def main() -> int:
    settings = get_settings()
    metadata = read_runtime_metadata(settings)
    if metadata is None:
        print("Cloud Storage Player is not running.")
        return 1

    try:
        state = fetch_shutdown_state(port=metadata.port, control_token=metadata.control_token)
    except httpx.HTTPError as exc:
        print(f"Failed to query runtime shutdown state: {exc}", file=sys.stderr)
        return 1

    if state.has_pending_work:
        print("Shutdown blocked because unfinished work still exists:")
        for item in state.active_jobs:
            print(f"- active job: {item}")
        for item in state.pending_manifest_sync_videos:
            print(f"- pending manifest sync: {item}")
        for item in state.pending_custom_poster_sync_videos:
            print(f"- pending custom poster sync: {item}")
        return 2

    try:
        request_shutdown(port=metadata.port, control_token=metadata.control_token)
    except httpx.HTTPError as exc:
        print(f"Failed to request shutdown: {exc}", file=sys.stderr)
        return 1

    for _ in range(40):
        time.sleep(0.25)
        try:
            fetch_shutdown_state(port=metadata.port, control_token=metadata.control_token)
        except httpx.HTTPError:
            delete_runtime_metadata(settings)
            print("Cloud Storage Player stopped.")
            return 0

    print("Shutdown request was sent, but the process is still responding.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
