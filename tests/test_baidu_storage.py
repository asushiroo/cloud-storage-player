import hashlib
from pathlib import Path

from app.core.config import Settings
from app.main import create_app
from app.services.baidu_oauth import set_baidu_refresh_token
from app.storage.baidu import BaiduStorageBackend, normalize_baidu_path
from app.storage.baidu_api import BaiduToken


class FakeBaiduStorageApi:
    def __init__(self) -> None:
        self.refresh_calls: list[tuple] = []
        self.precreate_calls: list[dict] = []
        self.upload_calls: list[dict] = []
        self.create_calls: list[dict] = []
        self.list_calls: list[dict] = []
        self.filemetas_calls: list[dict] = []
        self.download_calls: list[dict] = []

    def refresh_access_token(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> BaiduToken:
        self.refresh_calls.append((client_id, client_secret, refresh_token))
        return BaiduToken(
            access_token="access-token",
            refresh_token=refresh_token,
            expires_in=3600,
            scope="basic,netdisk",
        )

    def precreate_file(self, **kwargs):
        self.precreate_calls.append(kwargs)
        return {"errno": 0, "return_type": 1, "uploadid": "upload-id", "block_list": [0]}

    def upload_tmpfile(self, **kwargs):
        self.upload_calls.append(kwargs)
        return "uploaded-md5"

    def create_file(self, **kwargs):
        self.create_calls.append(kwargs)
        return {"errno": 0, "path": kwargs["remote_path"]}

    def list_directory(self, **kwargs):
        self.list_calls.append(kwargs)
        return [
            {
                "fs_id": 123456,
                "path": kwargs["dir_path"] + "/000000.cspseg",
                "server_filename": "000000.cspseg",
            }
        ]

    def get_file_metas(self, **kwargs):
        self.filemetas_calls.append(kwargs)
        return [{"dlink": "https://d.pcs.baidu.com/file/demo"}]

    def download_dlink(self, **kwargs):
        self.download_calls.append(kwargs)
        return b"remote-bytes"


def build_settings(tmp_path: Path, monkeypatch) -> Settings:
    monkeypatch.setenv("BAIDU_APP_KEY", "demo-app-key")
    monkeypatch.setenv("BAIDU_SECRET_KEY", "demo-secret-key")
    settings = Settings(
        session_secret="test-session-secret-123456",
        database_path=tmp_path / "baidu-storage.db",
    )
    create_app(settings)
    set_baidu_refresh_token(settings, "refresh-token")
    return settings


def test_normalize_baidu_path_prefixes_apps_root() -> None:
    assert normalize_baidu_path("/CloudStoragePlayer/videos/1/manifest.json") == (
        "/apps/CloudStoragePlayer/videos/1/manifest.json"
    )
    assert normalize_baidu_path("/apps/CloudStoragePlayer/videos/1/manifest.json") == (
        "/apps/CloudStoragePlayer/videos/1/manifest.json"
    )


def test_baidu_storage_backend_uploads_bytes(monkeypatch, tmp_path: Path) -> None:
    settings = build_settings(tmp_path, monkeypatch)
    api = FakeBaiduStorageApi()
    backend = BaiduStorageBackend(settings, api=api)
    payload = b"hello baidu"

    backend.upload_bytes(payload, "/CloudStoragePlayer/videos/1/manifest.json")

    assert api.refresh_calls == [("demo-app-key", "demo-secret-key", "refresh-token")]
    assert api.precreate_calls[0]["remote_path"] == "/apps/CloudStoragePlayer/videos/1/manifest.json"
    assert api.precreate_calls[0]["block_list"] == [hashlib.md5(payload).hexdigest()]
    assert api.upload_calls[0]["remote_path"] == "/apps/CloudStoragePlayer/videos/1/manifest.json"
    assert api.upload_calls[0]["payload"] == payload
    assert api.create_calls[0]["block_list"] == ["uploaded-md5"]


def test_baidu_storage_backend_downloads_bytes(monkeypatch, tmp_path: Path) -> None:
    settings = build_settings(tmp_path, monkeypatch)
    api = FakeBaiduStorageApi()
    backend = BaiduStorageBackend(settings, api=api)

    payload = backend.download_bytes("/CloudStoragePlayer/videos/1/segments/000000.cspseg")

    assert payload == b"remote-bytes"
    assert api.list_calls[0]["dir_path"] == "/apps/CloudStoragePlayer/videos/1/segments"
    assert api.filemetas_calls[0]["fsids"] == [123456]
    assert api.download_calls[0] == {
        "dlink": "https://d.pcs.baidu.com/file/demo",
        "access_token": "access-token",
    }
