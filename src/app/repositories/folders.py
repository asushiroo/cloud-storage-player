from __future__ import annotations

import sqlite3

from app.core.config import Settings
from app.db.connection import connect_database
from app.models.library import Folder


def list_folders(settings: Settings) -> list[Folder]:
    with connect_database(settings) as connection:
        rows = connection.execute(
            """
            SELECT id, name, cover_path, created_at
            FROM folders
            ORDER BY name COLLATE NOCASE, id
            """
        ).fetchall()

    return [_row_to_folder(row) for row in rows]


def create_folder(
    settings: Settings,
    *,
    name: str,
    cover_path: str | None = None,
) -> Folder:
    with connect_database(settings) as connection:
        cursor = connection.execute(
            """
            INSERT INTO folders (name, cover_path)
            VALUES (?, ?)
            """,
            (name, cover_path),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT id, name, cover_path, created_at
            FROM folders
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _row_to_folder(row)


def get_folder(settings: Settings, folder_id: int) -> Folder | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            """
            SELECT id, name, cover_path, created_at
            FROM folders
            WHERE id = ?
            """,
            (folder_id,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_folder(row)


def _row_to_folder(row: sqlite3.Row) -> Folder:
    return Folder(
        id=row["id"],
        name=row["name"],
        cover_path=row["cover_path"],
        created_at=row["created_at"],
    )
