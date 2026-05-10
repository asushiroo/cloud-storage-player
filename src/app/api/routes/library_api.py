from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi import HTTPException, status

from app.api.dependencies import require_authenticated
from app.api.schemas.library import CatalogSyncResponse, FolderResponse, VideoResponse
from app.repositories.folders import list_folders
from app.repositories.videos import get_video, list_videos
from app.services.baidu_oauth import BaiduOAuthConfigurationError
from app.services.catalog_sync import sync_remote_catalog
from app.storage.baidu_api import BaiduApiError

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/folders", response_model=list[FolderResponse])
async def get_folders(
    request: Request,
    _: None = Depends(require_authenticated),
) -> list[FolderResponse]:
    settings = request.app.state.settings
    return [FolderResponse.model_validate(folder) for folder in list_folders(settings)]


@router.get("/videos", response_model=list[VideoResponse])
async def get_videos(
    request: Request,
    folder_id: int | None = None,
    _: None = Depends(require_authenticated),
) -> list[VideoResponse]:
    settings = request.app.state.settings
    return [
        VideoResponse.model_validate(video)
        for video in list_videos(settings, folder_id=folder_id)
    ]


@router.get("/videos/{video_id}", response_model=VideoResponse)
async def get_video_detail(
    video_id: int,
    request: Request,
    _: None = Depends(require_authenticated),
) -> VideoResponse:
    settings = request.app.state.settings
    video = get_video(settings, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    return VideoResponse.model_validate(video)


@router.post("/videos/sync", response_model=CatalogSyncResponse)
async def sync_videos(
    request: Request,
    _: None = Depends(require_authenticated),
) -> CatalogSyncResponse:
    settings = request.app.state.settings
    try:
        result = sync_remote_catalog(settings)
    except BaiduOAuthConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (BaiduApiError, RuntimeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return CatalogSyncResponse(
        discovered_manifest_count=result.discovered_manifest_count,
        created_video_count=result.created_video_count,
        updated_video_count=result.updated_video_count,
        failed_manifest_count=result.failed_manifest_count,
        errors=result.errors,
    )
