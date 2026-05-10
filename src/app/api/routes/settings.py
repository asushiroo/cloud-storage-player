from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import require_authenticated
from app.api.schemas.settings import BaiduOAuthRequest, SettingsResponse, SettingsUpdateRequest
from app.services.baidu_oauth import (
    BaiduAuthorizationError,
    BaiduOAuthConfigurationError,
    authorize_baidu_with_code,
)
from app.services.settings import get_public_settings, update_public_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings_view(
    request: Request,
    _: None = Depends(require_authenticated),
) -> SettingsResponse:
    settings = request.app.state.settings
    return SettingsResponse.model_validate(get_public_settings(settings))


@router.post("", response_model=SettingsResponse)
async def update_settings_view(
    payload: SettingsUpdateRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> SettingsResponse:
    settings = request.app.state.settings
    try:
        updated = update_public_settings(
            settings,
            baidu_root_path=payload.baidu_root_path,
            cache_limit_bytes=payload.cache_limit_bytes,
            storage_backend=payload.storage_backend,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SettingsResponse.model_validate(updated)


@router.post("/baidu/oauth", response_model=SettingsResponse)
async def authorize_baidu_view(
    payload: BaiduOAuthRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> SettingsResponse:
    settings = request.app.state.settings
    try:
        authorize_baidu_with_code(settings, code=payload.code)
    except (BaiduAuthorizationError, BaiduOAuthConfigurationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SettingsResponse.model_validate(get_public_settings(settings))
