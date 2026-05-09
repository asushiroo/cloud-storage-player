from __future__ import annotations

import subprocess
from pathlib import Path


class CoverExtractionError(RuntimeError):
    """Raised when ffmpeg cannot extract a cover frame."""


def extract_cover(
    source_path: Path,
    output_path: Path,
    *,
    ffmpeg_binary: str = "ffmpeg",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_binary,
        "-y",
        "-ss",
        "0",
        "-i",
        str(source_path),
        "-frames:v",
        "1",
        str(output_path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise CoverExtractionError(str(exc)) from exc
    if completed.returncode != 0:
        error_message = completed.stderr.strip() or "ffmpeg cover extraction failed."
        raise CoverExtractionError(error_message)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise CoverExtractionError("ffmpeg did not produce a cover file.")

    return output_path
