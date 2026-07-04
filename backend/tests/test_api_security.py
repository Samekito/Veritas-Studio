"""API-surface security tests: admin auth, upload hardening, rate limiting.

Offline only — generation is patched out so nothing hits B2/GMI or spends money.
"""
import importlib
import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolated on-disk DB and a known admin token; force dev so boot guards pass.
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.sqlite"))

    from app import config as config_module

    config_module.settings = config_module.Settings()

    import app.db as db
    import app.main as main

    importlib.reload(db)
    importlib.reload(main)
    # Neuter real generation so no worker touches external providers.
    monkeypatch.setattr(main.job_runner, "submit", lambda *a, **k: True)

    with TestClient(main.app) as c:
        yield c


def test_admin_route_rejects_missing_token_401(client):
    assert client.get("/api/admin/overview").status_code == 401


def test_admin_route_rejects_wrong_token_403(client):
    r = client.get("/api/admin/overview", headers={"X-Admin-Token": "nope"})
    assert r.status_code == 403


def test_admin_route_accepts_correct_token(client):
    r = client.get("/api/admin/overview", headers={"X-Admin-Token": "test-admin-token"})
    assert r.status_code == 200


def test_login_wrong_password_401(client):
    assert client.post("/api/admin/login", json={"password": "wrong"}).status_code == 401


def test_verify_sanitizes_traversal_filename(client, tmp_path, monkeypatch):
    # A malicious filename must not escape the temp dir; the handler just reports
    # "unsupported/none found" for a bogus file rather than writing outside it.
    import app.main as main

    captured = {}

    def fake_extract(path):
        captured["name"] = path.name
        captured["parent_ok"] = "veritas_verify_" in str(path.parent)
        return {"found": False, "verified": False, "reason": "stub"}

    monkeypatch.setattr(main, "extract_and_verify", fake_extract, raising=False)
    monkeypatch.setattr("app.media_tools.extract_and_verify", fake_extract)

    files = {"file": ("../../../../evil.txt", io.BytesIO(b"hi"), "text/plain")}
    r = client.post("/api/verify", files=files)
    assert r.status_code == 200
    assert "/" not in captured["name"] and "\\" not in captured["name"]
    assert captured["name"] == "evil.txt"
    assert captured["parent_ok"]


def test_verify_rejects_oversized_upload(client, monkeypatch):
    from app import config as config_module

    monkeypatch.setattr(config_module.settings, "max_upload_bytes", 8, raising=False)
    files = {"file": ("big.bin", io.BytesIO(b"x" * 1024), "application/octet-stream")}
    r = client.post("/api/verify", files=files)
    assert r.status_code == 413


def test_generate_rate_limit_kicks_in(client, monkeypatch):
    import app.main as main

    # Tight limiter so the test is fast and deterministic.
    from app.ratelimit import SlidingWindowRateLimiter

    monkeypatch.setattr(main, "generate_rate_limiter", SlidingWindowRateLimiter(2, 3600))
    monkeypatch.setattr(main.settings, "missing", lambda: [])
    monkeypatch.setattr(main.settings, "daily_cost_cap_usd", 0, raising=False)

    body = {"subject": "a bottle"}
    assert client.post("/api/generate", json=body).status_code == 200
    assert client.post("/api/generate", json=body).status_code == 200
    assert client.post("/api/generate", json=body).status_code == 429
