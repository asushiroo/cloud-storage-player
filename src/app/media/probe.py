from __future__ import annotations

import json
import mimetypes
import subprocess
from dataclasses import dataclass
from pathlib import Path


class MediaProbeError(RuntimeError):
    """Raised when ffprobe cannot inspect the source media."""


@dataclass(slots=True)
class MediaProbeResult:
    source_path: Path
    format_name: str | None
    mime_type: str
    size: int
    duration_seconds: float | None


def probe_video(source_path: Path, *, ffprobe_binary: str = "ffprobe") -> MediaProbeResult:
    if not source_path.exists() or not source_path.is_file():
        raise MediaProbeError(f"Source file does not exist: {source_path}")

    command = [
        ffprobe_binary,
        "-v",
        "error",
        "-show_entries",
        "format=duration,format_name:stream=codec_type",
        "-of",
        "json",
        str(source_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=False,
        check=False,
    )
    if completed.returncode != 0:
        error_message = _decode_process_output(completed.stderr).strip() or "ffprobe failed."
        raise MediaProbeError(error_message)

    try:
        payload = json.loads(_decode_process_output(completed.stdout) or "{}")
    except json.JSONDecodeError as exc:
        raise MediaProbeError("ffprobe returned invalid JSON.") from exc

    stream_types = {
        stream.get("codec_type")
        for stream in payload.get("streams", [])
        if isinstance(stream, dict)
    }
    if "video" not in stream_types:
        raise MediaProbeError("Source file does not contain a video stream.")

    format_payload = payload.get("format", {})
    duration_token = format_payload.get("duration")
    duration_seconds = float(duration_token) if duration_token not in (None, "") else None
    mime_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"

    return MediaProbeResult(
        source_path=source_path,
        format_name=format_payload.get("format_name"),
        mime_type=mime_type,
        size=source_path.stat().st_size,
        duration_seconds=duration_seconds,
    )


def _decode_process_output(payload: bytes | str | None) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "cp936"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")
