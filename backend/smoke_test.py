"""Smoke test — prove the stack works end to end BEFORE running the full app.

Runs the smallest possible real Genblaze pipeline (one text->image step) and
writes the asset + provenance manifest to your Backblaze B2 bucket. If this
prints "VERIFIED: True" with a B2 URL, your credentials, the SDK, and the
provider model id are all correct.

Usage (from backend/, with .env filled in and venv active):
    python smoke_test.py
    python smoke_test.py --video      # also try a short text->video clip (costs more)
"""
from __future__ import annotations

import sys

from app.config import settings


def check_env() -> None:
    missing = settings.missing()
    if missing:
        print(f"[FAIL] Missing env vars: {', '.join(missing)}")
        print("       Copy .env.example to .env and fill them in.")
        sys.exit(1)
    print(f"[ok] Credentials present. Bucket={settings.b2_bucket} Region={settings.b2_region}")


def run_image() -> None:
    from genblaze_core import KeyStrategy, Modality, ObjectStorageSink, Pipeline
    from genblaze_gmicloud import GMICloudImageProvider
    from genblaze_s3 import S3StorageBackend

    print("[..] Connecting to B2 (preflight)…")
    backend = S3StorageBackend.for_backblaze(
        settings.b2_bucket,
        region=settings.b2_region,
        key_id=settings.b2_key_id,
        app_key=settings.b2_app_key,
        public_url_base=settings.b2_public_url_base,
        preflight=True,
    )
    sink = ObjectStorageSink(backend, prefix=settings.key_prefix, key_strategy=KeyStrategy.CONTENT_ADDRESSABLE)
    print("[ok] B2 connected.")

    print(f"[..] Generating 1 image via GMI ({settings.image_model})… this can take ~30-90s")
    result = (
        Pipeline("veritas-smoke", project_id="veritas-studio")
        .step(
            GMICloudImageProvider(),
            model=settings.image_model,
            prompt="A single ripe red apple on a white studio background, soft light, product photo",
            modality=Modality.IMAGE,
        )
        .run(sink=sink, timeout=300, max_retries=1)
    )

    asset = result.run.steps[0].assets[0]
    print("\n=== RESULT ===")
    print(f"Run ID:    {result.run.run_id}")
    print(f"Status:    {result.run.steps[0].status}")
    print(f"Asset URL: {asset.url}")
    print(f"SHA-256:   {asset.sha256}")
    print(f"MediaType: {asset.media_type}")
    print(f"Manifest:  {result.manifest.manifest_uri}")
    print(f"Hash:      {result.manifest.canonical_hash}")
    print(f"VERIFIED:  {result.manifest.verify()}")
    cost = getattr(result.run.steps[0], "cost_usd", None)
    if cost is not None:
        print(f"Cost:      ${cost:.4f}")


def run_video() -> None:
    from genblaze_core import KeyStrategy, Modality, ObjectStorageSink, Pipeline
    from genblaze_gmicloud import GMICloudVideoProvider
    from genblaze_s3 import S3StorageBackend

    backend = S3StorageBackend.for_backblaze(
        settings.b2_bucket, region=settings.b2_region,
        key_id=settings.b2_key_id, app_key=settings.b2_app_key,
        public_url_base=settings.b2_public_url_base, preflight=True,
    )
    sink = ObjectStorageSink(backend, prefix=settings.key_prefix, key_strategy=KeyStrategy.CONTENT_ADDRESSABLE)
    print("[..] Generating a short text->video clip (Kling-Text2Video)… this can take a few minutes")
    result = (
        Pipeline("veritas-smoke-video", project_id="veritas-studio")
        .step(
            GMICloudVideoProvider(),
            model="Kling-Text2Video-V2.1-Master",
            prompt="A red apple slowly rotating on a white studio background, soft cinematic light",
            modality=Modality.VIDEO,
            duration=5,
            aspect_ratio="16:9",
        )
        .run(sink=sink, timeout=600, max_retries=1)
    )
    asset = result.run.steps[0].assets[0]
    print(f"\nVideo URL: {asset.url}")
    print(f"VERIFIED:  {result.manifest.verify()}")


if __name__ == "__main__":
    check_env()
    run_image()
    if "--video" in sys.argv:
        run_video()
    print("\nAll good. You can now run the API:  uvicorn app.main:app --reload --port 8000")
