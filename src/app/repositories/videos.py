from __future__ import annotations

import json
import sqlite3

from app.core.config import Settings
from app.core.tags import decode_tags, encode_tags
from app.db.connection import connect_database
from app.models.library import Video

VIDEO_SELECT_SQL = """
    SELECT videos.id,
           videos.title,
           videos.cover_path,
           videos.poster_path,
           videos.mime_type,
           videos.size,
           videos.duration_seconds,
           videos.manifest_path,
           videos.source_path,
           videos.tags_json,
           videos.content_fingerprint,
           videos.manifest_sync_dirty,
           videos.manifest_sync_requested_at,
           videos.valid_play_count,
           videos.total_session_count,
           videos.total_watch_seconds,
           videos.last_watched_at,
           videos.last_position_seconds,
           videos.avg_completion_ratio,
           videos.bounce_count,
           videos.bounce_rate,
           videos.rewatch_score,
           videos.interest_score,
           videos.popularity_score,
           videos.resume_score,
           videos.recommendation_score,
           videos.cache_priority,
           videos.like_count,
           videos.highlight_start_seconds,
           videos.highlight_end_seconds,
           videos.highlight_bucket_count,
           videos.highlight_heatmap_json,
           videos.created_at,
           COUNT(video_segments.id) AS segment_count
    FROM videos
    LEFT JOIN video_segments ON video_segments.video_id = videos.id
"""


def list_videos(
    settings: Settings,
    *,
    q: str | None = None,
    tag: str | None = None,
) -> list[Video]:
    query = VIDEO_SELECT_SQL
    query += " GROUP BY videos.id ORDER BY videos.title COLLATE NOCASE, videos.id"

    with connect_database(settings) as connection:
        rows = connection.execute(query).fetchall()

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
    cover_path: str | None = None,
    poster_path: str | None = None,
    duration_seconds: float | None = None,
    manifest_path: str | None = None,
    source_path: str | None = None,
    content_fingerprint: str | None = None,
) -> Video:
    with connect_database(settings) as connection:
        cursor = connection.execute(
            """
            INSERT INTO videos (
                title,
                cover_path,
                poster_path,
                mime_type,
                size,
                duration_seconds,
                manifest_path,
                source_path,
                tags_json,
                content_fingerprint
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                cover_path,
                poster_path,
                mime_type,
                size,
                duration_seconds,
                manifest_path,
                source_path,
                encode_tags(tags),
                content_fingerprint,
            ),
        )
        connection.commit()
        row = _fetch_video_row(connection, cursor.lastrowid)

    return _row_to_video(row)


def get_video(settings: Settings, video_id: int) -> Video | None:
    with connect_database(settings) as connection:
        row = _fetch_video_row(connection, video_id)

    if row is None:
        return None
    return _row_to_video(row)


def get_video_by_manifest_path(settings: Settings, manifest_path: str) -> Video | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            f"""
            {VIDEO_SELECT_SQL}
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
    return update_video_artwork_paths(
        settings,
        video_id,
        cover_path=cover_path,
        poster_path=_UNCHANGED,
    )


class _UnchangedValue:
    pass


_UNCHANGED = _UnchangedValue()


def update_video_artwork_paths(
    settings: Settings,
    video_id: int,
    *,
    cover_path: str | None | _UnchangedValue = _UNCHANGED,
    poster_path: str | None | _UnchangedValue = _UNCHANGED,
) -> Video:
    assignments: list[str] = []
    parameters: list[object] = []
    if not isinstance(cover_path, _UnchangedValue):
        assignments.append("cover_path = ?")
        parameters.append(cover_path)
    if not isinstance(poster_path, _UnchangedValue):
        assignments.append("poster_path = ?")
        parameters.append(poster_path)
    if not assignments:
        video = get_video(settings, video_id)
        if video is None:
            raise ValueError(f"Video not found: {video_id}")
        return video

    with connect_database(settings) as connection:
        connection.execute(
            f"""
            UPDATE videos
            SET {", ".join(assignments)}
            WHERE id = ?
            """,
            (*parameters, video_id),
        )
        connection.commit()
        row = _fetch_video_row(connection, video_id)

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
        row = _fetch_video_row(connection, video_id)

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
    content_fingerprint: str | None = None,
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
                tags_json = ?,
                content_fingerprint = ?,
                manifest_sync_dirty = 0
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
                content_fingerprint,
                video_id,
            ),
        )
        connection.commit()
        row = _fetch_video_row(connection, video_id)

    return _row_to_video(row)


