"""Backblaze B2 storage wiring for Genblaze.

Every asset and every provenance manifest is written to B2 by Genblaze's
ObjectStorageSink. We use a CONTENT_ADDRESSABLE layout so identical bytes are
stored once (sha256-keyed), with manifests as sidecars per run.
"""
from __future__ import annotations

from functools import lru_cache

from genblaze_core import KeyStrategy, ObjectStorageSink
from genblaze_s3 import S3StorageBackend

from .config import settings
from .logging_setup import get_logger

log = get_logger("veritas.storage")

# Lifetime of the browser-facing asset URLs minted by `signed_url`. Long enough
# that a passport page left open still plays, short enough that a leaked URL
# stops working.
ASSET_URL_TTL = 3600


@lru_cache(maxsize=1)
def get_backend() -> S3StorageBackend:
    """Construct (and cache) the B2-backed S3 storage backend.

    preflight=True verifies the bucket + credentials at construction so we fail
    loudly at startup rather than mid-generation.
    """
    return S3StorageBackend.for_backblaze(
        settings.b2_bucket,
        region=settings.b2_region,
        key_id=settings.b2_key_id,
        app_key=settings.b2_app_key,
        public_url_base=settings.b2_public_url_base,
        preflight=True,
    )


def make_sink() -> ObjectStorageSink:
    """A fresh sink per run; the pipeline closes it automatically on completion."""
    return ObjectStorageSink(
        get_backend(),
        prefix=settings.key_prefix,
        key_strategy=KeyStrategy.CONTENT_ADDRESSABLE,
    )


def signed_url(url: str | None) -> str | None:
    """Mint a short-lived readable URL for a persisted asset URL.

    What we store is the *durable* URL — credential-free and non-expiring, so it
    stays valid in the manifest forever. A private B2 bucket answers that URL
    with 401, which is why `<img>`/`<video>` tags render nothing. Presigning at
    the API boundary keeps the bucket private while still letting the browser
    read the bytes.

    Never raises: a signing failure degrades to the durable URL (correct when
    the bucket is public) rather than taking the whole response down.
    """
    if not url or not settings.b2_ready:
        return url
    try:
        backend = get_backend()
        key = backend.key_from_url(url)
        if not key:  # foreign URL — not ours to sign
            return url
        return backend.presigned_get_url(key, expires_in=ASSET_URL_TTL)
    except Exception:
        log.warning("asset presign failed; serving durable URL", exc_info=True)
        return url
