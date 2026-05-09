from __future__ import annotations

import sqlite3

from app.core.config import Settings
from app.db.connection import connect_database
from app.models.imports import ImportJob


def create_import_job(
    settings: Settings,
    *,
    source_path: str,
    folder_id: int | None = None,
    requested_title: str | None = None,
) -> ImportJob:
    with connect_database(settings) as connection:
        cursor = connection.execute(
            """
            INSERT INTO import_jobs (
                source_path,
                folder_id,
                requested_title,
                status,
                progress_percent
            )
            VALUES (?, ?, ?, 'queued', 0)
            """,
            (source_path, folder_id, requested_title),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT id, source_path, folder_id, requested_title, status, progress_percent,
                   error_message, video_id, created_at, updated_at
            FROM import_jobs
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _row_to_import_job(row)


def get_import_job(settings: Settings, job_id: int) -> ImportJob | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            """
            SELECT id, source_path, folder_id, requested_title, status, progress_percent,
                   error_message, video_id, created_at, updated_at
            FROM import_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_import_job(row)


def list_import_jobs(settings: Settings) -> list[ImportJob]:
    with connect_database(settings) as connection:
        rows = connection.execute(
            """
            SELECT id, source_path, folder_id, requested_title, status, progress_percent,
                   error_message, video_id, created_at, updated_at
            FROM import_jobs
            ORDER BY id DESC
            """
        ).fetchall()

    return [_row_to_import_job(row) for row in rows]


def mark_import_job_running(settings: Settings, job_id: int) -> ImportJob:
    return _update_import_job(
        settings,
        job_id,
        status="running",
        progress_percent=10,
        error_message=None,
        video_id=None,
    )


def mark_import_job_failed(settings: Settings, job_id: int, *, error_message: str) -> ImportJob:
    return _update_import_job(
        settings,
        job_id,
        status="failed",
        progress_percent=0,
        error_message=error_message,
        video_id=None,
    )


def mark_import_job_completed(settings: Settings, job_id: int, *, video_id: int) -> ImportJob:
    return _update_import_job(
        settings,
        job_id,
        status="completed",
        progress_percent=100,
        error_message=None,
        video_id=video_id,
    )


def _update_import_job(
    settings: Settings,
    job_id: int,
    *,
    status: str,
    progress_percent: int,
    error_message: str | None,
    video_id: int | None,
) -> ImportJob:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE import_jobs
            SET status = ?,
                progress_percent = ?,
                error_message = ?,
                video_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, progress_percent, error_message, video_id, job_id),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT id, source_path, folder_id, requested_title, status, progress_percent,
                   error_message, video_id, created_at, updated_at
            FROM import_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    return _row_to_import_job(row)


def _row_to_import_job(row: sqlite3.Row) -> ImportJob:
    return ImportJob(
        id=row["id"],
        source_path=row["source_path"],
        folder_id=row["folder_id"],
        requested_title=row["requested_title"],
        status=row["status"],
        progress_percent=row["progress_percent"],
        error_message=row["error_message"],
        video_id=row["video_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
