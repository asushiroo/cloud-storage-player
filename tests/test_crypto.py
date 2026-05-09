from app.media.crypto import compute_sha256_hex, decrypt_segment, encrypt_segment


def test_encrypt_and_decrypt_segment_round_trip() -> None:
    key = b"\x01" * 32
    plaintext = b"hello encrypted world"

    encrypted = encrypt_segment(plaintext, key, nonce=b"\x02" * 12)

    assert encrypted.plaintext_sha256 == compute_sha256_hex(plaintext)
    restored = decrypt_segment(
        encrypted.ciphertext,
        key,
        nonce=encrypted.nonce,
        tag=encrypted.tag,
    )
    assert restored == plaintext


def test_sha256_checksum_is_stable() -> None:
    payload = b"stable payload"

    assert compute_sha256_hex(payload) == compute_sha256_hex(payload)
