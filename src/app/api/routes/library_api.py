from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from fastapi import HTTPException, status

from app.api.dependencies import require_authenticated
from app.api.schemas.imports import ImportJobResponse
from app.api.schemas.library import (
    CatalogSyncResponse,
    VideoPageResponse,
    VideoRecommendationShelfResponse,
    VideoArtworkUpdateRequest,
    VideoLikeUpdateRequest,
    VideoWatchHeartbeatRequest,
    VideoWatchHeartbeatResponse,
    VideoMetadataUpdateRequest,
    VideoResponse,
    VideoTagsUpdateRequest,
)
from app.core.tags import normalize_tags
from app.repositories.videos import get_video, increment_video_like_count, list_videos
from app.services.baidu_oauth import BaiduOAuthConfigurationError
from app.services.cache import (
    get_video_cache_status,
    list_cached_byte_ranges,
)
from app.services.catalog_sync import sync_remote_catalog
from app.services.recommendations import (
    build_recommendation_shelf,
    record_watch_heartbeat,
)
from app.services.video_metadata import (
    VideoMetadataValidationError,
    update_video_metadata_and_rewrite_manifest,
)
from app.services.video_artwork import (
    VideoArtworkNotFoundError,
    VideoArtworkValidationError,
    replace_video_artwork,
)
from app.services.artwork_storage import read_artwork_bytes
from app.services.video_delete import VideoDeleteNotFoundError, queue_video_delete_job
from app.storage.baidu_api import BaiduApiError

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/videos", response_model=list[VideoResponse])
async def get_videos(
    request: Request,
    q: str | None = None,
    tag: str | None = None,
    _: None = Depends(require_authenticated),
) -> list[VideoResponse]:
    settings = request.app.state.settings
    return [
        VideoResponse.model_validate(video)
        for video in list_videos(settings, q=q, tag=tag)
    ]


@router.get("/videos/recommendations", response_model=VideoRecommendationShelfResponse)
async def get_video_recommendations(
    request: Request,
    _: None = Depends(require_authenticated),
) -> VideoRecommendationShelfResponse:
    settings = request.app.state.settings
    videos = {video.id: video for video in list_videos(settings)}
    shelf = build_recommendation_shelf(settings)
    return VideoRecommendationShelfResponse(
        recommended=[
            VideoResponse.model_validate(videos[video_id])
            for video_id in shelf.recommended_videos
            if video_id in videos
        ],
        continue_watching=[
            VideoResponse.model_validate(videos[video_id])
            for video_id in shelf.continue_watching_videos
            if video_id in videos
        ],
        popular=[
            VideoResponse.model_validate(videos[video_id])
            for video_id in shelf.popular_videos
            if video_id in videos
        ],
    )


@router.get("/videos/page", response_model=VideoPageResponse)
async def get_video_page(
    request: Request,
    q: str | None = None,
    tag: str | None = None,
    offset: int = 0,
    limit: int = 12,
    _: None = Depends(require_authenticated),
) -> VideoPageResponse:
    settings = request.app.state.settings
    if limit <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit must be greater than 0.")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="offset must be greater than or equal to 0.")

    filtered_videos = list_videos(settings, q=q, tag=tag)
    total = len(filtered_videos)
    page = filtered_videos[offset : offset + limit]
    return VideoPageResponse(
        items=[VideoResponse.model_validate(video) for video in page],
        offset=offset,
        limit=limit,
        total=total,
        has_more=offset + limit < total,
    )


@router.get("/artwork/{artwork_name}")
async def get_artwork(artwork_name: str, request: Request) -> Response:
    settings = request.app.state.settings
    try:
        payload, media_type = read_artwork_bytes(settings, artwork_name=artwork_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artwork not found.") from exc
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


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

    cache_status = get_video_cache_status(settings, video_id=video.id)
    video.cached_size_bytes = cache_status.cached_size_bytes
    video.cached_segment_count = cache_status.cached_segment_count
    video.cached_byte_ranges = list_cached_byte_ranges(settings, video_id=video.id)

    return VideoResponse.model_validate(video)


@router.post("/videos/{video_id}/like", response_model=VideoResponse)
async def like_video(
    video_id: int,
    request: Request,
    _: None = Depends(require_authenticated),
    payload: VideoLikeUpdateRequest | None = Body(default=None),
    delta: int | None = Query(default=None),
) -> VideoResponse:
    settings = request.app.state.settings
    video = get_video(settings, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    selected_delta = delta if delta is not None else (payload.delta if payload is not None else 1)
    if selected_delta not in {-1, 1}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="delta must be 1 or -1.")

    updated_video = increment_video_like_count(
        settings,
        video_id,
        delta=selected_delta,
        upper_bound=99,
    )
    return VideoResponse.model_validate(updated_video)


@router.post("/videos/{video_id}/watch", response_model=VideoWatchHeartbeatResponse)
async def report_video_watch_progress(
    video_id: int,
    payload: VideoWatchHeartbeatRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> VideoWatchHeartbeatResponse:
    settings = request.app.state.settings
    try:
        result = record_watch_heartbeat(
            settings,
            video_id=video_id,
            session_token=payload.session_token,
            position_seconds=payload.position_seconds,
            watched_seconds_delta=payload.watched_seconds_delta,
            completed=payload.completed,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Video not found:") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return VideoWatchHeartbeatResponse(
        session_token=result.session_token,
        video=VideoResponse.model_validate(result.video),
    )


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

    try:
        updated_video = update_video_metadata_and_rewrite_manifest(
            settings,
            video_id,
            title=video.title,
            tags=normalize_tags(payload.tags),
        )
    except VideoMetadataValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return VideoResponse.model_validate(updated_video)


@router.patch("/videos/{video_id}", response_model=VideoResponse)
async def patch_video_metadata(
    video_id: int,
    payload: VideoMetadataUpdateRequest,
    request: Request,
    _: None = Depends(require_authenticated),
) -> VideoResponse:
    settings = request.app.state.settings
    try:
        updated_video = update_video_metadata_and_rewrite_manifest(
            settings,
            video_id,
            title=payload.title,
            tags=normalize_tags(payload.tags),
        )
    except VideoMetadataValidationError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Video not found:") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
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
