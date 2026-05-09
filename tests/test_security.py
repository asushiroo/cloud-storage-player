from app.core.security import hash_password, verify_password


def test_hash_password_round_trip() -> None:
    password_hash = hash_password("shared-secret")

    assert verify_password("shared-secret", password_hash)


def test_hash_password_rejects_wrong_value() -> None:
    password_hash = hash_password("shared-secret")

    assert not verify_password("wrong-password", password_hash)
