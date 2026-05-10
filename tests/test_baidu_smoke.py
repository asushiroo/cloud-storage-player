from pathlib import Path

import pytest

from app.core.config import Settings
from app.db.schema import initialize_database
from app.services.baidu_oauth import (
    get_baidu_access_token,
    get_baidu_refresh_token,
    set_baidu_access_token,
    set_baidu_refresh_token,
)
from app.services.baidu_smoke import (
    BaiduSmokePrerequisiteError,
    clone_settings,
    copy_baidu_refresh_token,
    normalize_smoke_remote_root,
    persist_latest_refresh_token,
    prepare_runtime_settings,
)


def build_settings(tmp_path: Path) -> Settings:
    return Settings(
        session_secret="test-session-secret-123456",
        database_path=tmp_path / "base.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
    )


def test_copy_baidu_refresh_token_copies_existing_token(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BAIDU_APP_KEY", "demo-app-key")
    base_settings = build_settings(tmp_path)
    initialize_database(base_settings)
    set_baidu_refresh_token(base_settings, "refresh-token")
    set_baidu_access_token(base_settings, "access-token", expires_in=3600)

    target_settings = clone_settings(
        base_settings,
        database_path=tmp_path / "target.db",
        covers_path=tmp_path / "target-covers",
        content_key_path=tmp_path / "target-keys" / "content.key",
        segment_staging_path=tmp_path / "target-segments",
        mock_storage_path=tmp_path / "target-mock-remote",
    )
    prepare_runtime_settings(target_settings)

    copied = copy_baidu_refresh_token(base_settings, targets=[target_settings])

    assert copied == "refresh-token"
    assert get_baidu_refresh_token(target_settings) == "refresh-token"
    assert get_baidu_access_token(target_settings) == "access-token"


def test_copy_baidu_refresh_token_raises_clear_error_when_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BAIDU_APP_KEY", "demo-app-key")
    base_settings = build_settings(tmp_path)
    initialize_database(base_settings)

    target_settings = clone_settings(
        base_settings,
        database_path=tmp_path / "target.db",
        covers_path=tmp_path / "target-covers",
        content_key_path=tmp_path / "target-keys" / "content.key",
        segment_staging_path=tmp_path / "target-segments",
        mock_storage_path=tmp_path / "target-mock-remote",
    )
    prepare_runtime_settings(target_settings)

    with pytest.raises(BaiduSmokePrerequisiteError) as exc_info:
        copy_baidu_refresh_token(base_settings, targets=[target_settings])

    assert "--oauth-code" in str(exc_info.value)
    assert "Authorize URL:" in str(exc_info.value)


def test_normalize_smoke_remote_root_defaults_under_apps() -> None:
    normalized = normalize_smoke_remote_root(None)

    assert normalized.startswith("/apps/CloudStoragePlayer-smoke/")


def test_normalize_smoke_remote_root_rejects_non_apps_prefix() -> None:
    with pytest.raises(ValueError) as exc_info:
        normalize_smoke_remote_root("/CloudStoragePlayer-smoke/demo")

    assert str(exc_info.value) == "remote_root must start with '/apps/'."


def test_persist_latest_refresh_token_writes_back_to_base_settings(tmp_path: Path) -> None:
    base_settings = build_settings(tmp_path)
    initialize_database(base_settings)

    target_settings = clone_settings(
        base_settings,
        database_path=tmp_path / "target.db",
        covers_path=tmp_path / "target-covers",
        content_key_path=tmp_path / "target-keys" / "content.key",
        segment_staging_path=tmp_path / "target-segments",
        mock_storage_path=tmp_path / "target-mock-remote",
    )
    prepare_runtime_settings(target_settings)
    set_baidu_refresh_token(target_settings, "new-refresh-token")
    set_baidu_access_token(target_settings, "new-access-token", expires_in=3600)

    persist_latest_refresh_token(base_settings, candidates=[target_settings])

    assert get_baidu_refresh_token(base_settings) == "new-refresh-token"
    assert get_baidu_access_token(base_settings) == "new-access-token"
