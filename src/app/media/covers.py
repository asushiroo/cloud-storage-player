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
    ]
    return _run_artwork_command(
        command,
        output_path=output_path,
    )


def transcode_image_to_avif(
    source_path: Path,
    output_path: Path,
    *,
    ffmpeg_binary: str = "ffmpeg",
) -> Path:
    command = [
        ffmpeg_binary,
        "-y",
        "-i",
        str(source_path),
        "-frames:v",
        "1",
    ]
    return _run_artwork_command(
        command,
        output_path=output_path,
    )


def _run_artwork_command(
    command: list[str],
    *,
    output_path: Path,
) -> Path:
    attempts = [command + _codec_arguments_for(output_path) + [str(output_path)]]
    if output_path.suffix.casefold() == ".avif":
        attempts.append(command + ["-pix_fmt", "yuv420p", str(output_path)])

    last_error_message = "ffmpeg artwork extraction failed."
    for attempt in attempts:
        output_path.unlink(missing_ok=True)
        try:
            completed = subprocess.run(
                attempt,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise CoverExtractionError(str(exc)) from exc
        if completed.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return output_path
        last_error_message = completed.stderr.strip() or last_error_message

    raise CoverExtractionError(last_error_message)


def _codec_arguments_for(output_path: Path) -> list[str]:
    if output_path.suffix.casefold() == ".avif":
        return ["-c:v", "libaom-av1", "-still-picture", "1", "-pix_fmt", "yuv420p"]
    return []
