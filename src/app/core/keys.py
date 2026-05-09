from __future__ import annotations

import base64
import secrets
from pathlib import Path

from app.core.config import Settings

CONTENT_KEY_SIZE_BYTES = 32


def load_content_key(settings: Settings) -> bytes:
    key_path = settings.content_key_file
    if not key_path.exists():
        raise FileNotFoundError("Content encryption key file does not exist.")

    key_material = _decode_key_material(key_path.read_text(encoding="utf-8").strip())
    if len(key_material) != CONTENT_KEY_SIZE_BYTES:
        raise ValueError("Content encryption key has an invalid length.")
    return key_material


def load_or_create_content_key(settings: Settings) -> bytes:
    key_path = settings.content_key_file
    if key_path.exists():
        return load_content_key(settings)

    key_material = secrets.token_bytes(CONTENT_KEY_SIZE_BYTES)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(_encode_key_material(key_material), encoding="utf-8")
    return key_material


def _encode_key_material(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_key_material(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
