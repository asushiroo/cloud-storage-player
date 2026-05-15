import asyncio
import time
from pathlib import Path
from threading import Event, Thread

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.keys import load_or_create_content_key
from app.db.schema import initialize_database
from app.media.crypto import encrypt_segment
from app.core.security import hash_password
from app.main import create_app
from app.repositories.video_segments import NewVideoSegment, create_video_segments
from app.storage.mock import MockStorageBackend
from app.api.routes.stream import ManagedStreamingResponse, iterate_stream_chunks
from tests.test_streaming_remote_payload import _create_remote_only_segment_video, build_settings as build_remote_only_settings
from app.models.segments import VideoSegment
from app.repositories.videos import get_video
from app.repositories.video_segments import list_video_segments
from app.services.imports import import_local_video
from app.services.segment_local_paths import resolve_segment_local_staging_path
from app.services.segment_local_paths import serialize_local_staging_path
from app.storage.baidu_api import BaiduApiError
from app.repositories.videos import create_video


def build_client(tmp_path: Path, password: str = "shared-secret") -> tuple[TestClient, Settings, str]:
    settings = Settings(
        session_secret="test-session-secret-123456",
        password_hash=hash_password(password),
        database_path=tmp_path / "stream.db",
        covers_path=tmp_path / "covers",
        content_key_path=tmp_path / "keys" / "content.key",
        segment_staging_path=tmp_path / "segments",
        mock_storage_path=tmp_path / "mock-remote",
        segment_size_bytes=512,
    )
    return TestClient(create_app(settings)), settings, password


def login(client: TestClient, password: str) -> None:
    response = client.post("/api/auth/login", json={"password": password})
    assert response.status_code == 200


def create_sample_video(output_path: Path) -> Path:
    import subprocess

    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=160x90:d=1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output_path


def remove_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    root.rmdir()


def test_stream_requires_authentication(tmp_path: Path) -> None:
    client, settings, _ = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "stream.mp4")
    job = import_local_video(settings, source_path=str(source_path))

    response = client.get(f"/api/videos/{job.video_id}/stream")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_stream_response_closes_iterator_on_client_disconnect() -> None:
    iterator_closed = Event()

    def tracked_iterator():
        try:
            yield b"first-chunk"
            yield b"second-chunk"
        finally:
            iterator_closed.set()

    response = ManagedStreamingResponse(
        iterate_stream_chunks(tracked_iterator()),
        media_type="video/mp4",
    )

    async def receive():
        return {"type": "http.disconnect"}

    first_body_sent = False

    async def send(message):
        nonlocal first_body_sent
        if message["type"] != "http.response.body" or not message.get("more_body"):
            return
        if not first_body_sent:
            first_body_sent = True
            raise OSError("client disconnected")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/videos/1/stream",
        "raw_path": b"/api/videos/1/stream",
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "root_path": "",
    }

    asyncio.run(response(scope, receive, send))

    assert iterator_closed.wait(timeout=1.0)


def test_stream_returns_full_file(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "full.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    login(client, password)

    response = client.get(f"/api/videos/{job.video_id}/stream")

    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == str(len(file_bytes))
    assert response.content == file_bytes


def test_stream_returns_partial_content_for_range_request(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "range.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": "bytes=0-31"},
    )

    assert response.status_code == 206
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-length"] == "32"
    assert response.headers["content-range"] == f"bytes 0-31/{len(file_bytes)}"
    assert response.content == file_bytes[:32]


def test_stream_supports_suffix_ranges(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "suffix.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": "bytes=-24"},
    )

    assert response.status_code == 206
    assert response.headers["content-length"] == "24"
    assert response.content == file_bytes[-24:]


def test_stream_rejects_unsatisfiable_ranges(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "invalid-range.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": f"bytes={len(file_bytes)}-{len(file_bytes) + 10}"},
    )

    assert response.status_code == 416
    assert response.headers["content-range"] == f"bytes */{len(file_bytes)}"


