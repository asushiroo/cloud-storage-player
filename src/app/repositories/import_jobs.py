from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

from app.core.config import Settings
from app.core.tags import decode_tags, encode_tags
from app.db.connection import connect_database
from app.models.imports import ImportJob

JOB_SELECT_SQL = """
    SELECT id,
           source_path,
           folder_id,
           requested_title,
           requested_tags_json,
           job_kind,
           task_name,
           status,
           progress_percent,
           error_message,
           video_id,
           target_video_id,
           cancel_requested,
           remote_bytes_transferred,
           remote_transfer_millis,
           created_at,
           updated_at
    FROM import_jobs
"""

FINISHED_JOB_STATUSES = ("completed", "failed", "cancelled")
ACTIVE_JOB_STATUSES = ("queued", "running", "cancelling")
FAILED_JOB_STATUSES = ("failed", "cancelled")
COMPLETED_JOB_STATUSES = ("completed",)


class ImportJobNotFoundError(LookupError):
    """Raised when the target background job no longer exists."""


class ImportJobCancellationNotAllowedError(RuntimeError):
    """Raised when a job type does not support user cancellation."""


def create_import_job(
    settings: Settings,
    *,
    source_path: str,
    folder_id: int | None = None,
    requested_title: str | None = None,
    requested_tags: list[str] | None = None,
    task_name: str | None = None,
) -> ImportJob:
    resolved_task_name = _resolve_task_name(
        task_name,
        requested_title=requested_title,
        source_path=source_path,
    )
    with connect_database(settings) as connection:
        cursor = connection.execute(
            """
            INSERT INTO import_jobs (
                source_path,
                folder_id,
                requested_title,
                requested_tags_json,
                job_kind,
                task_name,
                status,
                progress_percent,
                cancel_requested
            )
            VALUES (?, ?, ?, ?, 'import', ?, 'queued', 0, 0)
            """,
            (
                source_path,
                folder_id,
                requested_title,
                encode_tags(requested_tags),
                resolved_task_name,
            ),
        )
        connection.commit()
        row = _fetch_job_row(connection, cursor.lastrowid)

    return _row_to_import_job(row)


def create_delete_job(
    settings: Settings,
    *,
    source_path: str,
    requested_title: str,
    task_name: str,
    target_video_id: int,
) -> ImportJob:
    with connect_database(settings) as connection:
        cursor = connection.execute(
            """
            INSERT INTO import_jobs (
                source_path,
                requested_title,
                requested_tags_json,
                job_kind,
                task_name,
                status,
                progress_percent,
                target_video_id,
                cancel_requested
            )
            VALUES (?, ?, '[]', 'delete', ?, 'queued', 0, ?, 0)
            """,
            (source_path, requested_title, task_name, target_video_id),
        )
        connection.commit()
        row = _fetch_job_row(connection, cursor.lastrowid)

    return _row_to_import_job(row)


def create_cache_job(
    settings: Settings,
    *,
    source_path: str,
    requested_title: str,
    task_name: str,
    target_video_id: int,
) -> ImportJob:
    with connect_database(settings) as connection:
        cursor = connection.execute(
            """
            INSERT INTO import_jobs (
                source_path,
                requested_title,
                requested_tags_json,
                job_kind,
                task_name,
                status,
                progress_percent,
                target_video_id,
                cancel_requested,
                remote_bytes_transferred,
                remote_transfer_millis
            )
            VALUES (?, ?, '[]', 'cache', ?, 'queued', 0, ?, 0, 0, 0)
            """,
            (source_path, requested_title, task_name, target_video_id),
        )
        connection.commit()
        row = _fetch_job_row(connection, cursor.lastrowid)

    return _row_to_import_job(row)


def get_import_job(settings: Settings, job_id: int) -> ImportJob | None:
    with connect_database(settings) as connection:
        row = _fetch_job_row(connection, job_id)

    if row is None:
        return None
    return _row_to_import_job(row)


def list_import_jobs(settings: Settings) -> list[ImportJob]:
    with connect_database(settings) as connection:
        rows = connection.execute(
            f"""
            {JOB_SELECT_SQL}
            ORDER BY id DESC
            """
        ).fetchall()

    return [_row_to_import_job(row) for row in rows]


