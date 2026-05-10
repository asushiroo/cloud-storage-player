from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

OPENAPI_BASE_URL = "https://openapi.baidu.com"
PAN_BASE_URL = "https://pan.baidu.com"
PCS_BASE_URL = "https://d.pcs.baidu.com"
DEFAULT_USER_AGENT = "pan.baidu.com"


class BaiduApiError(RuntimeError):
    """Raised when the Baidu Open Platform API returns an error."""


class BaiduAuthorizationError(BaiduApiError):
    """Raised when OAuth exchange or refresh fails."""


@dataclass(slots=True)
class BaiduToken:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str | None = None


class BaiduOpenApi:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        self._owns_client = client is None

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
        response = self._client.get(
            f"{OPENAPI_BASE_URL}/oauth/2.0/token",
            params={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
        )
        return _parse_token_response(response)

    def refresh_access_token(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> BaiduToken:
        response = self._client.get(
            f"{OPENAPI_BASE_URL}/oauth/2.0/token",
            params={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        return _parse_token_response(response)

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
        response.raise_for_status()
        data = response.json()
        _raise_for_pan_error(data)
        md5 = data.get("md5")
        if not md5:
            raise BaiduApiError("Baidu superfile2 response did not include md5.")
        return str(md5)

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
        response = self._client.get(
            dlink,
            params={"access_token": access_token},
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )
        response.raise_for_status()
        return response.content

    def _get_json(self, url: str, *, params: dict[str, Any]) -> dict[str, Any]:
        response = self._client.get(url, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BaiduApiError(str(exc)) from exc
        payload = response.json()
        _raise_for_pan_error(payload)
        return payload

    def _post_form_json(
        self,
        url: str,
        *,
        params: dict[str, Any],
        data: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._client.post(url, params=params, data=data)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BaiduApiError(str(exc)) from exc
        payload = response.json()
        _raise_for_pan_error(payload)
        return payload


def _parse_token_response(response: httpx.Response) -> BaiduToken:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            payload = response.json()
        except ValueError:
            raise BaiduAuthorizationError(str(exc)) from exc
        description = payload.get("error_description") or payload.get("error") or str(exc)
        raise BaiduAuthorizationError(str(description)) from exc

    payload = response.json()
    if "error" in payload:
        description = payload.get("error_description") or payload["error"]
        raise BaiduAuthorizationError(str(description))

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


def _raise_for_pan_error(payload: dict[str, Any]) -> None:
    errno = payload.get("errno")
    if errno in (None, 0, "0"):
        return

    message = payload.get("errmsg") or payload.get("show_msg") or payload.get("err_msg")
    if message:
        raise BaiduApiError(f"Baidu API error {errno}: {message}")
    raise BaiduApiError(f"Baidu API error {errno}.")
