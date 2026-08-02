"""Veritas Studio API — FastAPI app exposing the Genblaze + B2 pipeline."""
from __future__ import annotations

import hmac
import json
import shutil
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from . import db
from .config import settings
from .jobs import BoundedJobRunner
from .logging_setup import correlation_id, get_logger, setup_logging
from .pipelines import run_generation
from .ratelimit import SlidingWindowRateLimiter, client_ip_from_request
from .storage import signed_url

log = get_logger("veritas.api")

job_runner = BoundedJobRunner(settings.max_concurrent_jobs)
login_rate_limiter = SlidingWindowRateLimiter(max_attempts=5, window_seconds=60.0)
generate_rate_limiter = SlidingWindowRateLimiter(
    max_attempts=settings.generate_rate_limit, window_seconds=settings.generate_rate_window
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    settings.validate_for_production()  # refuses to boot on unsafe prod config
    db.init_db()
    reconciled = db.reconcile_stale_jobs()
    log.info(
        "startup",
        extra={"env": settings.env, "reconciled_jobs": reconciled, "b2_ready": settings.b2_ready},
    )
    yield
    job_runner.shutdown()


app = FastAPI(title="Veritas Studio", version="0.1.0", lifespan=lifespan)

# Auth is a custom header (X-Admin-Token), never a cookie — so credentials are
# not enabled and methods/headers are pinned to what the apps actually use.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Admin-Token", "X-Request-ID"],
)


@app.middleware("http")
async def observability_and_headers(request: Request, call_next):
    """Attach a correlation id to every request/log line and set security headers."""
    cid = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = correlation_id.set(cid)
    started = time.monotonic()
    try:
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled request error", extra={"path": request.url.path})
            response = JSONResponse(
                {"detail": "Internal server error", "request_id": cid}, status_code=500
            )
        # Log while the correlation id is still in context so the line carries it.
        took_ms = round((time.monotonic() - started) * 1000, 1)
        log.info(
            "request",
            extra={"method": request.method, "path": request.url.path,
                   "status": response.status_code, "ms": took_ms},
        )
        response.headers["X-Request-ID"] = cid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
    finally:
        correlation_id.reset(token)


# models
class BriefIn(BaseModel):
    subject: str
    audience: str | None = None
    tone: str | None = "cinematic"
    message: str | None = None
    cta: str | None = None
    title: str | None = None
    parent_run_id: str | None = None


class LoginIn(BaseModel):
    password: str


