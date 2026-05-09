from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi import HTTPException, status

from app.api.dependencies import require_authenticated
from app.api.schemas.library import FolderResponse, VideoResponse
from app.repositories.folders import list_folders
from app.repositories.videos import get_video, list_videos

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