def delete_video(settings: Settings, video_id: int) -> bool:
    with connect_database(settings) as connection:
        cursor = connection.execute(
            """
            DELETE FROM videos
            WHERE id = ?
            """,
            (video_id,),
        )
        connection.commit()
    return int(cursor.rowcount) > 0


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
        row = _fetch_video_row(connection, video_id)

    return _row_to_video(row)


def update_video_fields(
    settings: Settings,
    video_id: int,
    *,
    title: str,
    tags: list[str] | None,
    content_fingerprint: str | None | _UnchangedValue = _UNCHANGED,
) -> Video:
    assignments = [
        "title = ?",
        "tags_json = ?",
    ]
    parameters: list[object] = [title, encode_tags(tags)]
    if not isinstance(content_fingerprint, _UnchangedValue):
        assignments.append("content_fingerprint = ?")
        parameters.append(content_fingerprint)

    with connect_database(settings) as connection:
        connection.execute(
            f"""
            UPDATE videos
            SET {", ".join(assignments)}
            WHERE id = ?
            """,
            (*parameters, video_id),
        )
        connection.commit()
        row = _fetch_video_row(connection, video_id)

    return _row_to_video(row)


def update_video_metadata(
    settings: Settings,
    video_id: int,
    *,
    title: str,
    tags: list[str] | None,
) -> Video:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE videos
            SET title = ?,
                tags_json = ?,
                manifest_sync_dirty = 1,
                manifest_sync_requested_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, encode_tags(tags), video_id),
        )
        connection.commit()
        row = _fetch_video_row(connection, video_id)

    return _row_to_video(row)


def update_video_analytics(
    settings: Settings,
    video_id: int,
    *,
    valid_play_count: int,
    total_session_count: int,
    total_watch_seconds: float,
    last_watched_at: str | None,
    last_position_seconds: float,
    avg_completion_ratio: float,
    bounce_count: int,
    bounce_rate: float,
    rewatch_score: float,
    interest_score: float,
    popularity_score: float,
    resume_score: float,
    recommendation_score: float,
    cache_priority: float,
    like_count: int,
    highlight_start_seconds: float | None,
    highlight_end_seconds: float | None,
    highlight_bucket_count: int,
    highlight_heatmap: list[float],
) -> Video:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE videos
            SET valid_play_count = ?,
                total_session_count = ?,
                total_watch_seconds = ?,
                last_watched_at = ?,
                last_position_seconds = ?,
                avg_completion_ratio = ?,
                bounce_count = ?,
                bounce_rate = ?,
                rewatch_score = ?,
                interest_score = ?,
                popularity_score = ?,
                resume_score = ?,
                recommendation_score = ?,
                cache_priority = ?,
                like_count = ?,
                highlight_start_seconds = ?,
                highlight_end_seconds = ?,
                highlight_bucket_count = ?,
                highlight_heatmap_json = ?
            WHERE id = ?
            """,
            (
                valid_play_count,
                total_session_count,
                total_watch_seconds,
                last_watched_at,
                last_position_seconds,
                avg_completion_ratio,
                bounce_count,
                bounce_rate,
                rewatch_score,
                interest_score,
                popularity_score,
                resume_score,
                recommendation_score,
                cache_priority,
                like_count,
                highlight_start_seconds,
                highlight_end_seconds,
                highlight_bucket_count,
                json.dumps(highlight_heatmap, ensure_ascii=False, separators=(",", ":")),
                video_id,
            ),
        )
        connection.commit()
        row = _fetch_video_row(connection, video_id)

    return _row_to_video(row)


def mark_video_manifest_sync_clean(settings: Settings, video_id: int) -> Video:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE videos
            SET manifest_sync_dirty = 0
            WHERE id = ?
            """,
            (video_id,),
        )
        connection.commit()
        row = _fetch_video_row(connection, video_id)

    return _row_to_video(row)


