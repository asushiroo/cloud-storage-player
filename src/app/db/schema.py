from __future__ import annotations

import sqlite3

from app.core.config import Settings
from app.db.connection import connect_database

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    cover_path TEXT,
    poster_path TEXT,
    mime_type TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL,
    manifest_path TEXT,
    source_path TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]',
    content_fingerprint TEXT,
    is_visible INTEGER NOT NULL DEFAULT 1,
    manifest_sync_dirty INTEGER NOT NULL DEFAULT 0,
    manifest_sync_requested_at TEXT,
    valid_play_count INTEGER NOT NULL DEFAULT 0,
    total_session_count INTEGER NOT NULL DEFAULT 0,
    total_watch_seconds REAL NOT NULL DEFAULT 0,
    last_watched_at TEXT,
    last_position_seconds REAL NOT NULL DEFAULT 0,
    avg_completion_ratio REAL NOT NULL DEFAULT 0,
    bounce_count INTEGER NOT NULL DEFAULT 0,
    bounce_rate REAL NOT NULL DEFAULT 0,
    rewatch_score REAL NOT NULL DEFAULT 0,
    interest_score REAL NOT NULL DEFAULT 0,
    popularity_score REAL NOT NULL DEFAULT 0,
    resume_score REAL NOT NULL DEFAULT 0,
    recommendation_score REAL NOT NULL DEFAULT 0,
    cache_priority REAL NOT NULL DEFAULT 0,
    like_count INTEGER NOT NULL DEFAULT 0,
    highlight_start_seconds REAL,
    highlight_end_seconds REAL,
    highlight_bucket_count INTEGER NOT NULL DEFAULT 20,
    highlight_heatmap_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS import_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    requested_title TEXT,
    requested_tags_json TEXT NOT NULL DEFAULT '[]',
    job_kind TEXT NOT NULL DEFAULT 'import',
    task_name TEXT,
    status TEXT NOT NULL,
    progress_percent INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    video_id INTEGER REFERENCES videos(id) ON DELETE SET NULL,
    target_video_id INTEGER REFERENCES videos(id) ON DELETE SET NULL,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    remote_bytes_transferred INTEGER NOT NULL DEFAULT 0,
    remote_transfer_millis INTEGER NOT NULL DEFAULT 0,
    remote_transfer_started_at_millis INTEGER,
    remote_transfer_updated_at_millis INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS video_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    segment_index INTEGER NOT NULL,
    original_offset INTEGER NOT NULL,
    original_length INTEGER NOT NULL,
    ciphertext_size INTEGER NOT NULL,
    plaintext_sha256 TEXT NOT NULL,
    nonce_b64 TEXT NOT NULL,
    tag_b64 TEXT NOT NULL,
    cloud_path TEXT,
    local_staging_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS video_watch_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    session_token TEXT NOT NULL UNIQUE,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    accumulated_watch_seconds REAL NOT NULL DEFAULT 0,
    last_position_seconds REAL NOT NULL DEFAULT 0,
    max_position_seconds REAL NOT NULL DEFAULT 0,
    valid_play_recorded INTEGER NOT NULL DEFAULT 0,
    bounce_recorded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tag_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_value TEXT NOT NULL,
    tag_level TEXT NOT NULL,
    interest_sum REAL NOT NULL DEFAULT 0,
    interest_count INTEGER NOT NULL DEFAULT 0,
    preference_score REAL NOT NULL DEFAULT 0,
    exposure_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tag_value, tag_level)
);

