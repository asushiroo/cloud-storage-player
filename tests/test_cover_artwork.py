import subprocess
from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.repositories.videos import get_video
from app.services.artwork_storage import encrypted_artwork_path, read_artwork_bytes
from app.services.imports import import_local_video


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "cover-artwork.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
        segment_size_bytes=512,
    )
    initialize_database(settings)
    return settings


def create_sample_video(output_path: Path) -> Path:
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=1920x1080:d=1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output_path


def create_progressive_sample_video(output_path: Path, *, duration_seconds: int) -> Path:
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=1280x720:d={duration_seconds}",
        "-vf",
        "drawbox=x=0:y=0:w=iw*0.34:h=ih:color=red@1:t=fill:enable='lt(t,1)'"
        ",drawbox=x=0:y=0:w=iw*0.34:h=ih:color=green@1:t=fill:enable='between(t,1,2)'"
        ",drawbox=x=0:y=0:w=iw*0.34:h=ih:color=blue@1:t=fill:enable='gte(t,2)'",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output_path


def read_image_size(image_path: Path) -> tuple[int, int]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=p=0:s=x",
        str(image_path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    width_text, height_text = completed.stdout.strip().split("x", 1)
    return int(width_text), int(height_text)


def read_average_rgb(image_path: Path) -> tuple[float, float, float]:
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(image_path),
        "-vf",
        "scale=1:1,format=rgb24",
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "-",
    ]
    completed = subprocess.run(command, check=True, capture_output=True)
    payload = completed.stdout
    if len(payload) < 3:
        raise AssertionError("Unable to compute poster average color.")
    return float(payload[0]), float(payload[1]), float(payload[2])


def test_import_generates_fixed_ratio_poster_only(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    source_path = create_sample_video(tmp_path / "landscape.mp4")

    job = import_local_video(settings, source_path=str(source_path), title="Artwork Demo")
    video = get_video(settings, job.video_id)

    assert video is not None
    assert video.cover_path is None
    assert video.poster_path is not None
    artwork_name = Path(video.poster_path).name
    encrypted_poster_file = encrypted_artwork_path(settings, file_name=artwork_name)
    assert encrypted_poster_file.exists()
    poster_bytes, media_type = read_artwork_bytes(settings, artwork_name=artwork_name)
    assert media_type == "image/avif"
    poster_file = tmp_path / artwork_name
    poster_file.write_bytes(poster_bytes)

    poster_width, poster_height = read_image_size(poster_file)
    assert (poster_width, poster_height) == (1280, 720)


def test_import_uses_one_third_position_for_poster_frame(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    source_path = create_progressive_sample_video(tmp_path / "timeline.mp4", duration_seconds=3)

    job = import_local_video(settings, source_path=str(source_path), title="Timeline Demo")
    video = get_video(settings, job.video_id)
    assert video is not None
    assert video.poster_path is not None

    artwork_name = Path(video.poster_path).name
    poster_bytes, media_type = read_artwork_bytes(settings, artwork_name=artwork_name)
    assert media_type == "image/avif"
    poster_file = tmp_path / "timeline-poster.avif"
    poster_file.write_bytes(poster_bytes)

    red, green, blue = read_average_rgb(poster_file)
    assert green > red
    assert green > blue