def list_dirty_manifest_videos(settings: Settings) -> list[Video]:
    with connect_database(settings) as connection:
        rows = connection.execute(
            f"""
            {VIDEO_SELECT_SQL}
            WHERE videos.manifest_sync_dirty = 1
            GROUP BY videos.id
            ORDER BY videos.id
            """
        ).fetchall()

    return [_row_to_video(row) for row in rows]


def get_video_by_title(settings: Settings, title: str) -> Video | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            f"""
            {VIDEO_SELECT_SQL}
            WHERE videos.title = ?
            GROUP BY videos.id
            """,
            (title,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_video(row)


def get_video_by_content_fingerprint(settings: Settings, content_fingerprint: str) -> Video | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            f"""
            {VIDEO_SELECT_SQL}
            WHERE videos.content_fingerprint = ?
            GROUP BY videos.id
            """,
            (content_fingerprint,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_video(row)


def increment_video_like_count(
    settings: Settings,
    video_id: int,
    *,
    delta: int = 1,
    upper_bound: int = 99,
) -> Video:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE videos
            SET like_count = MIN(MAX(like_count + ?, 0), ?)
            WHERE id = ?
            """,
            (delta, upper_bound, video_id),
        )
        connection.commit()
        row = _fetch_video_row(connection, video_id)

    return _row_to_video(row)


def _fetch_video_row(connection: sqlite3.Connection, video_id: int) -> sqlite3.Row | None:
    return connection.execute(
        f"""
        {VIDEO_SELECT_SQL}
        WHERE videos.id = ?
        GROUP BY videos.id
        """,
        (video_id,),
    ).fetchone()


def _row_to_video(row: sqlite3.Row) -> Video:
    return Video(
        id=row["id"],
        title=row["title"],
        cover_path=row["cover_path"],
        poster_path=row["poster_path"],
        mime_type=row["mime_type"],
        size=row["size"],
        duration_seconds=row["duration_seconds"],
        manifest_path=row["manifest_path"],
        source_path=row["source_path"],
        created_at=row["created_at"],
        segment_count=row["segment_count"],
        tags=decode_tags(row["tags_json"]),
        content_fingerprint=row["content_fingerprint"],
        manifest_sync_dirty=bool(row["manifest_sync_dirty"]),
        manifest_sync_requested_at=row["manifest_sync_requested_at"],
        valid_play_count=row["valid_play_count"],
        total_session_count=row["total_session_count"],
        total_watch_seconds=float(row["total_watch_seconds"] or 0),
        last_watched_at=row["last_watched_at"],
        last_position_seconds=float(row["last_position_seconds"] or 0),
        avg_completion_ratio=float(row["avg_completion_ratio"] or 0),
        bounce_count=row["bounce_count"],
        bounce_rate=float(row["bounce_rate"] or 0),
        rewatch_score=float(row["rewatch_score"] or 0),
        interest_score=float(row["interest_score"] or 0),
        popularity_score=float(row["popularity_score"] or 0),
        resume_score=float(row["resume_score"] or 0),
        recommendation_score=float(row["recommendation_score"] or 0),
        cache_priority=float(row["cache_priority"] or 0),
        like_count=int(row["like_count"] or 0),
        highlight_start_seconds=row["highlight_start_seconds"],
        highlight_end_seconds=row["highlight_end_seconds"],
        highlight_bucket_count=int(row["highlight_bucket_count"] or 20),
        highlight_heatmap=_decode_heatmap(row["highlight_heatmap_json"]),
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


def _decode_heatmap(value: str | None) -> list[float]:
    if not value:
        return []
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    decoded: list[float] = []
    for item in payload:
        try:
            decoded.append(float(item))
        except (TypeError, ValueError):
            decoded.append(0.0)
    return decoded
