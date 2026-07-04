"""Configuration loaded from environment / .env.

Secrets and tunables are read from the environment. `validate_for_production()`
is called on startup and refuses to boot when a prod deployment is missing a
security-critical value (admin token, credentials) or is left on an insecure
default — fail loud at boot rather than silently degrade in production.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env regardless of the working directory uvicorn is launched from.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class ConfigError(RuntimeError):
    """Raised on startup when production configuration is unsafe or incomplete."""


class Settings:
    # Deployment environment: "development" (default) relaxes prod-only guards.
    env: str = os.getenv("ENV", "development").strip().lower()

    # Backblaze B2
    b2_key_id: str | None = os.getenv("B2_KEY_ID")
    b2_app_key: str | None = os.getenv("B2_APP_KEY")
    b2_bucket: str | None = os.getenv("B2_BUCKET")
    b2_region: str = os.getenv("B2_REGION", "us-west-004")
    b2_public_url_base: str | None = os.getenv("B2_PUBLIC_URL_BASE") or None

    # Providers
    gmi_api_key: str | None = os.getenv("GMI_API_KEY")
    elevenlabs_api_key: str | None = os.getenv("ELEVENLABS_API_KEY") or None
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None

    # Models
    image_model: str = os.getenv("IMAGE_MODEL", "seedream-5.0-lite")
    image_fallbacks: list[str] = _list(os.getenv("IMAGE_FALLBACKS"))
    video_model: str = os.getenv("VIDEO_MODEL", "Kling-Image2Video-V2.1-Master")
    video_fallbacks: list[str] = _list(os.getenv("VIDEO_FALLBACKS"))
    audio_model: str = os.getenv("AUDIO_MODEL", "minimax-tts-speech-2.6-turbo")
    audio_fallbacks: list[str] = _list(os.getenv("AUDIO_FALLBACKS"))

    pipeline_mode: str = os.getenv("PIPELINE_MODE", "chain")  # "chain" | "t2v"
    video_duration: int = _int("VIDEO_DURATION", 5)
    aspect_ratio: str = os.getenv("ASPECT_RATIO", "16:9")
    voice_id: str = os.getenv("VOICE_ID", "")  # provider default voice unless set

    # Admin console auth. Login is verified against ADMIN_PASSWORD_HASH — a salted
    # scrypt hash (generate with `python -m app.hashpw`); no recoverable password
    # is stored. ADMIN_TOKEN is the opaque bearer secret handed back on login and
    # required by admin routes. In production the hash + token must both be set
    # (see validate_for_production). ADMIN_PASSWORD (plaintext) is a dev-only
    # convenience used only when no hash is configured.
    admin_password_hash: str | None = os.getenv("ADMIN_PASSWORD_HASH") or None
    admin_password: str = os.getenv("ADMIN_PASSWORD", "veritas-admin")

    # Abuse / cost controls (generation spends real money).
    max_concurrent_jobs: int = _int("MAX_CONCURRENT_JOBS", 3)
    generate_rate_limit: int = _int("GENERATE_RATE_LIMIT", 5)          # per IP
    generate_rate_window: float = _float("GENERATE_RATE_WINDOW", 3600.0)  # seconds
    daily_cost_cap_usd: float = _float("DAILY_COST_CAP_USD", 25.0)     # 0 disables
    max_upload_bytes: int = _int("MAX_UPLOAD_BYTES", 200 * 1024 * 1024)  # /verify cap

    # Trust N reverse-proxy hops for client-IP extraction (Render/Vercel add one).
    trusted_proxy_hops: int = _int("TRUSTED_PROXY_HOPS", 1)

    # App
    db_path: str = os.getenv("DB_PATH", "veritas.sqlite")
    key_prefix: str = os.getenv("KEY_PREFIX", "veritas")
    cors_origins: list[str] = _list(os.getenv("CORS_ORIGINS")) or [
        "http://localhost:5173",  # customer app
        "http://localhost:5174",  # admin app
    ]

    @property
    def is_production(self) -> bool:
        # Read live so guards reflect the actual runtime environment, not just the
        # value captured at import time.
        return os.getenv("ENV", self.env).strip().lower() in ("production", "prod")

    @property
    def admin_token(self) -> str:
        """Opaque bearer secret for admin routes.

        Prefer an explicit random ADMIN_TOKEN (independent of the password, so it
        can be rotated without changing the login password and can't be derived
        from a guessed password). If unset we fall back to a clearly dev-only
        derived value — production boot is blocked unless ADMIN_TOKEN is set (see
        validate_for_production), so this fallback only ever runs locally.
        """
        explicit = os.getenv("ADMIN_TOKEN")
        if explicit:
            return explicit
        return "dev-" + hashlib.sha256(f"veritas-dev::{self.admin_password}".encode()).hexdigest()

    def verify_admin_password(self, plaintext: str) -> bool:
        """True if `plaintext` matches the admin credential (constant-time).

        Production verifies against the salted scrypt hash so no recoverable
        password lives in the environment. In development, if no hash is set, a
        plaintext ADMIN_PASSWORD (default) is accepted for convenience.
        """
        from .passwords import verify_password

        hashed = os.getenv("ADMIN_PASSWORD_HASH") or self.admin_password_hash
        if hashed:
            return verify_password(plaintext, hashed)
        if not self.is_production:
            return hmac.compare_digest(plaintext, os.getenv("ADMIN_PASSWORD", "veritas-admin"))
        return False

    @property
    def b2_ready(self) -> bool:
        return bool(self.b2_key_id and self.b2_app_key and self.b2_bucket)

    @property
    def gmi_ready(self) -> bool:
        return bool(self.gmi_api_key)

    def missing(self) -> list[str]:
        """Return required keys that are absent OR still set to the template placeholder."""
        def unset(value: str | None) -> bool:
            return not value or value.startswith("your_")

        gaps = []
        if unset(self.b2_key_id):
            gaps.append("B2_KEY_ID")
        if unset(self.b2_app_key):
            gaps.append("B2_APP_KEY")
        if unset(self.b2_bucket):
            gaps.append("B2_BUCKET")
        if unset(self.gmi_api_key):
            gaps.append("GMI_API_KEY")
        return gaps

    def validate_for_production(self) -> None:
        """Refuse to boot a production deployment with unsafe/incomplete config.

        No-op in development so local dev keeps working out of the box.
        """
        if not self.is_production:
            return

        # Read secrets/origins live so this reflects the real boot environment.
        cors = _list(os.getenv("CORS_ORIGINS"))

        errors: list[str] = []
        if not os.getenv("ADMIN_TOKEN"):
            errors.append("ADMIN_TOKEN must be set to a random secret in production")
        if not os.getenv("ADMIN_PASSWORD_HASH"):
            errors.append(
                "ADMIN_PASSWORD_HASH must be set to a scrypt hash "
                "(generate with `python -m app.hashpw`) in production"
            )
        if self.missing():
            errors.append(f"missing credentials: {', '.join(self.missing())}")
        if not cors:
            errors.append("CORS_ORIGINS must be set explicitly in production")
        elif "*" in cors:
            errors.append("CORS_ORIGINS must not be '*' in production")

        if errors:
            raise ConfigError("Unsafe production configuration:\n  - " + "\n  - ".join(errors))


settings = Settings()