def list_import_job_ids_by_status(
    settings: Settings,
    *,
    statuses: Sequence[str],
) -> list[int]:
    if not statuses:
        return []

    placeholders = ", ".join("?" for _ in statuses)
    with connect_database(settings) as connection:
        rows = connection.execute(
            f"""
            SELECT id
            FROM import_jobs
            WHERE status IN ({placeholders})
            ORDER BY id
            """,
            tuple(statuses),
        ).fetchall()

    return [int(row["id"]) for row in rows]


def mark_import_job_running(settings: Settings, job_id: int) -> ImportJob:
    return _update_import_job(
        settings,
        job_id,
        status="running",
        progress_percent=10,
        error_message=None,
        video_id=None,
        cancel_requested=False,
    )


def record_import_job_transfer(
    settings: Settings,
    job_id: int,
    *,
    byte_count: int,
    elapsed_seconds: float,
) -> ImportJob:
    elapsed_millis = max(int(round(elapsed_seconds * 1000)), 1 if byte_count > 0 else 0)
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE import_jobs
            SET remote_bytes_transferred = remote_bytes_transferred + ?,
                remote_transfer_millis = remote_transfer_millis + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (max(byte_count, 0), elapsed_millis, job_id),
        )
        connection.commit()
        row = _fetch_job_row(connection, job_id)

    if row is None:
        raise ImportJobNotFoundError(f"Import job does not exist: {job_id}")
    return _row_to_import_job(row)


def update_import_job_progress(settings: Settings, job_id: int, *, progress_percent: int) -> ImportJob:
    job = get_import_job(settings, job_id)
    next_status = "cancelling" if job and job.cancel_requested else "running"
    return _update_import_job(
        settings,
        job_id,
        status=next_status,
        progress_percent=progress_percent,
        error_message=None,
        video_id=job.video_id if job else None,
        cancel_requested=job.cancel_requested if job else False,
    )


def mark_import_job_failed(settings: Settings, job_id: int, *, error_message: str) -> ImportJob:
    return _update_import_job(
        settings,
        job_id,
        status="failed",
        progress_percent=0,
        error_message=error_message,
        video_id=None,
        cancel_requested=False,
    )


def mark_import_job_completed(settings: Settings, job_id: int, *, video_id: int | None = None) -> ImportJob:
    return _update_import_job(
        settings,
        job_id,
        status="completed",
        progress_percent=100,
        error_message=None,
        video_id=video_id,
        cancel_requested=False,
    )


def mark_import_job_cancelled(settings: Settings, job_id: int, *, error_message: str) -> ImportJob:
    job = get_import_job(settings, job_id)
    return _update_import_job(
        settings,
        job_id,
        status="cancelled",
        progress_percent=0,
        error_message=error_message,
        video_id=job.video_id if job else None,
        cancel_requested=True,
    )


def mark_running_import_jobs_interrupted(settings: Settings) -> int:
    with connect_database(settings) as connection:
        cursor = connection.execute(
            """
            UPDATE import_jobs
            SET status = 'failed',
                progress_percent = 0,
                error_message = 'Import interrupted by service restart.',
                video_id = NULL,
                cancel_requested = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('running', 'cancelling')
            """
        )
        connection.commit()
    return int(cursor.rowcount)


def request_cancel_job(settings: Settings, job_id: int) -> ImportJob | None:
    job = get_import_job(settings, job_id)
    if job is None:
        return None
    if job.status in FINISHED_JOB_STATUSES:
        return job
    if job.job_kind == "delete":
        raise ImportJobCancellationNotAllowedError("Delete jobs cannot be cancelled.")
    if job.status == "queued":
        return mark_import_job_cancelled(settings, job_id, error_message="Cancelled by user.")

    return _update_import_job(
        settings,
        job_id,
        status="cancelling",
        progress_percent=job.progress_percent,
        error_message=None,
        video_id=job.video_id,
        cancel_requested=True,
    )


def request_cancel_all_active_jobs(settings: Settings) -> int:
    with connect_database(settings) as connection:
        queued_cursor = connection.execute(
            """
            UPDATE import_jobs
            SET status = 'cancelled',
                progress_percent = 0,
                error_message = 'Cancelled by user.',
                cancel_requested = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE status = 'queued'
              AND job_kind != 'delete'
            """
        )
        running_cursor = connection.execute(
            """
            UPDATE import_jobs
            SET status = 'cancelling',
                cancel_requested = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('running', 'cancelling')
              AND job_kind != 'delete'
            """
        )
        connection.commit()
    return int(queued_cursor.rowcount) + int(running_cursor.rowcount)