CREATE TABLE IF NOT EXISTS video_cache_entries (
    video_id INTEGER PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
    cached_size_bytes INTEGER NOT NULL DEFAULT 0,
    cached_segment_count INTEGER NOT NULL DEFAULT 0,
    total_segment_count INTEGER NOT NULL DEFAULT 0,
    cache_root_relative_segments_dir TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def initialize_database(settings: Settings) -> None:
    with connect_database(settings) as connection:
        _ensure_pragmas(connection)
        connection.executescript(SCHEMA_SQL)
        _migrate_legacy_schema(connection)
        _ensure_column(connection, "videos", "cover_path", "TEXT")
        _ensure_column(connection, "videos", "poster_path", "TEXT")
        _ensure_column(connection, "videos", "tags_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(connection, "videos", "content_fingerprint", "TEXT")
        _ensure_column(connection, "videos", "is_visible", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(connection, "videos", "manifest_sync_dirty", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "manifest_sync_requested_at", "TEXT")
        _ensure_column(connection, "videos", "valid_play_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "total_session_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "total_watch_seconds", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "last_watched_at", "TEXT")
        _ensure_column(connection, "videos", "last_position_seconds", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "avg_completion_ratio", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "bounce_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "bounce_rate", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "rewatch_score", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "interest_score", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "popularity_score", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "resume_score", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "recommendation_score", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "cache_priority", "REAL NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "like_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "videos", "highlight_start_seconds", "REAL")
        _ensure_column(connection, "videos", "highlight_end_seconds", "REAL")
        _ensure_column(connection, "videos", "highlight_bucket_count", "INTEGER NOT NULL DEFAULT 20")
        _ensure_column(connection, "videos", "highlight_heatmap_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(connection, "import_jobs", "requested_tags_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(connection, "import_jobs", "job_kind", "TEXT NOT NULL DEFAULT 'import'")
        _ensure_column(connection, "import_jobs", "task_name", "TEXT")
        _ensure_column(connection, "import_jobs", "target_video_id", "INTEGER REFERENCES videos(id) ON DELETE SET NULL")
        _ensure_column(connection, "import_jobs", "cancel_requested", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "import_jobs", "remote_bytes_transferred", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "import_jobs", "remote_transfer_millis", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "import_jobs", "remote_transfer_started_at_millis", "INTEGER")
        _ensure_column(connection, "import_jobs", "remote_transfer_updated_at_millis", "INTEGER")
        _ensure_column(connection, "video_cache_entries", "cached_size_bytes", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "video_cache_entries", "cached_segment_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "video_cache_entries", "total_segment_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "video_cache_entries", "cache_root_relative_segments_dir", "TEXT")
        _ensure_column(connection, "video_cache_entries", "updated_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")
        _rebuild_cache_entries(connection)
        connection.commit()


def _ensure_pragmas(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")


def _migrate_legacy_schema(connection: sqlite3.Connection) -> None:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {row["name"] for row in rows}
    if "folders" in table_names:
        connection.execute("DROP TABLE IF EXISTS folders")
    if "import_jobs" in table_names:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(import_jobs)").fetchall()}
        if "folder_id" in columns:
            _rebuild_import_jobs_table_without_folder(connection)
    if "videos" in table_names:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(videos)").fetchall()}
        if "folder_id" in columns:
            _rebuild_videos_table_without_folder(connection)


def _rebuild_videos_table_without_folder(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS videos_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            cover_path TEXT,
            poster_path TEXT,
            mime_type TEXT NOT NULL,
            size INTEGER NOT NULL DEFAULT 0,
            duration_seconds REAL,
            manifest_path TEXT,
            source_path TEXT,
            tags_json TEXT NOT NULL DEFAULT '[]',
            content_fingerprint TEXT,
            is_visible INTEGER NOT NULL DEFAULT 1,
            manifest_sync_dirty INTEGER NOT NULL DEFAULT 0,
            manifest_sync_requested_at TEXT,
            valid_play_count INTEGER NOT NULL DEFAULT 0,
            total_session_count INTEGER NOT NULL DEFAULT 0,
            total_watch_seconds REAL NOT NULL DEFAULT 0,
            last_watched_at TEXT,
            last_position_seconds REAL NOT NULL DEFAULT 0,
            avg_completion_ratio REAL NOT NULL DEFAULT 0,
            bounce_count INTEGER NOT NULL DEFAULT 0,
            bounce_rate REAL NOT NULL DEFAULT 0,
            rewatch_score REAL NOT NULL DEFAULT 0,
            interest_score REAL NOT NULL DEFAULT 0,
            popularity_score REAL NOT NULL DEFAULT 0,
            resume_score REAL NOT NULL DEFAULT 0,
            recommendation_score REAL NOT NULL DEFAULT 0,
            cache_priority REAL NOT NULL DEFAULT 0,
            like_count INTEGER NOT NULL DEFAULT 0,
            highlight_start_seconds REAL,
            highlight_end_seconds REAL,
            highlight_bucket_count INTEGER NOT NULL DEFAULT 20,
            highlight_heatmap_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO videos_new (
            id, title, cover_path, poster_path, mime_type, size, duration_seconds,
            manifest_path, source_path, tags_json, content_fingerprint, is_visible, manifest_sync_dirty,
            manifest_sync_requested_at, valid_play_count, total_session_count, total_watch_seconds,
            last_watched_at, last_position_seconds, avg_completion_ratio, bounce_count, bounce_rate,
            rewatch_score, interest_score, popularity_score, resume_score, recommendation_score,
            cache_priority, like_count, highlight_start_seconds, highlight_end_seconds,
            highlight_bucket_count, highlight_heatmap_json, created_at
        )
        SELECT
            id, title, cover_path, poster_path, mime_type, size, duration_seconds,
            manifest_path, source_path, tags_json, content_fingerprint, 1, manifest_sync_dirty,
            manifest_sync_requested_at, valid_play_count, total_session_count, total_watch_seconds,
            last_watched_at, last_position_seconds, avg_completion_ratio, bounce_count, bounce_rate,
            rewatch_score, interest_score, popularity_score, resume_score, recommendation_score,
            cache_priority, 0, highlight_start_seconds, highlight_end_seconds,
            highlight_bucket_count, highlight_heatmap_json, created_at
        FROM videos;
        DROP TABLE videos;
        ALTER TABLE videos_new RENAME TO videos;
        """
    )


def _rebuild_import_jobs_table_without_folder(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS import_jobs_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL,
            requested_title TEXT,
            requested_tags_json TEXT NOT NULL DEFAULT '[]',
            job_kind TEXT NOT NULL DEFAULT 'import',
            task_name TEXT,
            status TEXT NOT NULL,
            progress_percent INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            video_id INTEGER REFERENCES videos(id) ON DELETE SET NULL,
            target_video_id INTEGER REFERENCES videos(id) ON DELETE SET NULL,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            remote_bytes_transferred INTEGER NOT NULL DEFAULT 0,
            remote_transfer_millis INTEGER NOT NULL DEFAULT 0,
            remote_transfer_started_at_millis INTEGER,
            remote_transfer_updated_at_millis INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO import_jobs_new (
            id, source_path, requested_title, requested_tags_json, job_kind, task_name, status,
            progress_percent, error_message, video_id, target_video_id, cancel_requested,
            remote_bytes_transferred, remote_transfer_millis, remote_transfer_started_at_millis,
            remote_transfer_updated_at_millis, created_at, updated_at
        )
        SELECT
            id, source_path, requested_title, requested_tags_json, job_kind, task_name, status,
            progress_percent, error_message, video_id, target_video_id, cancel_requested,
            remote_bytes_transferred, remote_transfer_millis, remote_transfer_started_at_millis,
            remote_transfer_updated_at_millis, created_at, updated_at
        FROM import_jobs;
        DROP TABLE import_jobs;
        ALTER TABLE import_jobs_new RENAME TO import_jobs;
        """
    )


def _rebuild_cache_entries(connection: sqlite3.Connection) -> None:
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
        SELECT videos.id,
               0,
               0,
               COALESCE(segment_counts.total_segment_count, 0),
               NULL,
               CURRENT_TIMESTAMP
        FROM videos
        LEFT JOIN (
            SELECT video_id, COUNT(*) AS total_segment_count
            FROM video_segments
            GROUP BY video_id
        ) AS segment_counts
            ON segment_counts.video_id = videos.id
        ON CONFLICT(video_id) DO UPDATE SET
            total_segment_count = excluded.total_segment_count,
            updated_at = CURRENT_TIMESTAMP
        """
    )


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_columns = {row["name"] for row in rows}
    if column_name in existing_columns:
        return

    connection.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
    )
