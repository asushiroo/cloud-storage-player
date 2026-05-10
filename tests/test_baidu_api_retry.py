import httpx
import pytest

from app.storage.baidu_api import BaiduApiError, BaiduOpenApi


class SequenceClient:
    def __init__(self, *, get_actions=None, post_actions=None) -> None:
        self.get_actions = list(get_actions or [])
        self.post_actions = list(post_actions or [])
        self.get_calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.get_calls.append((url, kwargs))
        if not self.get_actions:
            raise AssertionError("No queued GET action.")
        action = self.get_actions.pop(0)
        if isinstance(action, Exception):
            raise action
        return action

    def post(self, url: str, **kwargs):
        self.post_calls.append((url, kwargs))
        if not self.post_actions:
            raise AssertionError("No queued POST action.")
        action = self.post_actions.pop(0)
        if isinstance(action, Exception):
            raise action
        return action

    def close(self) -> None:
        return None


def make_json_response(method: str, url: str, status_code: int, payload: dict) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status_code, request=request, json=payload)


def make_bytes_response(method: str, url: str, status_code: int, payload: bytes) -> httpx.Response:
    request = httpx.Request(method, url)
    return httpx.Response(status_code, request=request, content=payload)


def test_refresh_access_token_retries_on_temporary_authorization_error() -> None:
    client = SequenceClient(
        get_actions=[
            make_json_response(
                "GET",
                "https://openapi.baidu.com/oauth/2.0/token",
                400,
                {
                    "error": "Trigger security policy",
                    "error_description": "Please try again later",
                },
            ),
            make_json_response(
                "GET",
                "https://openapi.baidu.com/oauth/2.0/token",
                200,
                {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "expires_in": 3600,
                    "scope": "basic,netdisk",
                },
            ),
        ]
    )
    sleep_calls: list[float] = []
    api = BaiduOpenApi(client=client, sleep_func=sleep_calls.append, retry_delays=(0.0,))

    token = api.refresh_access_token(
        client_id="demo-app-key",
        client_secret="demo-secret-key",
        refresh_token="demo-refresh-token",
    )

    assert token.access_token == "access-token"
    assert len(client.get_calls) == 2
    assert sleep_calls == [0.0]


def test_list_directory_retries_on_retryable_baidu_errno() -> None:
    client = SequenceClient(
        get_actions=[
            make_json_response(
                "GET",
                "https://pan.baidu.com/rest/2.0/xpan/file",
                200,
                {"errno": 31034, "errmsg": "too many requests"},
            ),
            make_json_response(
                "GET",
                "https://pan.baidu.com/rest/2.0/xpan/file",
                200,
                {"errno": 0, "list": [{"path": "/apps/demo", "isdir": 1}]},
            ),
        ]
    )
    sleep_calls: list[float] = []
    api = BaiduOpenApi(client=client, sleep_func=sleep_calls.append, retry_delays=(0.0,))

    entries = api.list_directory(access_token="access-token", dir_path="/apps")

    assert entries == [{"path": "/apps/demo", "isdir": 1}]
    assert len(client.get_calls) == 2
    assert sleep_calls == [0.0]


def test_download_file_retries_on_request_error() -> None:
    request = httpx.Request("GET", "https://d.pcs.baidu.com/rest/2.0/pcs/file")
    client = SequenceClient(
        get_actions=[
            httpx.ConnectError("temporary network issue", request=request),
            make_bytes_response(
                "GET",
                "https://d.pcs.baidu.com/rest/2.0/pcs/file",
                200,
                b"remote-bytes",
            ),
        ]
    )
    sleep_calls: list[float] = []
    api = BaiduOpenApi(client=client, sleep_func=sleep_calls.append, retry_delays=(0.0,))

    payload = api.download_file(
        access_token="access-token",
        remote_path="/apps/demo/manifest.json",
    )

    assert payload == b"remote-bytes"
    assert len(client.get_calls) == 2
    assert sleep_calls == [0.0]


def test_precreate_file_does_not_retry_non_retryable_error() -> None:
    client = SequenceClient(
        post_actions=[
            make_json_response(
                "POST",
                "https://pan.baidu.com/rest/2.0/xpan/file",
                200,
                {"errno": 2, "errmsg": "invalid parameter"},
            )
        ]
    )
    sleep_calls: list[float] = []
    api = BaiduOpenApi(client=client, sleep_func=sleep_calls.append, retry_delays=(0.0, 0.0))

    with pytest.raises(BaiduApiError) as exc_info:
        api.precreate_file(
            access_token="access-token",
            remote_path="/apps/demo/manifest.json",
            size=5,
            block_list=["md5"],
            content_md5="md5",
            slice_md5="md5",
        )

    assert str(exc_info.value) == "Baidu API error 2: invalid parameter"
    assert len(client.post_calls) == 1
    assert sleep_calls == []
