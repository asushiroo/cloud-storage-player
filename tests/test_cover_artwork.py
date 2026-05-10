import subprocess
from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.repositories.videos import get_video
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


def test_import_generates_separate_fixed_ratio_cover_and_poster(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    source_path = create_sample_video(tmp_path / "landscape.mp4")

    job = import_local_video(settings, source_path=str(source_path), title="Artwork Demo")
    video = get_video(settings, job.video_id)

    assert video is not None
    assert video.cover_path is not None
    assert video.poster_path is not None
    cover_file = settings.covers_dir / Path(video.cover_path).name
    poster_file = settings.covers_dir / Path(video.poster_path).name
    assert cover_file.exists()
    assert poster_file.exists()

    cover_width, cover_height = read_image_size(cover_file)
    poster_width, poster_height = read_image_size(poster_file)
    assert (cover_width, cover_height) == (540, 810)
    assert (poster_width, poster_height) == (1280, 720)
