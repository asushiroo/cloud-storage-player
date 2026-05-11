from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import require_authenticated
from app.api.schemas.cache import CacheSummaryResponse, CachedVideoResponse, ClearedCacheResponse
from app.api.schemas.imports import ImportJobResponse
from app.services.cache import (
    VideoCacheNotFoundError,
    clear_all_cache,
    clear_video_cache,
    get_cache_summary,
    list_cached_videos,
    queue_video_cache_job,
)

router = APIRouter(prefix="/api", tags=["cache"])


@router.get("/cache", response_model=CacheSummaryResponse)
async def get_cache_summary_view(
    request: Request,
    _: None = Depends(require_authenticated),
) -> CacheSummaryResponse:
    return CacheSummaryResponse.model_validate(get_cache_summary(request.app.state.settings))


@router.get("/cache/videos", response_model=list[CachedVideoResponse])
async def get_cached_videos_view(
    request: Request,
    _: None = Depends(require_authenticated),
) -> list[CachedVideoResponse]:
    return [
        CachedVideoResponse.model_validate(video)
        for video in list_cached_videos(request.app.state.settings)
    ]


@router.delete("/cache", response_model=ClearedCacheResponse)
async def clear_all_cache_view(
    request: Request,
    _: None = Depends(require_authenticated),
) -> ClearedCacheResponse:
    return ClearedCacheResponse(
        cleared_video_count=clear_all_cache(request.app.state.settings),
    )


@router.delete("/cache/videos/{video_id}", response_model=ClearedCacheResponse)
async def clear_video_cache_view(
    video_id: int,
    request: Request,
    _: None = Depends(require_authenticated),
) -> ClearedCacheResponse:
    try:
        clear_video_cache(request.app.state.settings, video_id=video_id)
    except VideoCacheNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.") from exc
    return ClearedCacheResponse(cleared_video_count=1)


@router.post("/videos/{video_id}/cache", response_model=ImportJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_video_cache_job(
    video_id: int,
    request: Request,
    _: None = Depends(require_authenticated),
) -> ImportJobResponse:
    try:
        job = queue_video_cache_job(
            request.app.state.settings,
            video_id=video_id,
            worker=request.app.state.import_worker,
        )
    except VideoCacheNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.") from exc
    return ImportJobResponse.model_validate(job)
