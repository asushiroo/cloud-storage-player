from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from app.api.dependencies import require_authenticated
from app.media.range_map import RangeNotSatisfiableError
from app.services.streaming import (
    VideoStreamNotFoundError,
    iter_video_stream,
    prepare_video_stream,
)

router = APIRouter(prefix="/api/videos", tags=["stream"])


class _StopStreamingIteration(Exception):
    """Internal sentinel used to end threaded stream iteration cleanly."""


class ManagedStreamingResponse(StreamingResponse):
    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except ClientDisconnect:
            return
        finally:
            aclose = getattr(self.body_iterator, "aclose", None)
            if callable(aclose):
                await aclose()


async def iterate_stream_chunks(iterator: Iterator[bytes]) -> AsyncIterator[bytes]:
    try:
        while True:
            try:
                yield await run_in_threadpool(_next_stream_chunk, iterator)
            except _StopStreamingIteration:
                return
    finally:
        await run_in_threadpool(_close_stream_iterator, iterator)


@router.get("/{video_id}/stream")
def stream_video(
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
    else:
        headers["Content-Length"] = str(byte_range.length)
        headers["Content-Range"] = f"bytes {byte_range.start}-{byte_range.end}/{payload.size}"
        status_code = status.HTTP_206_PARTIAL_CONTENT

    return ManagedStreamingResponse(
        iterate_stream_chunks(iter_video_stream(payload)),
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


def _next_stream_chunk(iterator: Iterator[bytes]) -> bytes:
    try:
        return next(iterator)
    except StopIteration as exc:
        raise _StopStreamingIteration from exc


def _close_stream_iterator(iterator: Iterator[bytes]) -> None:
    close = getattr(iterator, "close", None)
    if callable(close):
        close()
