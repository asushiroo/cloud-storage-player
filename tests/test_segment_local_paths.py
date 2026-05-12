from pathlib import Path

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.repositories.settings import set_setting
from app.services.segment_local_paths import (
    build_segment_local_staging_path,
    coerce_local_staging_suffix,
    resolve_segment_local_staging_path,
    serialize_local_staging_path,
)
from app.services.settings import SEGMENT_CACHE_ROOT_PATH_KEY


def build_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password("shared-secret"),
        database_path=tmp_path / "paths.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "data" / "segments",
        mock_storage_path=tmp_path / "mock-remote",
    )
    initialize_database(settings)
    return settings


def test_local_staging_paths_are_serialized_as_cache_root_suffix(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    segment_path = build_segment_local_staging_path(
        settings,
        video_id=42,
        segment_index=3,
    )

    stored = serialize_local_staging_path(settings, segment_path)
    resolved = resolve_segment_local_staging_path(
        settings,
        video_id=42,
        segment_index=3,
        local_staging_path=stored,
    )

    assert stored == "42/segments/000003.cspseg"
    assert resolved == segment_path


def test_resolve_segment_local_staging_path_rejects_legacy_absolute_path(
    tmp_path: Path,
) -> None:
    settings = build_settings(tmp_path)
    try:
        resolve_segment_local_staging_path(
            settings,
            video_id=9,
            segment_index=3,
            local_staging_path="/legacy-root/data/segments/9/segments/000003.cspseg",
        )
    except ValueError as exc:
        assert "cache-root-relative" in str(exc)
    else:
        raise AssertionError("Expected legacy absolute path to be rejected.")


def test_segment_local_paths_follow_runtime_cache_root_setting(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    custom_root = tmp_path / "custom-cache-root"
    set_setting(
        settings,
        key=SEGMENT_CACHE_ROOT_PATH_KEY,
        value=str(custom_root),
    )

    resolved = resolve_segment_local_staging_path(
        settings,
        video_id=5,
        segment_index=1,
        local_staging_path="5/segments/000001.cspseg",
    )

    assert resolved == custom_root / "5" / "segments" / "000001.cspseg"


def test_coerce_local_staging_suffix_extracts_suffix_from_absolute_path(tmp_path: Path) -> None:
    _ = build_settings(tmp_path)

    coerced = coerce_local_staging_suffix(
        "D:/old/cache/data/segments/7/segments/000123.cspseg",
        video_id=7,
        segment_index=123,
    )

    assert coerced == "7/segments/000123.cspseg"
