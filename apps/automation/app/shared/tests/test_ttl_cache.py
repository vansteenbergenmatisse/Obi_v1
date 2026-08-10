"""`TTLCache`: expiry and max-entries eviction — the two behaviors its two consumers (the
`Idempotency-Key` replay cache and the PLAN 5 exact-match answer cache) both depend on."""

from __future__ import annotations

from app.shared.ttl_cache import TTLCache


def test_hit_returns_the_stored_value() -> None:
    cache: TTLCache[str, str] = TTLCache(ttl_seconds=60.0)
    cache.set("k", "v")
    assert cache.get("k") == "v"


def test_miss_on_unknown_key_returns_none() -> None:
    cache: TTLCache[str, str] = TTLCache(ttl_seconds=60.0)
    assert cache.get("missing") is None


def test_entry_expires_after_ttl(monkeypatch) -> None:
    cache: TTLCache[str, str] = TTLCache(ttl_seconds=10.0)
    clock = [1000.0]
    monkeypatch.setattr("app.shared.ttl_cache.time.monotonic", lambda: clock[0])
    cache.set("k", "v")
    clock[0] += 10.1
    assert cache.get("k") is None


def test_entry_survives_up_to_the_ttl_boundary(monkeypatch) -> None:
    cache: TTLCache[str, str] = TTLCache(ttl_seconds=10.0)
    clock = [1000.0]
    monkeypatch.setattr("app.shared.ttl_cache.time.monotonic", lambda: clock[0])
    cache.set("k", "v")
    clock[0] += 9.9
    assert cache.get("k") == "v"


def test_expired_entry_is_evicted_on_read() -> None:
    cache: TTLCache[str, str] = TTLCache(ttl_seconds=0.0)
    cache.set("k", "v")
    assert cache.get("k") is None
    assert len(cache) == 0


def test_max_entries_evicts_the_oldest_insertion() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=60.0, max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # should evict "a", the oldest
    assert len(cache) == 2
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_unbounded_when_max_entries_is_none() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=60.0)
    for i in range(1000):
        cache.set(str(i), i)
    assert len(cache) == 1000
