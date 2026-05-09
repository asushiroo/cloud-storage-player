from __future__ import annotations

import base64
import hashlib
import hmac
import os

from fastapi import Request

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
SESSION_AUTH_KEY = "authenticated"


def hash_password(
    password: str,
    *,
    salt: bytes | None = None,
    iterations: int = PASSWORD_ITERATIONS,
) -> str:
    if not password:
        raise ValueError("Password must not be empty.")

    salt_bytes = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        iterations,
    )
    salt_token = _encode_token(salt_bytes)
    digest_token = _encode_token(digest)
    return f"{PASSWORD_ALGORITHM}${iterations}${salt_token}${digest_token}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iteration_token, salt_token, digest_token = encoded_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iterations = int(iteration_token)
        salt = _decode_token(salt_token)
        expected_digest = _decode_token(digest_token)
    except (TypeError, ValueError):
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def mark_session_authenticated(request: Request) -> None:
    request.session[SESSION_AUTH_KEY] = True


def clear_session(request: Request) -> None:
    request.session.clear()


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get(SESSION_AUTH_KEY))


def _encode_token(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_token(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
