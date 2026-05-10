from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class CoverExtractionError(RuntimeError):
    """Raised when ffmpeg cannot extract an artwork frame."""


@dataclass(frozen=True, slots=True)
class ArtworkPreset:
    width: int
    height: int

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height


COVER_PRESET = ArtworkPreset(width=540, height=810)
POSTER_PRESET = ArtworkPreset(width=1280, height=720)


def extract_cover(
    source_path: Path,
    output_path: Path,
    *,
    ffmpeg_binary: str = "ffmpeg",
) -> Path:
    return extract_artwork_variant(
        source_path,
        output_path,
        preset=COVER_PRESET,
        ffmpeg_binary=ffmpeg_binary,
    )


def extract_poster(
    source_path: Path,
    output_path: Path,
    *,
    ffmpeg_binary: str = "ffmpeg",
) -> Path:
    return extract_artwork_variant(
        source_path,
        output_path,
        preset=POSTER_PRESET,
        ffmpeg_binary=ffmpeg_binary,
    )


def extract_artwork_variant(
    source_path: Path,
    output_path: Path,
    *,
    preset: ArtworkPreset,
    ffmpeg_binary: str = "ffmpeg",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filter_chain = (
        f"scale={preset.width}:{preset.height}:force_original_aspect_ratio=increase,"
        f"crop={preset.width}:{preset.height}"
    )
    command = [
        ffmpeg_binary,
        "-y",
        "-ss",
        "0",
        "-i",
        str(source_path),
        "-frames:v",
        "1",
        "-vf",
        filter_chain,
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
        error_message = completed.stderr.strip() or "ffmpeg artwork extraction failed."
        raise CoverExtractionError(error_message)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise CoverExtractionError("ffmpeg did not produce an artwork file.")

    return output_path
