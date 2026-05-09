from pathlib import Path

from app.storage.mock import MockStorageBackend


def test_mock_storage_backend_uploads_and_downloads_files(tmp_path: Path) -> None:
    backend = MockStorageBackend(tmp_path / "mock-remote")
    local_file = tmp_path / "payload.bin"
    local_file.write_bytes(b"hello world")

    backend.upload_file(local_file, "/CloudStoragePlayer/videos/1/segments/000000.cspseg")

    assert backend.exists("/CloudStoragePlayer/videos/1/segments/000000.cspseg")
    assert (
        backend.download_bytes("/CloudStoragePlayer/videos/1/segments/000000.cspseg")
        == b"hello world"
    )


def test_mock_storage_backend_rejects_parent_path_escape(tmp_path: Path) -> None:
    backend = MockStorageBackend(tmp_path / "mock-remote")

    try:
        backend.local_path_for("/CloudStoragePlayer/../escape.bin")
    except ValueError as exc:
        assert str(exc) == "remote_path must not escape the storage root."
    else:
        raise AssertionError("Expected ValueError for invalid remote path.")
