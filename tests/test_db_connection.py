from __future__ import annotations

from app.core.config import Settings
from app.db.connection import (
    SQLITE_BUSY_TIMEOUT_MS,
    SQLITE_TIMEOUT_SECONDS,
    connect_database,
)


def test_database_connection_enables_busy_timeout_and_wal(tmp_path) -> None:
    settings = Settings(
        session_secret="test-secret-123456",
        database_path=tmp_path / "connection.db",
    )

    with connect_database(settings) as connection:
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]

    assert busy_timeout == SQLITE_BUSY_TIMEOUT_MS
    assert journal_mode.lower() == "wal"
    assert synchronous in (1, "1")
    assert SQLITE_TIMEOUT_SECONDS == 30.0