def test_stream_can_fallback_to_local_encrypted_segments_when_source_is_removed(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "removed.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    login(client, password)

    response = client.get(f"/api/videos/{job.video_id}/stream")

    assert response.status_code == 200
    assert response.content == file_bytes


def test_stream_can_fallback_to_mock_remote_when_source_and_local_segments_are_removed(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "remote-fallback.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    remove_tree(settings.segment_staging_dir / str(job.video_id))
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": "bytes=16-127"},
    )

    assert response.status_code == 206
    assert response.headers["content-length"] == str(127 - 16 + 1)
    assert response.content == file_bytes[16:128]


def test_stream_remote_fallback_caches_downloaded_segments_without_full_exists_scan(monkeypatch, tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "remote-cache-window.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    remove_tree(settings.segment_staging_dir / str(job.video_id))

    segments = list_video_segments(settings, video_id=job.video_id)
    assert len(segments) >= 1
    storage = MockStorageBackend(settings.mock_storage_dir)
    exists_calls: list[str] = []
    download_calls: list[str] = []

    class CountingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            download_calls.append(remote_path)
            return storage.download_bytes(remote_path)

        def exists(self, remote_path: str) -> bool:
            exists_calls.append(remote_path)
            return storage.exists(remote_path)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: CountingStorage())
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": "bytes=0-31"},
    )

    assert response.status_code == 206
    assert response.content == file_bytes[:32]
    assert len(exists_calls) == 0
    assert download_calls[0] == segments[0].cloud_path
    first_segment = segments[0]
    assert first_segment.local_staging_path is not None
    assert resolve_segment_local_staging_path(
        settings,
        video_id=first_segment.video_id,
        segment_index=first_segment.segment_index,
        local_staging_path=first_segment.local_staging_path,
    ).exists()
    if len(segments) > 1:
        deadline = time.time() + 2
        while time.time() < deadline and len(download_calls) < 2:
            time.sleep(0.05)
        assert len(download_calls) >= 2

def test_stream_logs_warning_when_baidu_remote_segment_returns_404(
    monkeypatch,
    caplog,
    tmp_path: Path,
) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "missing-remote.mp4")
    job = import_local_video(settings, source_path=str(source_path))
    remove_tree(settings.segment_staging_dir / str(job.video_id))

    class FailingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            raise BaiduApiError("404 Not Found")

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: FailingStorage())
    login(client, password)

    with caplog.at_level("WARNING", logger="app.services.streaming"):
        response = client.get(
            f"/api/videos/{job.video_id}/stream",
            headers={"Range": "bytes=0-31"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Encrypted segment file is missing."}
    assert any(
        "Failed to fetch encrypted segment from Baidu remote storage" in record.message
        for record in caplog.records
    )


def test_stream_prefetch_stops_at_first_batch_when_stream_ends(monkeypatch, tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    settings.segment_size_bytes = 64
    source_path = create_sample_video(tmp_path / "prefetch-rolling-window.mp4")
    file_bytes = source_path.read_bytes()
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    remove_tree(settings.segment_staging_dir / str(job.video_id))

    segments = list_video_segments(settings, video_id=job.video_id)
    assert len(segments) >= 7
    storage = MockStorageBackend(settings.mock_storage_dir)
    download_calls: list[str] = []

    class TrackingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            download_calls.append(remote_path)
            time.sleep(0.03)
            return storage.download_bytes(remote_path)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: TrackingStorage())
    login(client, password)

    response = client.get(
        f"/api/videos/{job.video_id}/stream",
        headers={"Range": "bytes=0-31"},
    )

    assert response.status_code == 206
    assert response.content == file_bytes[:32]

    deadline = time.time() + 3
    while time.time() < deadline and len(download_calls) < 6:
        time.sleep(0.05)

    # Stream request ends quickly for this test range, so session releases after first prefetch batch.
    assert len(download_calls) == 6


def test_stream_request_does_not_block_other_api_requests(monkeypatch, tmp_path: Path) -> None:
    settings = build_remote_only_settings(tmp_path)
    settings.password_hash = hash_password("shared-secret")
    app = create_app(settings)
    client = TestClient(app)
    video = _create_remote_only_segment_video(
        settings,
        plaintext=b"abcdefghijklmnopqrstuvwxyz0123456789",
    )

    storage = MockStorageBackend(settings.mock_storage_dir)
    release_download = Event()
    started_download = Event()

    class BlockingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            started_download.set()
            release_download.wait(timeout=2)
            return storage.download_bytes(remote_path)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: BlockingStorage())
    login(client, "shared-secret")

    stream_result: dict[str, object] = {}

    def request_stream() -> None:
        stream_result["response"] = client.get(
            f"/api/videos/{video.id}/stream",
            headers={"Range": "bytes=0-31"},
        )

    stream_thread = Thread(target=request_stream)
    stream_thread.start()
    assert started_download.wait(timeout=2)

    videos_response = client.get("/api/videos")

    release_download.set()
    stream_thread.join(timeout=2)
    response = stream_result.get("response")

    assert videos_response.status_code == 200
    assert any(item["id"] == video.id for item in videos_response.json())
    assert response is not None
    assert response.status_code == 206


def test_stream_returns_404_when_source_local_and_remote_segments_are_all_missing(tmp_path: Path) -> None:
    client, settings, password = build_client(tmp_path)
    source_path = create_sample_video(tmp_path / "missing-everywhere.mp4")
    job = import_local_video(settings, source_path=str(source_path))
    source_path.unlink()
    remove_tree(settings.segment_staging_dir / str(job.video_id))

    video = get_video(settings, job.video_id)
    assert video is not None
    assert video.manifest_path is not None
    storage = MockStorageBackend(settings.mock_storage_dir)
    remove_tree(storage.local_path_for(video.manifest_path).parent)
    login(client, password)

    response = client.get(f"/api/videos/{job.video_id}/stream")

    assert response.status_code == 404
    assert response.json() == {"detail": "Encrypted segment file is missing."}


def test_stream_api_can_start_from_remote_only_without_local_cache(monkeypatch, tmp_path: Path) -> None:
    settings = build_remote_only_settings(tmp_path)
    settings.password_hash = hash_password("shared-secret")
    app = create_app(settings)
    client = TestClient(app)
    video = _create_remote_only_segment_video(
        settings,
        plaintext=b"abcdefghijklmnopqrstuvwxyz0123456789",
    )
    storage = MockStorageBackend(settings.mock_storage_dir)

    class TrackingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            return storage.download_bytes(remote_path)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: TrackingStorage())
    login(client, "shared-secret")

    response = client.get(
        f"/api/videos/{video.id}/stream",
        headers={"Range": "bytes=0-15"},
    )

    assert response.status_code == 206
    assert response.content == b"abcdefghijklmnop"


