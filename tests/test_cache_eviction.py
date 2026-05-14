from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.repositories.settings import set_setting
from app.repositories.videos import create_video
from app.services.cache_eviction import enforce_cache_limit


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "cache-eviction.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
    )
    initialize_database(settings)
    return settings


def _write_segment_tree(root: Path, *, video_id: int, size_bytes: int) -> Path:
    segment_dir = root / str(video_id) / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    (segment_dir / "000000.cspseg").write_bytes(b"x" * size_bytes)
    return segment_dir


def test_enforce_cache_limit_evicts_old_cache_before_current_import_video(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    set_setting(settings, key="cache_limit_bytes", value=str(512))

    older = create_video(
        settings,
        title="Older",
        mime_type="video/mp4",
        size=1024,
        source_path="older.mp4",
    )
    current = create_video(
        settings,
        title="Current",
        mime_type="video/mp4",
        size=1024,
        source_path="current.mp4",
    )

    older_dir = _write_segment_tree(settings.segment_staging_dir, video_id=older.id, size_bytes=400)
    current_dir = _write_segment_tree(settings.segment_staging_dir, video_id=current.id, size_bytes=400)
    assert older_dir.exists()
    assert current_dir.exists()

    result = enforce_cache_limit(settings, protect_video_ids={current.id})

    assert older.id in result.evicted_video_ids
    assert current.id not in result.evicted_video_ids
    assert not older_dir.exists()
    assert current_dir.exists()


def test_enforce_cache_limit_evicts_lower_priority_cache_first(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    set_setting(settings, key="cache_limit_bytes", value=str(600))

    low_priority = create_video(
        settings,
        title="Low Priority",
        mime_type="video/mp4",
        size=1024,
        source_path="low.mp4",
    )
    high_priority = create_video(
        settings,
        title="High Priority",
        mime_type="video/mp4",
        size=1024,
        source_path="high.mp4",
    )

    # Lower cache_priority should be evicted first.
    from app.repositories.videos import update_video_analytics

    update_video_analytics(
        settings,
        low_priority.id,
        valid_play_count=0,
        total_session_count=0,
        total_watch_seconds=0.0,
        last_watched_at=None,
        last_position_seconds=0.0,
        avg_completion_ratio=0.0,
        bounce_count=0,
        bounce_rate=0.0,
        rewatch_score=0.0,
        interest_score=0.0,
        popularity_score=0.0,
        resume_score=0.0,
        recommendation_score=0.0,
        cache_priority=0.1,
        highlight_start_seconds=None,
        highlight_end_seconds=None,
        highlight_bucket_count=20,
        highlight_heatmap=[],
    )
    update_video_analytics(
        settings,
        high_priority.id,
        valid_play_count=0,
        total_session_count=0,
        total_watch_seconds=0.0,
        last_watched_at=None,
        last_position_seconds=0.0,
        avg_completion_ratio=0.0,
        bounce_count=0,
        bounce_rate=0.0,
        rewatch_score=0.0,
        interest_score=0.0,
        popularity_score=0.0,
        resume_score=0.0,
        recommendation_score=0.0,
        cache_priority=0.9,
        highlight_start_seconds=None,
        highlight_end_seconds=None,
        highlight_bucket_count=20,
        highlight_heatmap=[],
    )

    low_dir = _write_segment_tree(settings.segment_staging_dir, video_id=low_priority.id, size_bytes=400)
    high_dir = _write_segment_tree(settings.segment_staging_dir, video_id=high_priority.id, size_bytes=400)
    assert low_dir.exists()
    assert high_dir.exists()

    result = enforce_cache_limit(settings)

    assert low_priority.id in result.evicted_video_ids
    assert high_priority.id not in result.evicted_video_ids
    assert not low_dir.exists()
    assert high_dir.exists()


def test_enforce_cache_limit_evicts_older_cache_first_when_priority_ties(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    set_setting(settings, key="cache_limit_bytes", value=str(600))

    first = create_video(
        settings,
        title="First",
        mime_type="video/mp4",
        size=1024,
        source_path="first.mp4",
    )
    second = create_video(
        settings,
        title="Second",
        mime_type="video/mp4",
        size=1024,
        source_path="second.mp4",
    )

    first_dir = _write_segment_tree(settings.segment_staging_dir, video_id=first.id, size_bytes=400)
    second_dir = _write_segment_tree(settings.segment_staging_dir, video_id=second.id, size_bytes=400)
    assert first_dir.exists()
    assert second_dir.exists()

    result = enforce_cache_limit(settings)

    assert first.id in result.evicted_video_ids
    assert second.id not in result.evicted_video_ids
    assert not first_dir.exists()
    assert second_dir.exists()
