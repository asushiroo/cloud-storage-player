from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi import HTTPException, status

from app.api.dependencies import require_authenticated
from app.api.schemas.imports import ImportJobResponse
from app.api.schemas.library import (
    CatalogSyncResponse,
    FolderResponse,
    VideoArtworkUpdateRequest,
    VideoResponse,
    VideoTagsUpdateRequest,
)
from app.core.tags import normalize_tags
from app.repositories.folders import list_folders
from app.repositories.videos import get_video, list_videos, update_video_tags
from app.services.baidu_oauth import BaiduOAuthConfigurationError
from app.services.catalog_sync import sync_remote_catalog
from app.services.video_artwork import (
    VideoArtworkNotFoundError,
    VideoArtworkValidationError,
    replace_video_artwork,
)
from app.services.video_delete import VideoDeleteNotFoundError, queue_video_delete_job
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
    q: str | None = None,
    tag: str | None = None,
    _: None = Depends(require_authenticated),
) -> list[VideoResponse]:
    settings = request.app.state.settings
    return [
        VideoResponse.model_validate(video)
        for video in list_videos(settings, folder_id=folder_id, q=q, tag=tag)
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


@router.patch("/videos/{video_id}/tags", response_model=VideoResponse)
async def patch_video_tags(
    video_id: int,
    payload: VideoTagsUpdateRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> VideoResponse:
    settings = request.app.state.settings
    video = get_video(settings, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    updated_video = update_video_tags(
        settings,
        video_id,
        tags=normalize_tags(payload.tags),
    )
    return VideoResponse.model_validate(updated_video)


@router.post("/videos/{video_id}/artwork", response_model=VideoResponse)
async def update_video_artwork(
    video_id: int,
    payload: VideoArtworkUpdateRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> VideoResponse:
    settings = request.app.state.settings
    try:
        updated_video = replace_video_artwork(
            settings,
            video_id,
            cover_data_url=payload.cover_data_url,
            poster_data_url=payload.poster_data_url,
        )
    except VideoArtworkNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.") from exc
    except VideoArtworkValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return VideoResponse.model_validate(updated_video)


@router.delete("/videos/{video_id}", response_model=ImportJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def delete_video_entry(
    video_id: int,
    request: Request,
    _: None = Depends(require_authenticated),
) -> ImportJobResponse:
    settings = request.app.state.settings
    worker = request.app.state.import_worker
    try:
        job = queue_video_delete_job(settings, video_id=video_id, worker=worker)
    except VideoDeleteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.") from exc

    return ImportJobResponse.model_validate(job)


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
