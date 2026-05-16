from __future__ import annotations

from threading import Thread

from fastapi import APIRouter, HTTPException, Request, status

from app.services.shutdown_state import collect_shutdown_state

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.get("/shutdown-state")
def get_shutdown_state(request: Request):
    settings = request.app.state.settings
    _validate_control_token(request)
    state = collect_shutdown_state(settings)
    return {
        "active_jobs": state.active_job_descriptions,
        "pending_manifest_sync_videos": state.pending_manifest_sync_videos,
        "pending_custom_poster_sync_videos": state.pending_custom_poster_sync_videos,
        "has_pending_work": state.has_pending_work,
    }


@router.post("/shutdown", status_code=status.HTTP_202_ACCEPTED)
def request_runtime_shutdown(request: Request):
    settings = request.app.state.settings
    _validate_control_token(request)
    state = collect_shutdown_state(settings)
    if state.has_pending_work:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "active_jobs": state.active_job_descriptions,
                "pending_manifest_sync_videos": state.pending_manifest_sync_videos,
                "pending_custom_poster_sync_videos": state.pending_custom_poster_sync_videos,
            },
        )

    server = getattr(request.app.state, "server", None)
    if server is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Server control is unavailable.")

    Thread(target=_request_server_exit, args=(server,), daemon=True).start()
    return {"accepted": True}


def _validate_control_token(request: Request) -> None:
    expected = request.app.state.settings.control_token
    provided = request.headers.get("x-csp-control-token", "")
    if not expected or provided != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Runtime control token is invalid.")


def _request_server_exit(server) -> None:
    server.should_exit = True
