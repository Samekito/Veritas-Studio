"""Asset URL presigning — the bridge between a private B2 bucket and the browser.

Offline only: the storage backend is faked, so nothing touches B2 or spends money.
"""
import pytest

DURABLE = "https://s3.us-east-005.backblazeb2.com/bkt/veritas/assets/ab/cd/abcd.mp4"
SIGNED = DURABLE + "?X-Amz-Signature=deadbeef"


class FakeBackend:
    """Stands in for S3StorageBackend: recognizes our own URLs, signs them."""

    def __init__(self, key: str | None = "veritas/assets/ab/cd/abcd.mp4"):
        self.key = key

    def key_from_url(self, url: str) -> str | None:
        return self.key if url == DURABLE else None

    def presigned_get_url(self, key: str, *, expires_in: int = 3600) -> str:
        return SIGNED


@pytest.fixture()
def storage(monkeypatch):
    from app import storage as storage_module

    monkeypatch.setattr(storage_module.settings, "b2_key_id", "k", raising=False)
    monkeypatch.setattr(storage_module.settings, "b2_app_key", "s", raising=False)
    monkeypatch.setattr(storage_module.settings, "b2_bucket", "bkt", raising=False)
    return storage_module


def test_durable_url_is_presigned(storage, monkeypatch):
    monkeypatch.setattr(storage, "get_backend", lambda: FakeBackend())

    assert storage.signed_url(DURABLE) == SIGNED


def test_foreign_url_passes_through_unsigned(storage, monkeypatch):
    """A URL the backend doesn't own must not be rewritten."""
    monkeypatch.setattr(storage, "get_backend", lambda: FakeBackend(key=None))

    assert storage.signed_url("https://cdn.example.com/x.mp4") == "https://cdn.example.com/x.mp4"


@pytest.mark.parametrize("value", [None, ""])
def test_empty_url_passes_through(storage, value):
    assert storage.signed_url(value) == value


def test_unconfigured_b2_passes_through(storage, monkeypatch):
    monkeypatch.setattr(storage.settings, "b2_bucket", None, raising=False)

    assert storage.signed_url(DURABLE) == DURABLE


def test_signing_failure_degrades_to_durable_url(storage, monkeypatch):
    """A signing error must not take down the whole job response."""

    def boom():
        raise RuntimeError("b2 unreachable")

    monkeypatch.setattr(storage, "get_backend", boom)

    assert storage.signed_url(DURABLE) == DURABLE


def test_serialize_job_signs_every_asset_url(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "signed_url", lambda u: (u + "?sig") if u else u)
    job = {
        "id": "j1",
        "status": "completed",
        "stage": "done",
        "title": "t",
        "assets": [
            {"modality": "video", "url": DURABLE, "sha256": "x"},
            {"modality": "audio", "url": None},
        ],
    }

    out = main._serialize_job(job)

    assert out["assets"][0]["url"] == DURABLE + "?sig"
    assert out["assets"][0]["sha256"] == "x"  # other fields survive the rewrite
    assert out["assets"][1]["url"] is None
