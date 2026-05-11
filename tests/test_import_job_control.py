import subprocess
import threading
import time
from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.repositories.import_jobs import (
    create_delete_job,
    create_import_job,
    delete_completed_import_jobs,
    delete_failed_import_jobs,
    get_import_job,
    mark_import_job_cancelled,
    mark_import_job_completed,
    mark_import_job_failed,
    request_cancel_job,
    request_cancel_all_active_jobs,
)
from app.repositories.videos import create_video
from app.repositories.videos import list_videos
from app.services.background_jobs import process_background_job
from app.services.imports import process_import_job
from app.services.video_delete import process_delete_job


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "job-control.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
        segment_size_bytes=128,
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
        "color=c=black:s=160x90:d=2",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output_path


def test_process_background_job_ignores_missing_jobs(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)

    assert process_background_job(settings, 999999) is None


def test_clear_completed_and_failed_jobs_are_separate(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    completed_job = create_import_job(settings, source_path="/tmp/completed.mp4")
    failed_job = create_import_job(settings, source_path="/tmp/failed.mp4")
    cancelled_job = create_import_job(settings, source_path="/tmp/cancelled.mp4")

    mark_import_job_completed(settings, completed_job.id)
    mark_import_job_failed(settings, failed_job.id, error_message="boom")
    mark_import_job_cancelled(settings, cancelled_job.id, error_message="cancelled")

    assert delete_completed_import_jobs(settings) == 1
    assert get_import_job(settings, completed_job.id) is None
    assert get_import_job(settings, failed_job.id) is not None
    assert get_import_job(settings, cancelled_job.id) is not None

    assert delete_failed_import_jobs(settings) == 2
    assert get_import_job(settings, failed_job.id) is None
    assert get_import_job(settings, cancelled_job.id) is None


def test_cancelling_running_import_cleans_uploaded_remote_artifacts(tmp_path: Path, monkeypatch) -> None:
    settings = build_settings(tmp_path)
    source_path = create_sample_video(tmp_path / "cancel.mp4")
    job = create_import_job(settings, source_path=str(source_path), task_name="cancel-demo")

    import app.services.imports as imports_module
    from app.storage.mock import MockStorageBackend

    real_iter_file_chunks = imports_module.iter_file_chunks
    real_upload_file = MockStorageBackend.upload_file

    def slow_iter_file_chunks(*args, **kwargs):
        for chunk in real_iter_file_chunks(*args, **kwargs):
            time.sleep(0.03)
            yield chunk

    def slow_upload_file(self, local_path, remote_path):
        real_upload_file(self, local_path, remote_path)
        time.sleep(0.03)

    monkeypatch.setattr(imports_module, "iter_file_chunks", slow_iter_file_chunks)
    monkeypatch.setattr(MockStorageBackend, "upload_file", slow_upload_file)

    worker = threading.Thread(target=process_import_job, args=(settings, job.id), daemon=True)
    worker.start()

    deadline = time.time() + 10
    while time.time() < deadline:
        current = get_import_job(settings, job.id)
        assert current is not None
        remote_has_files = settings.mock_storage_dir.exists() and any(path.is_file() for path in settings.mock_storage_dir.rglob("*"))
        if current.status in {"running", "cancelling"} and remote_has_files:
            break
        time.sleep(0.02)
    else:
        raise AssertionError("Import job did not reach a cancellable state with remote artifacts.")

    cancelled = request_cancel_job(settings, job.id)
    assert cancelled is not None
    worker.join(timeout=10)

    final_job = get_import_job(settings, job.id)
    assert final_job is not None
    assert final_job.status == "cancelled"
    assert list_videos(settings) == []
    assert not any(path.is_file() for path in settings.mock_storage_dir.rglob("*"))


def test_delete_job_cannot_be_cancelled(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    video = create_video(settings, title="Delete Locked", mime_type="video/mp4", size=123)
    job = create_delete_job(
        settings,
        source_path=f"video:{video.id}",
        requested_title=video.title,
        task_name=f"删除：{video.title}",
        target_video_id=video.id,
    )

    from app.repositories.import_jobs import ImportJobCancellationNotAllowedError

    try:
        request_cancel_job(settings, job.id)
    except ImportJobCancellationNotAllowedError:
        pass
    else:
        raise AssertionError("Expected delete job cancellation to be rejected.")

    current = get_import_job(settings, job.id)
    assert current is not None
    assert current.status == "queued"
    assert current.cancel_requested is False


def test_cancel_all_active_jobs_skips_delete_jobs(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    import_job = create_import_job(settings, source_path="/tmp/import.mp4")
    video = create_video(settings, title="Delete Locked", mime_type="video/mp4", size=123)
    delete_job = create_delete_job(
        settings,
        source_path=f"video:{video.id}",
        requested_title=video.title,
        task_name=f"删除：{video.title}",
        target_video_id=video.id,
    )

    updated_count = request_cancel_all_active_jobs(settings)

    assert updated_count == 1
    cancelled_import = get_import_job(settings, import_job.id)
    untouched_delete = get_import_job(settings, delete_job.id)
    assert cancelled_import is not None
    assert cancelled_import.status == "cancelled"
    assert untouched_delete is not None
    assert untouched_delete.status == "queued"
    assert untouched_delete.cancel_requested is False


def test_delete_job_progress_advances_before_completion(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    video = create_video(
        settings,
        title="Delete Progress",
        mime_type="video/mp4",
        size=123,
        manifest_path="/apps/CloudStoragePlayer/delete-progress/manifest.bin",
    )
    job = create_delete_job(
        settings,
        source_path=f"video:{video.id}",
        requested_title=video.title,
        task_name=f"删除：{video.title}",
        target_video_id=video.id,
    )

    from app.services import video_delete as video_delete_module

    progress_updates: list[int] = []
    real_update_progress = video_delete_module.update_import_job_progress

    def capture_progress(current_settings, job_id, *, progress_percent):
        progress_updates.append(progress_percent)
        return real_update_progress(current_settings, job_id, progress_percent=progress_percent)

    original_delete_remote = video_delete_module._delete_remote_paths_best_effort
    original_delete_local = video_delete_module._delete_local_artifacts
    try:
        video_delete_module.update_import_job_progress = capture_progress
        video_delete_module._delete_remote_paths_best_effort = lambda *args, **kwargs: None
        video_delete_module._delete_local_artifacts = lambda *args, **kwargs: None
        completed = process_delete_job(settings, job.id)
    finally:
        video_delete_module.update_import_job_progress = real_update_progress
        video_delete_module._delete_remote_paths_best_effort = original_delete_remote
        video_delete_module._delete_local_artifacts = original_delete_local

    assert completed.status == "completed"
    assert progress_updates == [40, 70, 90]
