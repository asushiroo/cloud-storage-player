from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TAG_SIZE_BYTES = 16


@dataclass(slots=True)
class EncryptedSegment:
    ciphertext: bytes
    nonce: bytes
    tag: bytes
    plaintext_sha256: str

    @property
    def ciphertext_size(self) -> int:
        return len(self.ciphertext) + len(self.tag)

    @property
    def nonce_b64(self) -> str:
        return _encode_token(self.nonce)

    @property
    def tag_b64(self) -> str:
        return _encode_token(self.tag)


def encrypt_segment(plaintext: bytes, key: bytes, *, nonce: bytes | None = None) -> EncryptedSegment:
    nonce_bytes = nonce or os.urandom(12)
    ciphertext_with_tag = AESGCM(key).encrypt(nonce_bytes, plaintext, associated_data=None)
    ciphertext = ciphertext_with_tag[:-TAG_SIZE_BYTES]
    tag = ciphertext_with_tag[-TAG_SIZE_BYTES:]
    return EncryptedSegment(
        ciphertext=ciphertext,
        nonce=nonce_bytes,
        tag=tag,
        plaintext_sha256=compute_sha256_hex(plaintext),
    )


def decrypt_segment(ciphertext: bytes, key: bytes, *, nonce: bytes, tag: bytes) -> bytes:
    return AESGCM(key).decrypt(nonce, ciphertext + tag, associated_data=None)


def compute_sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def decode_token(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _encode_token(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
