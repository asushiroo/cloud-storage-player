from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

import httpx

OPENAPI_BASE_URL = "https://openapi.baidu.com"
PAN_BASE_URL = "https://pan.baidu.com"
PCS_BASE_URL = "https://d.pcs.baidu.com"
DEFAULT_USER_AGENT = "pan.baidu.com"
DEFAULT_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)
RETRYABLE_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}
RETRYABLE_PAN_ERRNOS = {31034, 42000}
RETRYABLE_MESSAGE_FRAGMENTS = (
    "please try again later",
    "trigger security policy",
    "temporarily unavailable",
    "system busy",
    "too many requests",
)
T = TypeVar("T")


class BaiduApiError(RuntimeError):
    """Raised when the Baidu Open Platform API returns an error."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class BaiduAuthorizationError(BaiduApiError):
    """Raised when OAuth exchange or refresh fails."""


@dataclass(slots=True)
class BaiduToken:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str | None = None


class BaiduOpenApi:
    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        sleep_func: Callable[[float], None] | None = None,
        retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS_SECONDS,
    ) -> None:
        self._client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        self._owns_client = client is None
        self._sleep = sleep_func or time.sleep
        self._retry_delays = retry_delays

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def exchange_authorization_code(
        self,
        *,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> BaiduToken:
        return self._run_with_retry(
            lambda: _parse_token_response(
                self._client.get(
                    f"{OPENAPI_BASE_URL}/oauth/2.0/token",
                    params={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "redirect_uri": redirect_uri,
                    },
                )
            )
        )

    def refresh_access_token(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> BaiduToken:
        return self._run_with_retry(
            lambda: _parse_token_response(
                self._client.get(
                    f"{OPENAPI_BASE_URL}/oauth/2.0/token",
                    params={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": client_id,
                        "client_secret": client_secret,
                    },
                )
            )
        )

    def list_directory(self, *, access_token: str, dir_path: str) -> list[dict[str, Any]]:
        payload = self._get_json(
            f"{PAN_BASE_URL}/rest/2.0/xpan/file",
            params={
                "method": "list",
                "access_token": access_token,
                "dir": dir_path,
                "limit": 10000,
            },
        )
        return payload.get("list", [])

    def get_file_metas(
        self,
        *,
        access_token: str,
        fsids: list[int],
        dlink: bool = False,
    ) -> list[dict[str, Any]]:
        payload = self._get_json(
            f"{PAN_BASE_URL}/rest/2.0/xpan/multimedia",
            params={
                "method": "filemetas",
                "access_token": access_token,
                "fsids": json.dumps(fsids, separators=(",", ":")),
                "dlink": 1 if dlink else 0,
            },
        )
        return payload.get("list", [])

    def precreate_file(
        self,
        *,
        access_token: str,
        remote_path: str,
        size: int,
        block_list: list[str],
        content_md5: str,
        slice_md5: str,
        rtype: int = 3,
    ) -> dict[str, Any]:
        return self._post_form_json(
            f"{PAN_BASE_URL}/rest/2.0/xpan/file",
            params={
                "method": "precreate",
                "access_token": access_token,
            },
            data={
                "path": remote_path,
                "size": str(size),
                "isdir": "0",
                "autoinit": "1",
                "rtype": str(rtype),
                "block_list": json.dumps(block_list, separators=(",", ":")),
                "content-md5": content_md5,
                "slice-md5": slice_md5,
            },
        )

    def upload_tmpfile(
        self,
        *,
        access_token: str,
        remote_path: str,
        uploadid: str,
        partseq: int,
        payload: bytes,
    ) -> str:
        return self._run_with_retry(
            lambda: self._upload_tmpfile_once(
                access_token=access_token,
                remote_path=remote_path,
                uploadid=uploadid,
                partseq=partseq,
                payload=payload,
            )
        )

    def create_file(
        self,
        *,
        access_token: str,
        remote_path: str,
        size: int,
        uploadid: str,
        block_list: list[str],
        rtype: int = 3,
    ) -> dict[str, Any]:
        return self._post_form_json(
            f"{PAN_BASE_URL}/rest/2.0/xpan/file",
            params={
                "method": "create",
                "access_token": access_token,
            },
            data={
                "path": remote_path,
                "size": str(size),
                "isdir": "0",
                "rtype": str(rtype),
                "uploadid": uploadid,
                "block_list": json.dumps(block_list, separators=(",", ":")),
            },
        )

    def download_dlink(self, *, dlink: str, access_token: str) -> bytes:
        return self._run_with_retry(
            lambda: self._download_dlink_once(dlink=dlink, access_token=access_token)
        )

    def download_file(self, *, access_token: str, remote_path: str) -> bytes:
        return self._run_with_retry(
            lambda: self._download_file_once(access_token=access_token, remote_path=remote_path)
        )

    def _get_json(self, url: str, *, params: dict[str, Any]) -> dict[str, Any]:
        return self._run_with_retry(lambda: self._get_json_once(url, params=params))

    def _post_form_json(
        self,
        url: str,
        *,
        params: dict[str, Any],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        return self._run_with_retry(
            lambda: self._post_form_json_once(url, params=params, data=data)
        )

    def _get_json_once(self, url: str, *, params: dict[str, Any]) -> dict[str, Any]:
        response = self._client.get(url, params=params)
        _raise_for_status(response)
        payload = response.json()
        _raise_for_pan_error(payload)
        return payload

    def _post_form_json_once(
        self,
        url: str,
        *,
        params: dict[str, Any],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._client.post(url, params=params, data=data)
        _raise_for_status(response)
        payload = response.json()
        _raise_for_pan_error(payload)
        return payload

    def _upload_tmpfile_once(
        self,
        *,
        access_token: str,
        remote_path: str,
        uploadid: str,
        partseq: int,
        payload: bytes,
    ) -> str:
        response = self._client.post(
            f"{PCS_BASE_URL}/rest/2.0/pcs/superfile2",
            params={
                "method": "upload",
                "access_token": access_token,
                "type": "tmpfile",
                "path": remote_path,
                "uploadid": uploadid,
                "partseq": partseq,
            },
            files={"file": (Path(remote_path).name or "payload.bin", payload)},
        )
        _raise_for_status(response)
        data = response.json()
        _raise_for_pan_error(data)
        md5 = data.get("md5")
        if not md5:
            raise BaiduApiError("Baidu superfile2 response did not include md5.")
        return str(md5)

    def _download_dlink_once(self, *, dlink: str, access_token: str) -> bytes:
        response = self._client.get(
            dlink,
            params={"access_token": access_token},
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        _raise_for_status(response)
        return response.content

    def _download_file_once(self, *, access_token: str, remote_path: str) -> bytes:
        response = self._client.get(
            f"{PCS_BASE_URL}/rest/2.0/pcs/file",
            params={
                "method": "download",
                "access_token": access_token,
                "path": remote_path,
            },
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        _raise_for_status(response)
        return response.content

    def _run_with_retry(self, operation: Callable[[], T]) -> T:
        for attempt_index in range(len(self._retry_delays) + 1):
            try:
                return operation()
            except (BaiduApiError, httpx.RequestError) as exc:
                if not _is_retryable_exception(exc) or attempt_index >= len(self._retry_delays):
                    raise
                self._sleep(self._retry_delays[attempt_index])

        raise RuntimeError("Retry loop exited without returning or raising.")


def _parse_token_response(response: httpx.Response) -> BaiduToken:
    try:
        _raise_for_status(response, authorization=True)
    except BaiduApiError as exc:
        raise BaiduAuthorizationError(str(exc), retryable=exc.retryable) from exc

    payload = response.json()
    if "error" in payload:
        description = payload.get("error_description") or payload["error"]
        raise BaiduAuthorizationError(
            str(description),
            retryable=_should_retry_message(str(description)),
        )

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    expires_in = payload.get("expires_in")
    if not access_token or not refresh_token or expires_in is None:
        raise BaiduAuthorizationError("Baidu token response is missing required fields.")

    return BaiduToken(
        access_token=str(access_token),
        refresh_token=str(refresh_token),
        expires_in=int(expires_in),
        scope=str(payload.get("scope")) if payload.get("scope") is not None else None,
    )


def _raise_for_status(response: httpx.Response, *, authorization: bool = False) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _build_http_error(exc, authorization=authorization) from exc


def _raise_for_pan_error(payload: dict[str, Any]) -> None:
    errno = payload.get("errno")
    if errno in (None, 0, "0"):
        return

    message = payload.get("errmsg") or payload.get("show_msg") or payload.get("err_msg")
    retryable = _is_retryable_errno(errno) or _should_retry_message(str(message or ""))
    if message:
        raise BaiduApiError(f"Baidu API error {errno}: {message}", retryable=retryable)
    raise BaiduApiError(f"Baidu API error {errno}.", retryable=retryable)


def _build_http_error(
    exc: httpx.HTTPStatusError,
    *,
    authorization: bool = False,
) -> BaiduApiError:
    response = exc.response
    message = str(exc)
    retryable = response.status_code in RETRYABLE_HTTP_STATUS_CODES
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if payload is not None:
        payload_message = (
            payload.get("error_description")
            or payload.get("errmsg")
            or payload.get("show_msg")
            or payload.get("err_msg")
            or payload.get("error")
        )
        if payload_message:
            message = str(payload_message)
            retryable = retryable or _should_retry_message(message)

    error_type = BaiduAuthorizationError if authorization else BaiduApiError
    return error_type(message, retryable=retryable)


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, BaiduApiError):
        return exc.retryable
    return isinstance(exc, httpx.RequestError)


def _is_retryable_errno(errno: object) -> bool:
    try:
        normalized = int(errno)
    except (TypeError, ValueError):
        return False
    return normalized in RETRYABLE_PAN_ERRNOS


def _should_retry_message(message: str) -> bool:
    normalized = message.strip().lower()
    if not normalized:
        return False
    return any(fragment in normalized for fragment in RETRYABLE_MESSAGE_FRAGMENTS)
