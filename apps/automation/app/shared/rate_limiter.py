"""In-process sliding-window rate limiter (C2 control), shared across HTTP surfaces.

Originally lived inside `confluence_sync/server/webhook.py`; extracted here once a second
consumer (the `rag_agent` chat endpoint, PLAN 4.4) needed the exact same mechanism — a generic
technical primitive with no feature-specific behavior belongs in `shared`, not in whichever
feature happened to write it first.

Adequate for a single-process deployment. Multi-instance deployment needs a shared store (Redis) —
intentionally deferred until horizontal scale is a confirmed requirement (proportionality gate).

Bounded memory (PLAN 4.6.4 fix): a key whose bucket empties out (every hit aged past the window)
is dropped opportunistically the next time that same key is looked up, and an optional
`max_tracked_keys` evicts the oldest-inserted key outright once the dict grows past it — the same
oldest-first bound `TTLCache.max_entries` already uses, for the same reason: a caller that never
revisits a key (many distinct one-shot IPs, say) would otherwise never trigger the opportunistic
prune and could grow the dict unboundedly.
"""

from __future__ import annotations

import time
from collections import deque


class SlidingWindowRateLimiter:
    """In-process per-key sliding-window limiter. One instance per app per limited surface."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: float = 60.0,
        max_tracked_keys: int | None = None,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._max_tracked_keys = max_tracked_keys
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        cutoff = now - self._window
        bucket = self._hits.get(key)
        if bucket is not None:
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if not bucket:
                del self._hits[key]
                bucket = None
        if bucket is None:
            bucket = deque()
            self._hits[key] = bucket
            if self._max_tracked_keys is not None:
                while len(self._hits) > self._max_tracked_keys:
                    oldest_key = next(iter(self._hits))
                    del self._hits[oldest_key]
        if len(bucket) >= self._max:
            return False
        bucket.append(now)
        return True

    def __len__(self) -> int:
        return len(self._hits)
