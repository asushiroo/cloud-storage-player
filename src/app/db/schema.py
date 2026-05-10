from __future__ import annotations

import sqlite3

from app.core.config import Settings
from app.db.connection import connect_database

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cover_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    cover_path TEXT,
    mime_type TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL,
    manifest_path TEXT,
    source_path TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]',
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
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    requested_title TEXT,
    requested_tags_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    progress_percent INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    video_id INTEGER REFERENCES videos(id) ON DELETE SET NULL,
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
"""


def initialize_database(settings: Settings) -> None:
    with connect_database(settings) as connection:
        connection.executescript(SCHEMA_SQL)
        _ensure_column(connection, "videos", "source_path", "TEXT")
        _ensure_column(connection, "videos", "tags_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(connection, "import_jobs", "requested_tags_json", "TEXT NOT NULL DEFAULT '[]'")
        connection.commit()


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
