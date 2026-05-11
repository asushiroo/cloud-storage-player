from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.core.config import Settings
from app.db.connection import connect_database
from app.models.segments import VideoSegment


@dataclass(slots=True)
class NewVideoSegment:
    segment_index: int
    original_offset: int
    original_length: int
    ciphertext_size: int
    plaintext_sha256: str
    nonce_b64: str
    tag_b64: str
    cloud_path: str | None
    local_staging_path: str | None


def create_video_segments(
    settings: Settings,
    *,
    video_id: int,
    segments: list[NewVideoSegment],
) -> list[VideoSegment]:
    if not segments:
        return []

    with connect_database(settings) as connection:
        connection.executemany(
            """
            INSERT INTO video_segments (
                video_id,
                segment_index,
                original_offset,
                original_length,
                ciphertext_size,
                plaintext_sha256,
                nonce_b64,
                tag_b64,
                cloud_path,
                local_staging_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    video_id,
                    segment.segment_index,
                    segment.original_offset,
                    segment.original_length,
                    segment.ciphertext_size,
                    segment.plaintext_sha256,
                    segment.nonce_b64,
                    segment.tag_b64,
                    segment.cloud_path,
                    segment.local_staging_path,
                )
                for segment in segments
            ],
        )
        connection.commit()
        rows = connection.execute(
            """
            SELECT id, video_id, segment_index, original_offset, original_length,
                   ciphertext_size, plaintext_sha256, nonce_b64, tag_b64,
                   cloud_path, local_staging_path, created_at
            FROM video_segments
            WHERE video_id = ?
            ORDER BY segment_index
            """,
            (video_id,),
        ).fetchall()

    return [_row_to_video_segment(row) for row in rows]


def list_video_segments(settings: Settings, *, video_id: int) -> list[VideoSegment]:
    with connect_database(settings) as connection:
        rows = connection.execute(
            """
            SELECT id, video_id, segment_index, original_offset, original_length,
                   ciphertext_size, plaintext_sha256, nonce_b64, tag_b64,
                   cloud_path, local_staging_path, created_at
            FROM video_segments
            WHERE video_id = ?
            ORDER BY segment_index
            """,
            (video_id,),
        ).fetchall()

    return [_row_to_video_segment(row) for row in rows]


def list_all_video_segments(settings: Settings) -> list[VideoSegment]:
    with connect_database(settings) as connection:
        rows = connection.execute(
            """
            SELECT id, video_id, segment_index, original_offset, original_length,
                   ciphertext_size, plaintext_sha256, nonce_b64, tag_b64,
                   cloud_path, local_staging_path, created_at
            FROM video_segments
            ORDER BY video_id, segment_index
            """
        ).fetchall()

    return [_row_to_video_segment(row) for row in rows]


def update_video_segment_local_staging_path(
    settings: Settings,
    segment_id: int,
    *,
    local_staging_path: str | None,
) -> VideoSegment:
    with connect_database(settings) as connection:
        connection.execute(
            """
            UPDATE video_segments
            SET local_staging_path = ?
            WHERE id = ?
            """,
            (local_staging_path, segment_id),
        )
        connection.commit()
        row = connection.execute(
            """
            SELECT id, video_id, segment_index, original_offset, original_length,
                   ciphertext_size, plaintext_sha256, nonce_b64, tag_b64,
                   cloud_path, local_staging_path, created_at
            FROM video_segments
            WHERE id = ?
            """,
            (segment_id,),
        ).fetchone()

    return _row_to_video_segment(row)


def delete_video_segments(settings: Settings, *, video_id: int) -> None:
    with connect_database(settings) as connection:
        connection.execute(
            """
            DELETE FROM video_segments
            WHERE video_id = ?
            """,
            (video_id,),
        )
        connection.commit()


def _row_to_video_segment(row: sqlite3.Row) -> VideoSegment:
    return VideoSegment(
        id=row["id"],
        video_id=row["video_id"],
        segment_index=row["segment_index"],
        original_offset=row["original_offset"],
        original_length=row["original_length"],
        ciphertext_size=row["ciphertext_size"],
        plaintext_sha256=row["plaintext_sha256"],
        nonce_b64=row["nonce_b64"],
        tag_b64=row["tag_b64"],
        cloud_path=row["cloud_path"],
        local_staging_path=row["local_staging_path"],
        created_at=row["created_at"],
    )
