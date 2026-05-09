from __future__ import annotations

from app.core.config import Settings
from app.db.connection import connect_database
from app.models.settings import Setting


def get_setting(settings: Settings, key: str) -> Setting | None:
    with connect_database(settings) as connection:
        row = connection.execute(
            """
            SELECT key, value, updated_at
            FROM settings
            WHERE key = ?
            """,
            (key,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_setting(row)


def set_setting(settings: Settings, *, key: str, value: str) -> Setting:
    with connect_database(settings) as connection:
        connection.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT key, value, updated_at
            FROM settings
            WHERE key = ?
            """,
            (key,),
        ).fetchone()

    return _row_to_setting(row)


def _row_to_setting(row: object) -> Setting:
    return Setting(
        key=row["key"],
        value=row["value"],
        updated_at=row["updated_at"],
    )
