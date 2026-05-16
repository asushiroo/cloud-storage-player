from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import require_authenticated
from app.api.schemas.admin_settings import (
    AdminPasswordUpdateRequest,
    AdminPasswordUpdateResponse,
    AdminSettingsResponse,
    AdminSettingsUpdateRequest,
)
from app.services.admin_settings import (
    get_admin_settings,
    update_admin_settings,
    update_login_password,
)

router = APIRouter(prefix="/api/admin/settings", tags=["admin-settings"])


@router.get("", response_model=AdminSettingsResponse)
def get_admin_settings_view(
    request: Request,
    _: None = Depends(require_authenticated),
) -> AdminSettingsResponse:
    settings = request.app.state.settings
    return AdminSettingsResponse.model_validate(get_admin_settings(settings))


@router.post("", response_model=AdminSettingsResponse)
def update_admin_settings_view(
    payload: AdminSettingsUpdateRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> AdminSettingsResponse:
    settings = request.app.state.settings
    try:
        updated = update_admin_settings(
            settings,
            playback_download_transfer_concurrency=payload.playback_download_transfer_concurrency,
            baidu_app_key=payload.baidu_app_key,
            baidu_secret_key=payload.baidu_secret_key,
            baidu_sign_key=payload.baidu_sign_key,
            baidu_oauth_redirect_uri=payload.baidu_oauth_redirect_uri,
            session_secret=payload.session_secret,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AdminSettingsResponse.model_validate(updated)


@router.post("/password", response_model=AdminPasswordUpdateResponse)
def update_admin_password_view(
    payload: AdminPasswordUpdateRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> AdminPasswordUpdateResponse:
    settings = request.app.state.settings
    try:
        update_login_password(
            settings,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AdminPasswordUpdateResponse(updated=True)
