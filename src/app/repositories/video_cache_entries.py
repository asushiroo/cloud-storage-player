from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.core.config import Settings
from app.db.connection import connect_database


@dataclass(slots=True)
class VideoCacheEntry:
    video_id: int
    cached_size_bytes: int
    cached_segment_count: int
    total_segment_count: int
    cache_root_relative_segments_dir: str | None
    updated_at: str


def upsert_video_cache_entry(
    settings: Settings,
    *,
    video_id: int,
    cached_size_bytes: int,
    cached_segment_count: int,
    total_segment_count: int,
    cache_root_relative_segments_dir: str | None,
) -> VideoCacheEntry:
    with connect_database(settings) as connection:
        connection.execute(
            """
            INSERT INTO video_cache_entries (
                video_id,
                cached_size_bytes,
                cached_segment_count,
                total_segment_count,
                cache_root_relative_segments_dir,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(video_id) DO UPDATE SET
                cached_size_bytes = excluded.cached_size_bytes,
                cached_segment_count = excluded.cached_segment_count,
                total_segment_count = excluded.total_segment_count,
                cache_root_relative_segments_dir = excluded.cache_root_relative_segments_dir,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                video_id,
                max(cached_size_bytes, 0),
                max(cached_segment_count, 0),
                max(total_segment_count, 0),
                cache_root_relative_segments_dir,
            ),
        )
        connection.commit()
        row = _fetch_video_cache_entry_row(connection, video_id=video_id)

    if row is None:
        raise ValueError(f"Video cache entry was not persisted: {video_id}")
    return _row_to_video_cache_entry(row)


def get_video_cache_entry(settings: Settings, *, video_id: int) -> VideoCacheEntry | None:
    with connect_database(settings) as connection:
        row = _fetch_video_cache_entry_row(connection, video_id=video_id)

    if row is None:
        return None
    return _row_to_video_cache_entry(row)


def list_video_cache_entries(settings: Settings) -> list[VideoCacheEntry]:
    with connect_database(settings) as connection:
        rows = connection.execute(
            """
            SELECT video_id,
                   cached_size_bytes,
                   cached_segment_count,
                   total_segment_count,
                   cache_root_relative_segments_dir,
                   updated_at
            FROM video_cache_entries
            WHERE cached_segment_count > 0
            ORDER BY updated_at DESC, video_id DESC
            """
        ).fetchall()

    return [_row_to_video_cache_entry(row) for row in rows]


def delete_video_cache_entry(settings: Settings, *, video_id: int) -> None:
    with connect_database(settings) as connection:
        connection.execute(
            """
            DELETE FROM video_cache_entries
            WHERE video_id = ?
            """,
            (video_id,),
        )
        connection.commit()


def _fetch_video_cache_entry_row(
    connection: sqlite3.Connection,
    *,
    video_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT video_id,
               cached_size_bytes,
               cached_segment_count,
               total_segment_count,
               cache_root_relative_segments_dir,
               updated_at
        FROM video_cache_entries
        WHERE video_id = ?
        """,
        (video_id,),
    ).fetchone()


def _row_to_video_cache_entry(row: sqlite3.Row) -> VideoCacheEntry:
    return VideoCacheEntry(
        video_id=int(row["video_id"]),
        cached_size_bytes=int(row["cached_size_bytes"] or 0),
        cached_segment_count=int(row["cached_segment_count"] or 0),
        total_segment_count=int(row["total_segment_count"] or 0),
        cache_root_relative_segments_dir=row["cache_root_relative_segments_dir"],
        updated_at=row["updated_at"],
    )
