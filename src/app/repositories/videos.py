from __future__ import annotations

import sqlite3

from app.core.config import Settings
from app.core.tags import decode_tags, encode_tags
from app.db.connection import connect_database
from app.models.library import Video


def list_videos(
    settings: Settings,
    *,
    folder_id: int | None = None,
    q: str | None = None,
    tag: str | None = None,
) -> list[Video]:
    query = """
        SELECT videos.id,
               videos.folder_id,
               videos.title,
               videos.cover_path,
               videos.mime_type,
               videos.size,
               videos.duration_seconds,
               videos.manifest_path,
               videos.source_path,
               videos.tags_json,
               videos.created_at,
               COUNT(video_segments.id) AS segment_count
        FROM videos
        LEFT JOIN video_segments ON video_segments.video_id = videos.id
    """
    parameters: tuple[object, ...] = ()
    if folder_id is None:
        query += " GROUP BY videos.id ORDER BY videos.title COLLATE NOCASE, videos.id"
    else:
        query += """
            WHERE videos.folder_id = ?
            GROUP BY videos.id
            ORDER BY videos.title COLLATE NOCASE, videos.id
        """
        parameters = (folder_id,)

    with connect_database(settings) as connection:
        rows = connection.execute(query, parameters).fetchall()

    videos = [_row_to_video(row) for row in rows]
    normalized_query = q.strip().casefold() if q and q.strip() else None
    normalized_tag = tag.strip().casefold() if tag and tag.strip() else None
    if normalized_query is None and normalized_tag is None:
        return videos

    return [
        video
        for video in videos
        if _matches_video_filters(
            video,
            normalized_query=normalized_query,
            normalized_tag=normalized_tag,
        )
    ]


def create_video(
    settings: Settings,
    *,
    title: str,
    mime_type: str,
    size: int,
    tags: list[str] | None = None,
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
                source_path,
                tags_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                encode_tags(tags),
            ),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT videos.id,
                   videos.folder_id,
                   videos.title,
                   videos.cover_path,
                   videos.mime_type,
                   videos.size,
                   videos.duration_seconds,
                   videos.manifest_path,
                   videos.source_path,
                   videos.tags_json,
                   videos.created_at,
                   COUNT(video_segments.id) AS segment_count
            FROM videos
            LEFT JOIN video_segments ON video_segments.video_id = videos.id
            WHERE videos.id = ?
            GROUP BY videos.id
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _row_to_video(row)


def get_video(settings: Settings, video_id: int) -> Video | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            """
            SELECT videos.id,
                   videos.folder_id,
                   videos.title,
                   videos.cover_path,
                   videos.mime_type,
                   videos.size,
                   videos.duration_seconds,
                   videos.manifest_path,
                   videos.source_path,
                   videos.tags_json,
                   videos.created_at,
                   COUNT(video_segments.id) AS segment_count
            FROM videos
            LEFT JOIN video_segments ON video_segments.video_id = videos.id
            WHERE videos.id = ?
            GROUP BY videos.id
            """,
            (video_id,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_video(row)


def get_video_by_manifest_path(settings: Settings, manifest_path: str) -> Video | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            """
            SELECT videos.id,
                   videos.folder_id,
                   videos.title,
                   videos.cover_path,
                   videos.mime_type,
                   videos.size,
                   videos.duration_seconds,
                   videos.manifest_path,
                   videos.source_path,
                   videos.tags_json,
                   videos.created_at,
                   COUNT(video_segments.id) AS segment_count
            FROM videos
            LEFT JOIN video_segments ON video_segments.video_id = videos.id
            WHERE videos.manifest_path = ?
            GROUP BY videos.id
            """,
            (manifest_path,),
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
            SELECT videos.id,
                   videos.folder_id,
                   videos.title,
                   videos.cover_path,
                   videos.mime_type,
                   videos.size,
                   videos.duration_seconds,
                   videos.manifest_path,
                   videos.source_path,
                   videos.tags_json,
                   videos.created_at,
                   COUNT(video_segments.id) AS segment_count
            FROM videos
            LEFT JOIN video_segments ON video_segments.video_id = videos.id
            WHERE videos.id = ?
            GROUP BY videos.id
            """,
            (video_id,),
        ).fetchone()

    return _row_to_video(row)


def update_video_manifest_path(
    settings: Settings,
    video_id: int,
    *,
    manifest_path: str | None,
) -> Video:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE videos
            SET manifest_path = ?
            WHERE id = ?
            """,
            (manifest_path, video_id),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT videos.id,
                   videos.folder_id,
                   videos.title,
                   videos.cover_path,
                   videos.mime_type,
                   videos.size,
                   videos.duration_seconds,
                   videos.manifest_path,
                   videos.source_path,
                   videos.tags_json,
                   videos.created_at,
                   COUNT(video_segments.id) AS segment_count
            FROM videos
            LEFT JOIN video_segments ON video_segments.video_id = videos.id
            WHERE videos.id = ?
            GROUP BY videos.id
            """,
            (video_id,),
        ).fetchone()

    return _row_to_video(row)


def update_video_sync_metadata(
    settings: Settings,
    video_id: int,
    *,
    title: str,
    mime_type: str,
    size: int,
    duration_seconds: float | None,
    manifest_path: str,
    source_path: str | None,
    tags: list[str] | None,
) -> Video:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE videos
            SET title = ?,
                mime_type = ?,
                size = ?,
                duration_seconds = ?,
                manifest_path = ?,
                source_path = ?,
                tags_json = ?
            WHERE id = ?
            """,
            (
                title,
                mime_type,
                size,
                duration_seconds,
                manifest_path,
                source_path,
                encode_tags(tags),
                video_id,
            ),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT videos.id,
                   videos.folder_id,
                   videos.title,
                   videos.cover_path,
                   videos.mime_type,
                   videos.size,
                   videos.duration_seconds,
                   videos.manifest_path,
                   videos.source_path,
                   videos.tags_json,
                   videos.created_at,
                   COUNT(video_segments.id) AS segment_count
            FROM videos
            LEFT JOIN video_segments ON video_segments.video_id = videos.id
            WHERE videos.id = ?
            GROUP BY videos.id
            """,
            (video_id,),
        ).fetchone()

    return _row_to_video(row)


def update_video_tags(
    settings: Settings,
    video_id: int,
    *,
    tags: list[str] | None,
) -> Video:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE videos
            SET tags_json = ?
            WHERE id = ?
            """,
            (encode_tags(tags), video_id),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT videos.id,
                   videos.folder_id,
                   videos.title,
                   videos.cover_path,
                   videos.mime_type,
                   videos.size,
                   videos.duration_seconds,
                   videos.manifest_path,
                   videos.source_path,
                   videos.tags_json,
                   videos.created_at,
                   COUNT(video_segments.id) AS segment_count
            FROM videos
            LEFT JOIN video_segments ON video_segments.video_id = videos.id
            WHERE videos.id = ?
            GROUP BY videos.id
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
        segment_count=row["segment_count"],
        tags=decode_tags(row["tags_json"]),
    )


def _matches_video_filters(
    video: Video,
    *,
    normalized_query: str | None,
    normalized_tag: str | None,
) -> bool:
    if normalized_tag is not None and normalized_tag not in {tag.casefold() for tag in video.tags}:
        return False

    if normalized_query is None:
        return True

    haystacks = [video.title.casefold()]
    if video.source_path:
        haystacks.append(video.source_path.casefold())
    haystacks.extend(tag.casefold() for tag in video.tags)
    return any(normalized_query in value for value in haystacks)
