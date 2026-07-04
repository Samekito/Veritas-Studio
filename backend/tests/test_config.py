"""Unit tests for config: admin-token sourcing, missing-key detection, prod guards."""
import pytest

from app.config import ConfigError, Settings


def test_admin_token_prefers_explicit_env_secret(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "random-opaque-secret")
    s = Settings()
    assert s.admin_token == "random-opaque-secret"


def test_admin_token_dev_fallback_is_not_a_bare_password_hash(monkeypatch):
    # No ADMIN_TOKEN set: a clearly dev-only value is derived, and it must NOT be
    # the old sha256(password) that a guessed password would reproduce.
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    s = Settings()
    s.admin_password = "hunter2"
    assert s.admin_token.startswith("dev-")
    import hashlib

    old_derivation = hashlib.sha256(b"veritas::hunter2").hexdigest()
    assert s.admin_token != old_derivation


def test_missing_flags_absent_and_placeholder_values():
    s = Settings()
    s.b2_key_id = "real-key"
    s.b2_app_key = "real-app"
    s.b2_bucket = "real-bucket"
    s.gmi_api_key = "real-gmi"
    assert s.missing() == []

    s.b2_key_id = "your_b2_key_id"
    assert "B2_KEY_ID" in s.missing()

    s.gmi_api_key = None
    assert "GMI_API_KEY" in s.missing()


def test_production_boot_requires_password_hash(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ADMIN_TOKEN", "x")
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    s = Settings()
    s.b2_key_id = s.b2_app_key = s.b2_bucket = s.gmi_api_key = "real"
    with pytest.raises(ConfigError):
        s.validate_for_production()


def test_production_boot_requires_admin_token(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "scrypt$1$1$1$AAAA$AAAA")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    s = Settings()
    s.b2_key_id = s.b2_app_key = s.b2_bucket = s.gmi_api_key = "real"
    with pytest.raises(ConfigError):
        s.validate_for_production()


def test_admin_login_verifies_against_hash_not_plaintext(monkeypatch):
    from app.passwords import hash_password

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password("correct horse"))
    # A stray plaintext ADMIN_PASSWORD must be ignored when a hash is present.
    monkeypatch.setenv("ADMIN_PASSWORD", "correct horse")
    s = Settings()
    assert s.verify_admin_password("correct horse") is True
    assert s.verify_admin_password("wrong") is False


def test_dev_login_falls_back_to_plaintext_when_no_hash(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)
    monkeypatch.setenv("ADMIN_PASSWORD", "letmein")
    s = Settings()
    assert s.verify_admin_password("letmein") is True
    assert s.verify_admin_password("nope") is False


def test_development_never_blocks_boot(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    s = Settings()
    s.validate_for_production()  # must not raise even with default creds
