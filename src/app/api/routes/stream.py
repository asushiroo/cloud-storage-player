from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.dependencies import require_authenticated
from app.media.range_map import RangeNotSatisfiableError
from app.services.streaming import (
    VideoStreamNotFoundError,
    iter_file_range,
    prepare_video_stream,
)

router = APIRouter(prefix="/api/videos", tags=["stream"])


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: int,
    request: Request,
    _: None = Depends(require_authenticated),
) -> StreamingResponse:
    settings = request.app.state.settings
    try:
        payload = prepare_video_stream(
            settings,
            video_id=video_id,
            range_header=request.headers.get("range"),
        )
    except VideoStreamNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RangeNotSatisfiableError as exc:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail=str(exc),
            headers={"Content-Range": f"bytes */{payload_size_from_request(settings, video_id)}"},
        ) from exc

    headers = {
        "Accept-Ranges": "bytes",
    }
    status_code = status.HTTP_200_OK
    byte_range = payload.byte_range
    if byte_range is None:
        headers["Content-Length"] = str(payload.size)
        start = 0
        end = payload.size - 1
    else:
        headers["Content-Length"] = str(byte_range.length)
        headers["Content-Range"] = f"bytes {byte_range.start}-{byte_range.end}/{payload.size}"
        status_code = status.HTTP_206_PARTIAL_CONTENT
        start = byte_range.start
        end = byte_range.end

    return StreamingResponse(
        iter_file_range(payload.source_path, start=start, end=end),
        media_type=payload.mime_type,
        status_code=status_code,
        headers=headers,
    )


def payload_size_from_request(settings, video_id: int) -> int:
    try:
        payload = prepare_video_stream(settings, video_id=video_id, range_header=None)
    except VideoStreamNotFoundError:
        return 0
    return payload.size
