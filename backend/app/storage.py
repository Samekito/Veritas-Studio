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
