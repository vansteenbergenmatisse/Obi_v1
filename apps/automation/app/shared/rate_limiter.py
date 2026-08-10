"""In-process sliding-window rate limiter (C2 control), shared across HTTP surfaces.

Originally lived inside `confluence_sync/server/webhook.py`; extracted here once a second
consumer (the `rag_agent` chat endpoint, PLAN 4.4) needed the exact same mechanism — a generic
technical primitive with no feature-specific behavior belongs in `shared`, not in whichever
feature happened to write it first.

Adequate for a single-process deployment. Multi-instance deployment needs a shared store (Redis) —
intentionally deferred until horizontal scale is a confirmed requirement (proportionality gate).
"""

from __future__ import annotations

import time
from collections import deque


class SlidingWindowRateLimiter:
    """In-process per-key sliding-window limiter. One instance per app per limited surface."""

    def __init__(self, max_requests: int, window_seconds: float = 60.0) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        bucket = self._hits.setdefault(key, deque())
        cutoff = now - self._window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self._max:
            return False
        bucket.append(now)
        return True
