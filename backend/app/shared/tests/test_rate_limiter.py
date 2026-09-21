"""`SlidingWindowRateLimiter`: window enforcement plus the PLAN 4.6.4 bounded-memory fixes —
opportunistic pruning of an expired bucket and a hard cap on distinct tracked keys."""

from __future__ import annotations

from app.shared.rate_limiter import SlidingWindowRateLimiter


def test_allows_up_to_max_requests_within_the_window() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    assert limiter.allow("k", now=0.0) is True
    assert limiter.allow("k", now=1.0) is True
    assert limiter.allow("k", now=2.0) is False


def test_request_is_allowed_again_once_the_window_elapses() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=10.0)
    assert limiter.allow("k", now=0.0) is True
    assert limiter.allow("k", now=5.0) is False
    assert limiter.allow("k", now=10.1) is True


def test_distinct_keys_are_independent() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    assert limiter.allow("a", now=0.0) is True
    assert limiter.allow("b", now=0.0) is True


def test_expired_bucket_is_pruned_from_the_dict_on_next_access() -> None:
    """PLAN 4.6.4: a key whose only hit has aged out of the window must not leave a stale
    zero-length bucket sitting in the dict forever."""
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=10.0)
    limiter.allow("k", now=0.0)
    assert len(limiter) == 1
    limiter.allow("k", now=100.0)  # old hit is well past the window
    assert len(limiter) == 1  # pruned then re-added for the new hit, not left growing


def test_bucket_count_stays_bounded_across_many_distinct_keys() -> None:
    """PLAN 4.6.4: without a cap, one-shot distinct keys (rotating IPs/principals) that are never
    revisited would never trigger the opportunistic prune above and would grow the dict forever."""
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60.0, max_tracked_keys=10)
    for i in range(50):
        limiter.allow(f"key-{i}", now=float(i))
    assert len(limiter) == 10


def test_max_tracked_keys_evicts_the_oldest_key_first() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60.0, max_tracked_keys=2)
    limiter.allow("a", now=0.0)
    limiter.allow("b", now=0.0)
    limiter.allow("c", now=0.0)  # should evict "a", the oldest
    assert len(limiter) == 2
    # "a" was evicted, so it gets a fresh bucket and is allowed again immediately
    assert limiter.allow("a", now=0.1) is True


def test_unbounded_when_max_tracked_keys_is_none() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60.0)
    for i in range(1000):
        limiter.allow(f"key-{i}", now=float(i))
    assert len(limiter) == 1000
