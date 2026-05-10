from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.core.config import Settings

SQLITE_TIMEOUT_SECONDS = 30.0
SQLITE_BUSY_TIMEOUT_MS = 30_000


@contextmanager
def connect_database(settings: Settings) -> Iterator[sqlite3.Connection]:
    database_path = settings.database_file
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        database_path,
        timeout=SQLITE_TIMEOUT_SECONDS,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    try:
        yield connection
    finally:
        connection.close()
