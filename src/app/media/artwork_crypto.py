from __future__ import annotations

from hashlib import sha256

_ARTWORK_CONTEXT = b"cloud-storage-player:artwork:v1:"
_BLOCK_SIZE = sha256().digest_size


def crypt_artwork_bytes(payload: bytes, key: bytes, *, artwork_name: str) -> bytes:
    if not payload:
        return b""

    salt = _ARTWORK_CONTEXT + artwork_name.encode("utf-8")
    output = bytearray(len(payload))
    offset = 0
    counter = 0
    while offset < len(payload):
        keystream = sha256(key + salt + counter.to_bytes(4, "big")).digest()
        chunk_length = min(_BLOCK_SIZE, len(payload) - offset)
        for index in range(chunk_length):
            output[offset + index] = payload[offset + index] ^ keystream[index]
        offset += chunk_length
        counter += 1
    return bytes(output)