def test_stream_falls_back_to_source_bytes_when_later_remote_segment_is_missing(monkeypatch, tmp_path: Path) -> None:
    settings = build_remote_only_settings(tmp_path)
    settings.password_hash = hash_password("shared-secret")
    initialize_database(settings)
    app = create_app(settings)
    client = TestClient(app)

    file_bytes = b"abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    source_path = tmp_path / "fallback-source.bin"
    source_path.write_bytes(file_bytes)
    video = _create_remote_segment_video_with_source(
        settings,
        plaintext=file_bytes,
        source_path=source_path,
    )

    segments = list_video_segments(settings, video_id=video.id)
    assert len(segments) >= 2
    storage = MockStorageBackend(settings.mock_storage_dir)
    missing_remote_path = segments[1].cloud_path
    assert missing_remote_path is not None
    storage.local_path_for(missing_remote_path).unlink()

    class TrackingStorage:
        def download_bytes(self, remote_path: str) -> bytes:
            return storage.download_bytes(remote_path)

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.services.streaming.build_storage_backend", lambda _settings: TrackingStorage())
    login(client, "shared-secret")

    response = client.get(f"/api/videos/{video.id}/stream")

    assert response.status_code == 200
    assert response.content == file_bytes


def _create_remote_segment_video_with_source(settings: Settings, *, plaintext: bytes, source_path: Path):
    key = load_or_create_content_key(settings)
    video = create_video(
        settings,
        title="Remote Segment With Source",
        mime_type="video/mp4",
        size=len(plaintext),
        manifest_path="/apps/CloudStoragePlayer/mock/manifest.bin",
        source_path=str(source_path),
    )

    segment_length = 32
    segments: list[NewVideoSegment] = []
    storage = MockStorageBackend(settings.mock_storage_dir)
    for index, start in enumerate(range(0, len(plaintext), segment_length)):
        chunk = plaintext[start : start + segment_length]
        encrypted = encrypt_segment(chunk, key, nonce=f"{index:012d}".encode("ascii"))
        remote_path = f"/apps/CloudStoragePlayer/mock/{video.id}/{index}.bin"
        storage.upload_bytes(encrypted.ciphertext + encrypted.tag, remote_path)
        segments.append(
            NewVideoSegment(
                segment_index=index,
                original_offset=start,
                original_length=len(chunk),
                ciphertext_size=encrypted.ciphertext_size,
                plaintext_sha256=encrypted.plaintext_sha256,
                nonce_b64=encrypted.nonce_b64,
                tag_b64=encrypted.tag_b64,
                cloud_path=remote_path,
                local_staging_path=serialize_local_staging_path(
                    settings,
                    settings.segment_staging_dir / str(video.id) / "segments" / f"{index:06d}.cspseg",
                ),
            )
        )

    create_video_segments(
        settings,
        video_id=video.id,
        segments=segments,
    )
    return video
