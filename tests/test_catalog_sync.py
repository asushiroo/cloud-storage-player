from app.services.catalog_sync import _discover_manifest_paths
from app.storage.baidu_api import BaiduApiError
from app.storage.base import StorageEntry


class FakeStorage:
    def list_directory(self, remote_path: str):
        if remote_path == "/apps/root":
            return [StorageEntry(path="/apps/root/video-a", is_dir=True)]
        if remote_path == "/apps/root/videos":
            raise BaiduApiError("Baidu API error -9.")
        raise AssertionError(f"Unexpected list_directory path: {remote_path}")

    def exists(self, remote_path: str) -> bool:
        return remote_path == "/apps/root/video-a/manifest.json"


def test_discover_manifest_paths_ignores_missing_legacy_directory() -> None:
    storage = FakeStorage()

    manifest_paths = _discover_manifest_paths(
        storage,
        root_path="/apps/root",
        content_key=None,
    )

    assert manifest_paths == ["/apps/root/video-a/manifest.json"]
