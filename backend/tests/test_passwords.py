"""Unit tests for the admin password hashing primitives (scrypt)."""
from app.passwords import hash_password, verify_password


def test_hash_verify_roundtrip():
    encoded = hash_password("s3cret-pass")
    assert verify_password("s3cret-pass", encoded) is True
    assert verify_password("s3cret-pas", encoded) is False


def test_encoded_hash_does_not_contain_plaintext():
    encoded = hash_password("correct horse battery staple")
    assert "correct horse battery staple" not in encoded
    assert encoded.startswith("scrypt$")


def test_salt_makes_each_hash_unique():
    assert hash_password("same") != hash_password("same")


def test_verify_rejects_malformed_hash():
    assert verify_password("whatever", "not-a-valid-encoded-hash") is False
    assert verify_password("whatever", "") is False
