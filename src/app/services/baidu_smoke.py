from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import Settings
from app.db.schema import initialize_database
from app.repositories.videos import list_videos
from app.services.baidu_oauth import (
    BaiduOAuthConfigurationError,
    authorize_baidu_with_code,
    build_baidu_authorize_url,
    get_baidu_access_token,
    get_baidu_refresh_token,
    set_baidu_access_token,
    set_baidu_refresh_token,
)
from app.services.catalog_sync import sync_remote_catalog
from app.services.imports import import_local_video
from app.services.settings import update_public_settings
from app.services.streaming import iter_video_stream, prepare_video_stream
from app.storage.factory import build_storage_backend


class BaiduSmokePrerequisiteError(RuntimeError):
    """Raised when the smoke test cannot start due to missing OAuth prerequisites."""


@dataclass(slots=True)
class BaiduSmokeResult:
    remote_root: str
    manifest_path: str
    writer_video_id: int
    reader_video_id: int
    segment_count: int
    discovered_manifest_count: int
    created_video_count: int
    updated_video_count: int
    verified_range_end: int
    workspace_dir: Path


@dataclass(slots=True)
class SmokeRuntime:
    writer_settings: Settings
    reader_settings: Settings
    remote_root: str
    workspace_dir: Path


def run_baidu_smoke(
    base_settings: Settings,
    *,
    source_path: str | None = None,
    oauth_code: str | None = None,
    remote_root: str | None = None,
    range_end: int = 255,
) -> BaiduSmokeResult:
    runtime = prepare_smoke_runtime(
        base_settings,
        oauth_code=oauth_code,
        remote_root=remote_root,
    )
    try:
        smoke_source_path = _prepare_smoke_source(base_settings, runtime.workspace_dir, source_path)
        expected_bytes = _read_expected_range(smoke_source_path, range_end=range_end)

        import_job = import_local_video(
            runtime.writer_settings,
            source_path=str(smoke_source_path),
            title=f"baidu-smoke-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        )
        if import_job.video_id is None:
            raise RuntimeError(f"Smoke import did not create a video: {import_job.error_message}")

        writer_videos = list_videos(runtime.writer_settings)
        if len(writer_videos) != 1:
            raise RuntimeError(f"Expected exactly 1 writer video, got {len(writer_videos)}.")
        writer_video = writer_videos[0]
        if not writer_video.manifest_path:
            raise RuntimeError("Smoke import did not persist a manifest path.")

        storage = build_storage_backend(runtime.writer_settings)
        if not storage.exists(writer_video.manifest_path):
            raise RuntimeError(f"Remote manifest was not uploaded: {writer_video.manifest_path}")

        smoke_source_path.unlink(missing_ok=True)
        shutil.rmtree(runtime.writer_settings.segment_staging_dir / str(writer_video.id), ignore_errors=True)

        sync_result = sync_remote_catalog(runtime.reader_settings)
        reader_videos = list_videos(runtime.reader_settings)
        if len(reader_videos) != 1:
            raise RuntimeError(f"Expected exactly 1 reader video after sync, got {len(reader_videos)}.")
        reader_video = reader_videos[0]

        payload = prepare_video_stream(
            runtime.reader_settings,
            video_id=reader_video.id,
            range_header=f"bytes=0-{range_end}",
        )
        remote_bytes = b"".join(iter_video_stream(payload))
        if remote_bytes != expected_bytes:
            raise RuntimeError("Remote playback bytes did not match the original source range.")

        return BaiduSmokeResult(
            remote_root=runtime.remote_root,
            manifest_path=writer_video.manifest_path,
            writer_video_id=writer_video.id,
            reader_video_id=reader_video.id,
            segment_count=writer_video.segment_count,
            discovered_manifest_count=sync_result.discovered_manifest_count,
            created_video_count=sync_result.created_video_count,
            updated_video_count=sync_result.updated_video_count,
            verified_range_end=range_end,
            workspace_dir=runtime.workspace_dir,
        )
    finally:
        persist_latest_refresh_token(
            base_settings,
            candidates=[runtime.reader_settings, runtime.writer_settings],
        )


def prepare_smoke_runtime(
    base_settings: Settings,
    *,
    oauth_code: str | None = None,
    remote_root: str | None = None,
) -> SmokeRuntime:
    normalized_remote_root = normalize_smoke_remote_root(remote_root)
    workspace_dir = build_smoke_workspace_dir()
    runtime_root = workspace_dir / "runtime"
    writer_settings = clone_settings(
        base_settings,
        database_path=runtime_root / "writer.db",
        covers_path=runtime_root / "writer-covers",
        content_key_path=runtime_root / "shared-content.key",
        segment_staging_path=runtime_root / "writer-segments",
        mock_storage_path=runtime_root / "writer-mock-remote",
    )
    reader_settings = clone_settings(
        base_settings,
        database_path=runtime_root / "reader.db",
        covers_path=runtime_root / "reader-covers",
        content_key_path=runtime_root / "shared-content.key",
        segment_staging_path=runtime_root / "reader-segments",
        mock_storage_path=runtime_root / "reader-mock-remote",
    )

    prepare_runtime_settings(writer_settings)
    prepare_runtime_settings(reader_settings)
    copy_baidu_refresh_token(
        base_settings,
        targets=[writer_settings, reader_settings],
        oauth_code=oauth_code,
    )
    update_public_settings(
        writer_settings,
        baidu_root_path=normalized_remote_root,
        storage_backend="baidu",
    )
    update_public_settings(
        reader_settings,
        baidu_root_path=normalized_remote_root,
        storage_backend="baidu",
    )
    return SmokeRuntime(
        writer_settings=writer_settings,
        reader_settings=reader_settings,
        remote_root=normalized_remote_root,
        workspace_dir=workspace_dir,
    )


def copy_baidu_refresh_token(
    base_settings: Settings,
    *,
    targets: list[Settings],
    oauth_code: str | None = None,
) -> str:
    initialize_database(base_settings)
    if oauth_code is not None:
        authorize_baidu_with_code(base_settings, code=oauth_code)
    refresh_token = get_baidu_refresh_token(base_settings)

    if refresh_token is None:
        authorize_url = build_baidu_authorize_url(base_settings)
        if authorize_url is None:
            raise BaiduOAuthConfigurationError("BAIDU_APP_KEY is not configured.")
        raise BaiduSmokePrerequisiteError(
            "Baidu refresh token is not configured. Open the authorize URL, then rerun with --oauth-code.\n"
            f"Authorize URL: {authorize_url}"
        )

    for settings in targets:
        set_baidu_refresh_token(settings, refresh_token)
        access_token = get_baidu_access_token(base_settings)
        if access_token:
            _copy_baidu_access_token(base_settings, settings)
    return refresh_token


def clone_settings(
    base_settings: Settings,
    *,
    database_path: Path,
    covers_path: Path,
    content_key_path: Path,
    segment_staging_path: Path,
    mock_storage_path: Path,
) -> Settings:
    return Settings(
        app_name=base_settings.app_name,
        host=base_settings.host,
        port=base_settings.port,
        session_secret=base_settings.session_secret,
        password=base_settings.password,
        password_hash=base_settings.password_hash,
        database_path=database_path,
        ffprobe_binary=base_settings.ffprobe_binary,
        ffmpeg_binary=base_settings.ffmpeg_binary,
        covers_path=covers_path,
        content_key_path=content_key_path,
        segment_staging_path=segment_staging_path,
        mock_storage_path=mock_storage_path,
        segment_size_bytes=base_settings.segment_size_bytes,
        storage_backend="baidu",
        baidu_oauth_redirect_uri=base_settings.baidu_oauth_redirect_uri,
        cors_allowed_origins_raw=base_settings.cors_allowed_origins_raw,
    )


def prepare_runtime_settings(settings: Settings) -> None:
    initialize_database(settings)
    settings.covers_dir.mkdir(parents=True, exist_ok=True)
    settings.segment_staging_dir.mkdir(parents=True, exist_ok=True)
    settings.mock_storage_dir.mkdir(parents=True, exist_ok=True)
    settings.content_key_file.parent.mkdir(parents=True, exist_ok=True)


def persist_latest_refresh_token(base_settings: Settings, *, candidates: list[Settings]) -> None:
    for settings in candidates:
        refresh_token = get_baidu_refresh_token(settings)
        if refresh_token:
            set_baidu_refresh_token(base_settings, refresh_token)
            _copy_baidu_access_token(settings, base_settings)
            return


def _copy_baidu_access_token(source_settings: Settings, target_settings: Settings) -> None:
    access_token = get_baidu_access_token(source_settings)
    if not access_token:
        return

    expires_at_value = _load_baidu_access_token_expires_at(source_settings)
    if expires_at_value is None:
        return

    now = datetime.now(timezone.utc)
    remaining_seconds = int((expires_at_value - now).total_seconds())
    if remaining_seconds <= 0:
        return

    set_baidu_access_token(
        target_settings,
        access_token,
        expires_in=remaining_seconds,
    )


def _load_baidu_access_token_expires_at(settings: Settings) -> datetime | None:
    from app.repositories.settings import get_setting
    from app.services.baidu_oauth import BAIDU_ACCESS_TOKEN_EXPIRES_AT_KEY

    expires_at = get_setting(settings, BAIDU_ACCESS_TOKEN_EXPIRES_AT_KEY)
    if expires_at is None:
        return None
    try:
        value = datetime.fromisoformat(expires_at.value)
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def build_smoke_workspace_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    workspace_dir = Path("tmp") / "baidu-smoke" / timestamp
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


def normalize_smoke_remote_root(remote_root: str | None) -> str:
    if remote_root is not None:
        normalized = remote_root.strip()
        if not normalized:
            raise ValueError("remote_root must not be empty.")
        if not normalized.startswith("/apps/"):
            raise ValueError("remote_root must start with '/apps/'.")
        return normalized.rstrip("/")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"/apps/CloudStoragePlayer-smoke/{timestamp}"


def _prepare_smoke_source(
    settings: Settings,
    workspace_dir: Path,
    source_path: str | None,
) -> Path:
    source_dir = workspace_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    if source_path is None:
        generated_path = source_dir / "generated-smoke.mp4"
        _generate_sample_video(settings, generated_path)
        return generated_path

    original_source = Path(source_path)
    if not original_source.exists() or not original_source.is_file():
        raise FileNotFoundError(f"Smoke source file does not exist: {source_path}")

    copied_path = source_dir / original_source.name
    shutil.copyfile(original_source, copied_path)
    return copied_path


def _generate_sample_video(settings: Settings, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        settings.ffmpeg_binary,
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


def _read_expected_range(source_path: Path, *, range_end: int) -> bytes:
    if range_end < 0:
        raise ValueError("range_end must be greater than or equal to 0.")
    with source_path.open("rb") as file_handle:
        return file_handle.read(range_end + 1)