# auth / throttling dependencies
def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Guard admin routes: the X-Admin-Token header must match the server token.

    Uses a constant-time compare so a wrong token can't be recovered by timing.
    401 when no credential is presented, 403 when one is presented but invalid.
    """
    if not x_admin_token:
        raise HTTPException(401, "Admin authentication required")
    if not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(403, "Invalid admin token")


def throttle_login(request: Request) -> None:
    login_rate_limiter.check(client_ip_from_request(request, settings.trusted_proxy_hops))


def throttle_generate(request: Request) -> None:
    generate_rate_limiter.check(client_ip_from_request(request, settings.trusted_proxy_hops))


# routes
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": settings.b2_ready and settings.gmi_ready,
        "missing_keys": settings.missing(),
        "pipeline_mode": settings.pipeline_mode,
        "bucket": settings.b2_bucket,
        "models": {
            "image": settings.image_model,
            "video": settings.video_model,
            "audio": settings.audio_model,
        },
    }


@app.get("/api/stats")
def get_stats() -> dict[str, Any]:
    return db.stats()


def _enforce_spend_cap() -> None:
    """Reject generation once a rolling 24h spend cap is reached (0 disables)."""
    cap = settings.daily_cost_cap_usd
    if cap and cap > 0:
        spent = db.cost_since(time.time() - 86_400)
        if spent >= cap:
            log.warning("daily spend cap reached", extra={"spent": spent, "cap": cap})
            raise HTTPException(429, "Daily generation limit reached — try again tomorrow")


@app.post("/api/generate", dependencies=[Depends(throttle_generate)])
def generate(brief: BriefIn) -> dict[str, Any]:
    if settings.missing():
        raise HTTPException(503, f"Server missing credentials: {', '.join(settings.missing())}")
    _enforce_spend_cap()

    job_id = uuid.uuid4().hex[:12]
    brief_dict = brief.model_dump()
    db.create_job(job_id, title=brief.title or brief.subject, brief=brief_dict,
                  parent_run_id=brief.parent_run_id)

    # Bounded pool: reject (don't queue unboundedly) when at capacity.
    if not job_runner.submit(run_generation, job_id, brief_dict):
        db.delete_job(job_id)
        raise HTTPException(503, "Server is at capacity — please retry shortly",
                            headers={"Retry-After": "30"})

    log.info("job queued", extra={"job_id": job_id})
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _serialize_job(job)


@app.get("/api/library")
def library(limit: int = 24, offset: int = 0) -> dict[str, Any]:
    page = db.list_jobs(limit=limit, offset=offset)
    return {
        "jobs": [_serialize_job(j) for j in page["jobs"]],
        "total_count": page["total_count"],
        "limit": page["limit"],
        "offset": page["offset"],
        "has_more": page["has_more"],
        "next_offset": page["next_offset"],
    }


@app.get("/api/passport/{job_id}")
def passport(job_id: str) -> dict[str, Any]:
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    data = _serialize_job(job)
    if job.get("manifest_json"):
        try:
            data["manifest"] = json.loads(job["manifest_json"])
        except (ValueError, TypeError):
            data["manifest"] = None
    return data


def _assert_allowed_asset_host(url: str) -> None:
    """Only proxy downloads from our own B2 storage — never an arbitrary URL.

    Asset URLs are server-written today, but guarding the egress here keeps this
    endpoint from becoming an SSRF/open-proxy if that ever changes.
    """
    host = (urlparse(url).hostname or "").lower()
    allowed = host.endswith(".backblazeb2.com") or host == "backblazeb2.com"
    if settings.b2_public_url_base:
        base_host = (urlparse(settings.b2_public_url_base).hostname or "").lower()
        allowed = allowed or (bool(base_host) and host == base_host)
    if not allowed:
        raise HTTPException(400, "Asset URL is not from an allowed storage host")


@app.get("/api/passport/{job_id}/download")
def download_verifiable(job_id: str):
    """Return the primary video with its provenance manifest embedded in-file.

    This is the 'tamper-evident copy' you can share — anyone can drop it into the
    Verify page (or `genblaze verify file.mp4`) and confirm its origin.
    """
    job = db.get_job(job_id)
    if not job or not job.get("manifest_json"):
        raise HTTPException(404, "No manifest for this job")

    video = next((a for a in job["assets"] if (a.get("modality") or "").endswith("video")), None)
    asset = video or (job["assets"][0] if job["assets"] else None)
    if not asset or not asset.get("url"):
        raise HTTPException(404, "No asset to embed")
    _assert_allowed_asset_host(asset["url"])

    from .media_tools import embed_manifest, manifest_from_json

    suffix = Path(asset["url"].split("?")[0]).suffix or ".mp4"
    tmpdir = Path(tempfile.mkdtemp(prefix="veritas_"))
    src = tmpdir / f"asset{suffix}"
    out = tmpdir / f"verified_{job_id}{suffix}"

    # Presign for the same reason the read paths do — a private bucket 401s the
    # durable URL. Host is asserted above on the durable URL; presigning keeps it.
    source_url = signed_url(asset["url"]) or asset["url"]

    try:
        with httpx.stream("GET", source_url, timeout=120, follow_redirects=False) as r:
            r.raise_for_status()
            with src.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        manifest = manifest_from_json(job["manifest_json"])
        embed_manifest(src, manifest, out)
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        log.exception("download build failed", extra={"job_id": job_id})
        raise HTTPException(500, "Could not build verifiable copy")

    # Clean up the temp dir only after the file has been streamed to the client.
    return FileResponse(
        out,
        filename=f"verified_{job_id}{suffix}",
        media_type="application/octet-stream",
        background=BackgroundTask(shutil.rmtree, tmpdir, ignore_errors=True),
    )


# admin
@app.post("/api/admin/login", dependencies=[Depends(throttle_login)])
def admin_login(body: LoginIn) -> dict[str, Any]:
    if not settings.verify_admin_password(body.password):
        raise HTTPException(401, "Incorrect password")
    return {"token": settings.admin_token}


@app.get("/api/admin/overview", dependencies=[Depends(require_admin)])
def admin_overview() -> dict[str, Any]:
    return {
        "health": health(),
        "stats": db.stats(),
        "recent_errors": db.recent_errors(),
    }


@app.post("/api/admin/jobs/{job_id}/retry", dependencies=[Depends(require_admin)])
def admin_retry(job_id: str) -> dict[str, Any]:
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if settings.missing():
        raise HTTPException(503, f"Server missing credentials: {', '.join(settings.missing())}")
    _enforce_spend_cap()
    try:
        brief = json.loads(job.get("brief") or "{}")
    except (ValueError, TypeError):
        brief = {}
    if not brief.get("subject"):
        raise HTTPException(400, "Original brief unavailable to retry")

    new_id = uuid.uuid4().hex[:12]
    db.create_job(new_id, title=brief.get("title") or brief.get("subject"), brief=brief,
                  parent_run_id=brief.get("parent_run_id"))
    if not job_runner.submit(run_generation, new_id, brief):
        db.delete_job(new_id)
        raise HTTPException(503, "Server is at capacity — please retry shortly",
                            headers={"Retry-After": "30"})
    log.info("job retried", extra={"job_id": new_id, "retried_from": job_id})
    return {"job_id": new_id, "status": "queued", "retried_from": job_id}


@app.delete("/api/admin/jobs/{job_id}", dependencies=[Depends(require_admin)])
def admin_delete(job_id: str) -> dict[str, Any]:
    ok = db.delete_job(job_id)
    if not ok:
        raise HTTPException(404, "Job not found")
    return {"deleted": job_id}


@app.post("/api/verify")
async def verify(file: UploadFile = File(...)):
    from .media_tools import extract_and_verify

    tmpdir = Path(tempfile.mkdtemp(prefix="veritas_verify_"))
    # Strip any path components from the client-supplied name (path traversal),
    # and cap the size while streaming so a huge upload can't exhaust memory/disk.
    safe_name = Path(file.filename or "upload.bin").name or "upload.bin"
    dest = tmpdir / safe_name
    try:
        size = 0
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(413, "File too large")
                out.write(chunk)
        result = extract_and_verify(dest)
        return JSONResponse(result)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# helpers
def _serialize_job(job: dict[str, Any]) -> dict[str, Any]:
    out = {
        "id": job["id"],
        "status": job["status"],
        "stage": job["stage"],
        "title": job["title"],
        "error": job.get("error"),
        "run_id": job.get("run_id"),
        "parent_run_id": job.get("parent_run_id"),
        "manifest_uri": job.get("manifest_uri"),
        "manifest_hash": job.get("manifest_hash"),
        "verified": bool(job.get("verified")),
        "cost_usd": job.get("cost_usd") or 0,
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        # Presigned at the boundary — the durable URL stored in the DB/manifest
        # is 401 against a private bucket, so browsers can't render it directly.
        "assets": [{**a, "url": signed_url(a.get("url"))} for a in job.get("assets", [])],
    }
    for key in ("brief", "plan", "steps"):
        if job.get(key):
            try:
                out[key] = json.loads(job[key])
            except (ValueError, TypeError):
                out[key] = None
    steps = out.get("steps") or []
    out["partial"] = job.get("status") == "completed" and any(
        s.get("error") or "fail" in str(s.get("status", "")).lower() for s in steps
    )
    return out