def delete_import_jobs_by_statuses(settings: Settings, *, statuses: Sequence[str]) -> int:
    if not statuses:
        return 0

    placeholders = ", ".join("?" for _ in statuses)
    with connect_database(settings) as connection:
        cursor = connection.execute(
            f"""
            DELETE FROM import_jobs
            WHERE status IN ({placeholders})
            """,
            tuple(statuses),
        )
        connection.commit()
    return int(cursor.rowcount)


def delete_completed_import_jobs(settings: Settings) -> int:
    return delete_import_jobs_by_statuses(settings, statuses=COMPLETED_JOB_STATUSES)


def delete_failed_import_jobs(settings: Settings) -> int:
    return delete_import_jobs_by_statuses(settings, statuses=FAILED_JOB_STATUSES)


def find_active_delete_job(settings: Settings, *, target_video_id: int) -> ImportJob | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            f"""
            {JOB_SELECT_SQL}
            WHERE job_kind = 'delete'
              AND target_video_id = ?
              AND status IN ('queued', 'running', 'cancelling')
            ORDER BY id DESC
            LIMIT 1
            """,
            (target_video_id,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_import_job(row)


def find_active_cache_job(settings: Settings, *, target_video_id: int) -> ImportJob | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            f"""
            {JOB_SELECT_SQL}
            WHERE job_kind = 'cache'
              AND target_video_id = ?
              AND status IN ('queued', 'running', 'cancelling')
            ORDER BY id DESC
            LIMIT 1
            """,
            (target_video_id,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_import_job(row)


def _update_import_job(
    settings: Settings,
    job_id: int,
    *,
    status: str,
    progress_percent: int,
    error_message: str | None,
    video_id: int | None,
    cancel_requested: bool,
) -> ImportJob:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE import_jobs
            SET status = ?,
                progress_percent = ?,
                error_message = ?,
                video_id = ?,
                cancel_requested = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, progress_percent, error_message, video_id, int(cancel_requested), job_id),
        )
        connection.commit()
        row = _fetch_job_row(connection, job_id)

    if row is None:
        raise ImportJobNotFoundError(f"Import job does not exist: {job_id}")
    return _row_to_import_job(row)


def _fetch_job_row(connection: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    return connection.execute(
        f"""
        {JOB_SELECT_SQL}
        WHERE id = ?
        """,
        (job_id,),
    ).fetchone()


def _resolve_task_name(
    task_name: str | None,
    *,
    requested_title: str | None,
    source_path: str,
) -> str:
    if task_name and task_name.strip():
        return task_name.strip()
    if requested_title and requested_title.strip():
        return requested_title.strip()
    path = Path(source_path)
    if path.stem:
        return path.stem
    if path.name:
        return path.name
    return source_path


def _row_to_import_job(row: sqlite3.Row) -> ImportJob:
    remote_bytes_transferred = int(row["remote_bytes_transferred"] or 0)
    remote_transfer_millis = int(row["remote_transfer_millis"] or 0)
    transfer_speed_bytes_per_second = None
    if remote_bytes_transferred > 0 and remote_transfer_millis > 0:
        transfer_speed_bytes_per_second = remote_bytes_transferred / (remote_transfer_millis / 1000)

    return ImportJob(
        id=row["id"],
        source_path=row["source_path"],
        folder_id=row["folder_id"],
        requested_title=row["requested_title"],
        requested_tags=decode_tags(row["requested_tags_json"]),
        job_kind=row["job_kind"] or "import",
        task_name=_resolve_task_name(
            row["task_name"],
            requested_title=row["requested_title"],
            source_path=row["source_path"],
        ),
        status=row["status"],
        progress_percent=row["progress_percent"],
        error_message=row["error_message"],
        video_id=row["video_id"],
        target_video_id=row["target_video_id"],
        cancel_requested=bool(row["cancel_requested"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        remote_bytes_transferred=remote_bytes_transferred,
        remote_transfer_millis=remote_transfer_millis,
        transfer_speed_bytes_per_second=transfer_speed_bytes_per_second,
    )
