from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.repositories.video_segments import list_video_segments
from app.services.imports import import_local_video


def create_sample_video(output_path: Path) -> Path:
    import subprocess

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=160x90:d=1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output_path


def test_import_persists_encrypted_segment_metadata(tmp_path: Path) -> None:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "segments.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        segment_size_bytes=512,
    )
    create_app(settings)
    source_path = create_sample_video(tmp_path / "segmented.mp4")

    job = import_local_video(settings, source_path=str(source_path))
    segments = list_video_segments(settings, video_id=job.video_id)

    assert job.status == "completed"
    assert len(segments) >= 2
    assert [segment.segment_index for segment in segments] == list(range(len(segments)))
    assert segments[0].original_offset == 0
    assert all(segment.original_length > 0 for segment in segments)
    assert all(segment.ciphertext_size >= segment.original_length for segment in segments)
    assert all(segment.local_staging_path is not None for segment in segments)
    assert all(Path(segment.local_staging_path).exists() for segment in segments)
