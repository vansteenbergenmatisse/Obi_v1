"""Generic in-process TTL cache, shared across HTTP surfaces.

Extracted from `rag_agent/server/router.py`'s `Idempotency-Key` replay cache (PLAN 4.4) once a
second consumer (the PLAN 5 exact-match answer cache) needed the exact same get/set/expire/bound
mechanism — the same "two consumers" proportionality trigger that already moved
`SlidingWindowRateLimiter` here.

Adequate for a single-process deployment, like its sibling `rate_limiter.py`. Multi-instance
deployment needs a shared store (Redis) — intentionally deferred until horizontal scale is a
confirmed requirement (proportionality gate).

Eviction is insertion-order (oldest-inserted-first), not true LRU (access doesn't reorder) — a
deliberate simplification: `max_entries` exists to bound memory, not to maximize hit rate, and the
call sites here have single-digit-to-low-hundreds working sets.
"""

from __future__ import annotations

import time


class TTLCache[K, V]:
    """In-process TTL cache with an optional max-entries bound. One instance per cached surface."""

    def __init__(self, ttl_seconds: float, max_entries: int | None = None) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._entries: dict[K, tuple[float, V]] = {}

    def get(self, key: K) -> V | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > self._ttl:
            del self._entries[key]
            return None
        return value

    def set(self, key: K, value: V) -> None:
        self._entries[key] = (time.monotonic(), value)
        if self._max_entries is not None:
            while len(self._entries) > self._max_entries:
                oldest_key = next(iter(self._entries))
                del self._entries[oldest_key]

    def __len__(self) -> int:
        return len(self._entries)
