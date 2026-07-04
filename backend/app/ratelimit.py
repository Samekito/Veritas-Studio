"""In-process sliding-window rate limiting, keyed by client IP.

Dependency-free and in-memory: Render's single instance makes a process-local
window sufficient defence-in-depth. A multi-worker/multi-instance deploy would
back this with a shared store (e.g. Redis) instead — the interface stays the
same.

`client_ip_from_request` resolves the real client behind a reverse proxy by
walking `X-Forwarded-For` from the right, skipping exactly `trusted_hops`
proxy-added entries. Trusting a fixed number of hops (rather than the whole
header) prevents a client from spoofing its IP by prepending fake entries.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class SlidingWindowRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        """Record a hit for `key`; raise HTTP 429 if the window is exhausted."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_attempts:
                retry_after = int(self.window_seconds - (now - hits[0])) + 1
                raise HTTPException(
                    429,
                    "Too many requests — try again later",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)


def client_ip_from_request(request: Request, trusted_hops: int = 1) -> str:
    """Best-effort real client IP, accounting for `trusted_hops` reverse proxies."""
    xff = request.headers.get("x-forwarded-for")
    if xff and trusted_hops > 0:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            # The rightmost entries are added by our own proxies; step past them.
            idx = max(0, len(parts) - trusted_hops - 1)
            return parts[idx]
    return request.client.host if request.client else "unknown"
