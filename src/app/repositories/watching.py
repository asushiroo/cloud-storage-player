from __future__ import annotations

from app.core.config import Settings
from app.db.connection import connect_database
from app.models.watching import TagPreference, VideoWatchSession


def get_watch_session(settings: Settings, *, session_token: str) -> VideoWatchSession | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            """
            SELECT id,
                   video_id,
                   session_token,
                   started_at,
                   last_activity_at,
                   completed_at,
                   accumulated_watch_seconds,
                   last_position_seconds,
                   max_position_seconds,
                   valid_play_recorded,
                   bounce_recorded
            FROM video_watch_sessions
            WHERE session_token = ?
            """,
            (session_token,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_watch_session(row)


def create_watch_session(
    settings: Settings,
    *,
    video_id: int,
    session_token: str,
) -> VideoWatchSession:
    with connect_database(settings) as connection:
        connection.execute(
            """
            INSERT INTO video_watch_sessions (
                video_id,
                session_token
            )
            VALUES (?, ?)
            """,
            (video_id, session_token),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT id,
                   video_id,
                   session_token,
                   started_at,
                   last_activity_at,
                   completed_at,
                   accumulated_watch_seconds,
                   last_position_seconds,
                   max_position_seconds,
                   valid_play_recorded,
                   bounce_recorded
            FROM video_watch_sessions
            WHERE session_token = ?
            """,
            (session_token,),
        ).fetchone()

    return _row_to_watch_session(row)


def update_watch_session(
    settings: Settings,
    session_token: str,
    *,
    accumulated_watch_seconds: float,
    last_position_seconds: float,
    max_position_seconds: float,
    valid_play_recorded: bool,
    bounce_recorded: bool,
    completed: bool,
) -> VideoWatchSession:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE video_watch_sessions
            SET last_activity_at = CURRENT_TIMESTAMP,
                completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END,
                accumulated_watch_seconds = ?,
                last_position_seconds = ?,
                max_position_seconds = ?,
                valid_play_recorded = ?,
                bounce_recorded = ?
            WHERE session_token = ?
            """,
            (
                int(completed),
                accumulated_watch_seconds,
                last_position_seconds,
                max_position_seconds,
                int(valid_play_recorded),
                int(bounce_recorded),
                session_token,
            ),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT id,
                   video_id,
                   session_token,
                   started_at,
                   last_activity_at,
                   completed_at,
                   accumulated_watch_seconds,
                   last_position_seconds,
                   max_position_seconds,
                   valid_play_recorded,
                   bounce_recorded
            FROM video_watch_sessions
            WHERE session_token = ?
            """,
            (session_token,),
        ).fetchone()

    return _row_to_watch_session(row)


def list_video_watch_sessions(settings: Settings, *, video_id: int) -> list[VideoWatchSession]:
    with connect_database(settings) as connection:
        rows = connection.execute(
            """
            SELECT id,
                   video_id,
                   session_token,
                   started_at,
                   last_activity_at,
                   completed_at,
                   accumulated_watch_seconds,
                   last_position_seconds,
                   max_position_seconds,
                   valid_play_recorded,
                   bounce_recorded
            FROM video_watch_sessions
            WHERE video_id = ?
            ORDER BY id
            """,
            (video_id,),
        ).fetchall()

    return [_row_to_watch_session(row) for row in rows]


def list_all_watch_sessions(settings: Settings) -> list[VideoWatchSession]:
    with connect_database(settings) as connection:
        rows = connection.execute(
            """
            SELECT id,
                   video_id,
                   session_token,
                   started_at,
                   last_activity_at,
                   completed_at,
                   accumulated_watch_seconds,
                   last_position_seconds,
                   max_position_seconds,
                   valid_play_recorded,
                   bounce_recorded
            FROM video_watch_sessions
            ORDER BY id
            """
        ).fetchall()

    return [_row_to_watch_session(row) for row in rows]


def upsert_tag_preference(
    settings: Settings,
    *,
    tag_value: str,
    tag_level: str,
    interest_sum: float,
    interest_count: int,
    preference_score: float,
    exposure_count: int,
) -> TagPreference:
    with connect_database(settings) as connection:
        connection.execute(
            """
            INSERT INTO tag_preferences (
                tag_value,
                tag_level,
                interest_sum,
                interest_count,
                preference_score,
                exposure_count
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tag_value, tag_level) DO UPDATE SET
                interest_sum = excluded.interest_sum,
                interest_count = excluded.interest_count,
                preference_score = excluded.preference_score,
                exposure_count = excluded.exposure_count,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                tag_value,
                tag_level,
                interest_sum,
                interest_count,
                preference_score,
                exposure_count,
            ),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT tag_value,
                   tag_level,
                   interest_sum,
                   interest_count,
                   preference_score,
                   exposure_count,
                   updated_at
            FROM tag_preferences
            WHERE tag_value = ? AND tag_level = ?
            """,
            (tag_value, tag_level),
        ).fetchone()

    return _row_to_tag_preference(row)


def list_tag_preferences(settings: Settings) -> list[TagPreference]:
    with connect_database(settings) as connection:
        rows = connection.execute(
            """
            SELECT tag_value,
                   tag_level,
                   interest_sum,
                   interest_count,
                   preference_score,
                   exposure_count,
                   updated_at
            FROM tag_preferences
            ORDER BY tag_level, tag_value COLLATE NOCASE
            """
        ).fetchall()

    return [_row_to_tag_preference(row) for row in rows]


def _row_to_watch_session(row: object) -> VideoWatchSession:
    return VideoWatchSession(
        id=row["id"],
        video_id=row["video_id"],
        session_token=row["session_token"],
        started_at=row["started_at"],
        last_activity_at=row["last_activity_at"],
        completed_at=row["completed_at"],
        accumulated_watch_seconds=float(row["accumulated_watch_seconds"] or 0),
        last_position_seconds=float(row["last_position_seconds"] or 0),
        max_position_seconds=float(row["max_position_seconds"] or 0),
        valid_play_recorded=bool(row["valid_play_recorded"]),
        bounce_recorded=bool(row["bounce_recorded"]),
    )


def _row_to_tag_preference(row: object) -> TagPreference:
    return TagPreference(
        tag_value=row["tag_value"],
        tag_level=row["tag_level"],
        interest_sum=float(row["interest_sum"] or 0),
        interest_count=int(row["interest_count"] or 0),
        preference_score=float(row["preference_score"] or 0),
        exposure_count=int(row["exposure_count"] or 0),
        updated_at=row["updated_at"],
    )
