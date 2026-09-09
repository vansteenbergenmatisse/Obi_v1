"""`CachingAnswerService` (PLAN 5): exact-match cache decorator, unit-tested with a fake
`AnswerProvider` — no network, no DB. Asserts on *call count* into the inner provider, not just
the returned `Answer`, since the whole point of the cache is to skip that work."""

from __future__ import annotations

from app.features.rag_agent.application.answer_cache import CachingAnswerService
from app.features.rag_agent.schemas import Answer, ChatMessage


class _CountingProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[tuple[str, str], ...], str | None, str | None]] = []

    def answer(self, history, scope, knowledge_scope=None):
        self.calls.append((tuple((m.role, m.content) for m in history), scope, knowledge_scope))
        n = len(self.calls)
        return Answer(text=f"answer #{n}", refused=False, trace_id=str(n))


def _history(text: str) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=text)]


def test_identical_history_and_scope_is_served_from_cache() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    first = cache.answer(_history("what is the vpn policy"), "alice")
    second = cache.answer(_history("what is the vpn policy"), "alice")

    assert len(inner.calls) == 1
    assert first == second


def test_different_scope_is_not_served_from_cache() -> None:
    """The cache key includes principal — a hit must never cross a principal boundary."""
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    cache.answer(_history("what is the vpn policy"), "alice")
    cache.answer(_history("what is the vpn policy"), "bob")

    assert len(inner.calls) == 2


def test_different_history_is_not_served_from_cache() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    cache.answer(_history("what is the vpn policy"), "alice")
    cache.answer(_history("what is the pto policy"), "alice")

    assert len(inner.calls) == 2


def test_earlier_turns_are_part_of_the_cache_key() -> None:
    """Same final turn, different earlier context -> different key (rewrite can use history)."""
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    history_a = [
        ChatMessage(role="user", content="I'm on the platform team"),
        ChatMessage(role="assistant", content="Got it."),
        ChatMessage(role="user", content="what's the policy"),
    ]
    history_b = [
        ChatMessage(role="user", content="I'm a new hire"),
        ChatMessage(role="assistant", content="Welcome."),
        ChatMessage(role="user", content="what's the policy"),
    ]
    cache.answer(history_a, "alice")
    cache.answer(history_b, "alice")

    assert len(inner.calls) == 2


def test_expired_entry_recomputes(monkeypatch) -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=10.0)
    clock = [1000.0]
    monkeypatch.setattr("app.shared.ttl_cache.time.monotonic", lambda: clock[0])

    cache.answer(_history("what is the vpn policy"), "alice")
    clock[0] += 10.1
    cache.answer(_history("what is the vpn policy"), "alice")

    assert len(inner.calls) == 2


def test_identical_history_scope_and_knowledge_scope_is_served_from_cache() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    first = cache.answer(_history("what is the vpn policy"), "alice", "obi-mews-test")
    second = cache.answer(_history("what is the vpn policy"), "alice", "obi-mews-test")

    assert len(inner.calls) == 1
    assert first == second


def test_different_knowledge_scope_is_not_served_from_cache() -> None:
    """PLAN 10.5: a cached answer was retrieved under one resolved knowledge-scope allow-list — a
    hit must never cross a knowledge-scope boundary, mirroring the pre-existing principal check."""
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    cache.answer(_history("what is the vpn policy"), "alice", "obi-mews-test")
    cache.answer(_history("what is the vpn policy"), "alice", "obi-operacloud-test")

    assert len(inner.calls) == 2


def test_omitted_knowledge_scope_is_not_conflated_with_a_named_one() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    cache.answer(_history("what is the vpn policy"), "alice")
    cache.answer(_history("what is the vpn policy"), "alice", "obi-mews-test")

    assert len(inner.calls) == 2


def test_max_entries_bounds_the_cache() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0, max_entries=1)

    cache.answer(_history("question one"), "alice")
    cache.answer(_history("question two"), "alice")  # evicts "question one"'s entry
    cache.answer(_history("question one"), "alice")  # cache miss again

    assert len(inner.calls) == 3
