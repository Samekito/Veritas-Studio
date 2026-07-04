"""Thin SQLite index over generation runs and their assets.

This is the local mirror of what lives in B2: every run gets a row here so the
library, dashboard, and Content Passport pages can query fast without hitting B2.
The authoritative artifacts (media + provenance manifest) live in the bucket.

Every connection is opened inside `contextlib.closing` so it is closed (not just
committed) when the block exits — `sqlite3`'s own context manager commits but
leaves the connection open, which leaks file handles under sustained traffic.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import closing
from typing import Any

from .config import settings

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _lock, closing(_conn()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id            TEXT PRIMARY KEY,
                status        TEXT NOT NULL,          -- queued|running|completed|failed
                stage         TEXT,                   -- human-readable current step
                title         TEXT,
                brief         TEXT,                   -- JSON of the original brief
                plan          TEXT,                   -- JSON of the generated plan
                error         TEXT,
                run_id        TEXT,
                parent_run_id TEXT,
                manifest_uri  TEXT,
                manifest_hash TEXT,
                manifest_json TEXT,                   -- full provenance manifest
                verified      INTEGER DEFAULT 0,
                cost_usd      REAL DEFAULT 0,
                created_at    REAL NOT NULL,
                updated_at    REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS assets (
                id          TEXT PRIMARY KEY,
                job_id      TEXT NOT NULL,
                run_id      TEXT,
                step_index  INTEGER,
                modality    TEXT,
                provider    TEXT,
                model       TEXT,
                url         TEXT,
                sha256      TEXT,
                media_type  TEXT,
                created_at  REAL NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            );

            CREATE INDEX IF NOT EXISTS idx_assets_job ON assets(job_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
            """
        )
        # Lightweight migration: add per-step detail column if an older DB predates it.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "steps" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN steps TEXT")


def reconcile_stale_jobs() -> int:
    """Fail jobs left mid-flight by a crash/restart.

    Background generation lives only in worker threads; if the process dies, any
    'queued'/'running' rows are orphaned forever. On startup we mark them failed
    so the UI shows a terminal state instead of a spinner that never resolves.
    Returns the number of rows reconciled.
    """
    now = time.time()
    with _lock, closing(_conn()) as conn, conn:
        cur = conn.execute(
            "UPDATE jobs SET status='failed', stage='Failed', "
            "error='Interrupted by a server restart', updated_at=? "
            "WHERE status IN ('queued','running')",
            (now,),
        )
        return cur.rowcount


def create_job(job_id: str, title: str, brief: dict[str, Any], parent_run_id: str | None) -> None:
    now = time.time()
    with _lock, closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO jobs (id, status, stage, title, brief, parent_run_id, created_at, updated_at) "
            "VALUES (?, 'queued', 'Queued', ?, ?, ?, ?, ?)",
            (job_id, title, json.dumps(brief), parent_run_id, now, now),
        )


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _lock, closing(_conn()) as conn, conn:
        conn.execute(f"UPDATE jobs SET {cols} WHERE id = ?", (*fields.values(), job_id))


def add_asset(asset: dict[str, Any]) -> None:
    with _lock, closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT OR REPLACE INTO assets "
            "(id, job_id, run_id, step_index, modality, provider, model, url, sha256, media_type, created_at) "
            "VALUES (:id, :job_id, :run_id, :step_index, :modality, :provider, :model, :url, :sha256, :media_type, :created_at)",
            asset,
        )


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock, closing(_conn()) as conn, conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        job = dict(row)
        assets = conn.execute(
            "SELECT * FROM assets WHERE job_id = ? ORDER BY step_index", (job_id,)
        ).fetchall()
        job["assets"] = [dict(a) for a in assets]
        return job


def delete_job(job_id: str) -> bool:
    with _lock, closing(_conn()) as conn, conn:
        cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.execute("DELETE FROM assets WHERE job_id = ?", (job_id,))
        return cur.rowcount > 0


def list_jobs(limit: int = 24, offset: int = 0) -> dict[str, Any]:
    """Paginated jobs newest-first, with their assets attached in one extra query.

    Assets are fetched with a single `job_id IN (...)` query and grouped in
    memory rather than one query per job (avoids an N+1 over the page).
    """
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    with _lock, closing(_conn()) as conn, conn:
        total = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        jobs = [dict(r) for r in rows]

        ids = [j["id"] for j in jobs]
        by_job: dict[str, list[dict[str, Any]]] = {jid: [] for jid in ids}
        if ids:
            placeholders = ",".join("?" for _ in ids)
            assets = conn.execute(
                f"SELECT * FROM assets WHERE job_id IN ({placeholders}) ORDER BY step_index",
                ids,
            ).fetchall()
            for a in assets:
                by_job[a["job_id"]].append(dict(a))
        for j in jobs:
            j["assets"] = by_job.get(j["id"], [])

    return {
        "jobs": jobs,
        "total_count": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(jobs) < total,
        "next_offset": offset + len(jobs) if offset + len(jobs) < total else None,
    }


def cost_since(since_epoch: float) -> float:
    """Total generation spend recorded at/after `since_epoch` (for a rolling cap)."""
    with _lock, closing(_conn()) as conn, conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0) s FROM jobs WHERE updated_at >= ?",
            (since_epoch,),
        ).fetchone()
        return float(row["s"] or 0)


def stats() -> dict[str, Any]:
    with _lock, closing(_conn()) as conn, conn:
        total = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
        completed = conn.execute(
            "SELECT COUNT(*) c FROM jobs WHERE status='completed'"
        ).fetchone()["c"]
        failed = conn.execute("SELECT COUNT(*) c FROM jobs WHERE status='failed'").fetchone()["c"]
        running = conn.execute(
            "SELECT COUNT(*) c FROM jobs WHERE status IN ('running','queued')"
        ).fetchone()["c"]
        verified = conn.execute("SELECT COUNT(*) c FROM jobs WHERE verified=1").fetchone()["c"]
        cost = conn.execute("SELECT COALESCE(SUM(cost_usd),0) s FROM jobs").fetchone()["s"]
        assets = conn.execute("SELECT COUNT(*) c FROM assets").fetchone()["c"]
        return {
            "runs": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "verified": verified,
            "assets": assets,
            "total_cost_usd": round(cost or 0, 4),
        }


def recent_errors(limit: int = 8) -> list[dict[str, Any]]:
    with _lock, closing(_conn()) as conn, conn:
        rows = conn.execute(
            "SELECT id, title, error, updated_at FROM jobs "
            "WHERE error IS NOT NULL AND error != '' ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
