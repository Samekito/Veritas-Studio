"""Bounded background execution for generation runs.

Generation is long (minutes) and spends money, so we cap how many run at once
instead of spawning an unbounded daemon thread per request. When the pool is at
capacity `submit` returns False and the caller responds 503/429 — backpressure
rather than silent resource + credit exhaustion.

Correlation ids are propagated into the worker so a job's logs stay linkable to
the request that created it.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .logging_setup import correlation_id, get_logger

log = get_logger("veritas.jobs")


class BoundedJobRunner:
    def __init__(self, max_concurrent: int) -> None:
        self.max_concurrent = max(1, max_concurrent)
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_concurrent, thread_name_prefix="genjob"
        )
        self._active = 0
        self._lock = threading.Lock()

    @property
    def active(self) -> int:
        with self._lock:
            return self._active

    def submit(self, fn: Callable[..., Any], *args: Any) -> bool:
        """Run `fn(*args)` on the pool. Returns False if already at capacity."""
        with self._lock:
            if self._active >= self.max_concurrent:
                return False
            self._active += 1

        cid = correlation_id.get()

        def _wrapped() -> None:
            token = correlation_id.set(cid)
            try:
                fn(*args)
            except Exception:  # last-resort guard so a bug never leaks a slot
                log.exception("job crashed")
            finally:
                correlation_id.reset(token)
                with self._lock:
                    self._active -= 1

        self._executor.submit(_wrapped)
        return True

    def shutdown(self) -> None:
        # Don't block server shutdown on in-flight generation; let daemon-style
        # workers wind down. Stale rows are reconciled on next startup.
        self._executor.shutdown(wait=False, cancel_futures=True)
