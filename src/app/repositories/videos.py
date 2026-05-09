from __future__ import annotations

import sqlite3

from app.core.config import Settings
from app.db.connection import connect_database
from app.models.library import Video


def list_videos(settings: Settings, *, folder_id: int | None = None) -> list[Video]:
    query = """
        SELECT id, folder_id, title, cover_path, mime_type, size, duration_seconds,
               manifest_path, source_path, created_at
        FROM videos
    """
    parameters: tuple[object, ...] = ()
    if folder_id is None:
        query += " ORDER BY title COLLATE NOCASE, id"
    else:
        query += " WHERE folder_id = ? ORDER BY title COLLATE NOCASE, id"
        parameters = (folder_id,)

    with connect_database(settings) as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [_row_to_video(row) for row in rows]


def create_video(
    settings: Settings,
    *,
    title: str,
    mime_type: str,
    size: int,
    folder_id: int | None = None,
    cover_path: str | None = None,
    duration_seconds: float | None = None,
    manifest_path: str | None = None,
    source_path: str | None = None,
) -> Video:
    with connect_database(settings) as connection:
        cursor = connection.execute(
            """
            INSERT INTO videos (
                folder_id,
                title,
                cover_path,
                mime_type,
                size,
                duration_seconds,
                manifest_path,
                source_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                folder_id,
                title,
                cover_path,
                mime_type,
                size,
                duration_seconds,
                manifest_path,
                source_path,
            ),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT id, folder_id, title, cover_path, mime_type, size, duration_seconds,
                   manifest_path, source_path, created_at
            FROM videos
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _row_to_video(row)


def get_video(settings: Settings, video_id: int) -> Video | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            """
            SELECT id, folder_id, title, cover_path, mime_type, size, duration_seconds,
                   manifest_path, source_path, created_at
            FROM videos
            WHERE id = ?
            """,
            (video_id,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_video(row)


def update_video_cover_path(
    settings: Settings,
    video_id: int,
    *,
    cover_path: str | None,
) -> Video:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE videos
            SET cover_path = ?
            WHERE id = ?
            """,
            (cover_path, video_id),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT id, folder_id, title, cover_path, mime_type, size, duration_seconds,
                   manifest_path, source_path, created_at
            FROM videos
            WHERE id = ?
            """,
            (video_id,),
        ).fetchone()

    return _row_to_video(row)


def _row_to_video(row: sqlite3.Row) -> Video:
    return Video(
        id=row["id"],
        folder_id=row["folder_id"],
        title=row["title"],
        cover_path=row["cover_path"],
        mime_type=row["mime_type"],
        size=row["size"],
        duration_seconds=row["duration_seconds"],
        manifest_path=row["manifest_path"],
        source_path=row["source_path"],
        created_at=row["created_at"],
    )
