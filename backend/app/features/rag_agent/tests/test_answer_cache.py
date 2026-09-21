"""`CachingAnswerService` (PLAN 5): exact-match cache decorator, unit-tested with a fake
`AnswerProvider` — no network, no DB. Asserts on *call count* into the inner provider, not just
the returned `Answer`, since the whole point of the cache is to skip that work.

PLAN 11.1c (ADR-0014): the cache is now keyed off the frozen `AuthContext` — a hit can never
cross a principal, a knowledge-scope allow-list, or a token-subject boundary."""

from __future__ import annotations

from app.features.rag_agent.application.answer_cache import CachingAnswerService
from app.features.rag_agent.application.auth_context import AuthContext
from app.features.rag_agent.schemas import Answer, ChatMessage


def _auth(
    principal: str | None = None,
    scopes: tuple[str, ...] = ("obi-general-test",),
    token_subject: str | None = None,
) -> AuthContext:
    return AuthContext(None, None, None, scopes, ("confluence:default",), principal, token_subject)


class _CountingProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[tuple[str, str], ...], str | None, tuple[str, ...]]] = []

    def answer(self, history, auth: AuthContext):
        self.calls.append(
            (tuple((m.role, m.content) for m in history), auth.principal, auth.allowed_scopes)
        )
        n = len(self.calls)
        return Answer(text=f"answer #{n}", refused=False, trace_id=str(n))


def _history(text: str) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=text)]


def test_identical_history_and_scope_is_served_from_cache() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    first = cache.answer(_history("what is the vpn policy"), _auth(principal="alice"))
    second = cache.answer(_history("what is the vpn policy"), _auth(principal="alice"))

    assert len(inner.calls) == 1
    assert first == second


def test_different_scope_is_not_served_from_cache() -> None:
    """The cache key includes principal — a hit must never cross a principal boundary."""
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    cache.answer(_history("what is the vpn policy"), _auth(principal="alice"))
    cache.answer(_history("what is the vpn policy"), _auth(principal="bob"))

    assert len(inner.calls) == 2


def test_different_history_is_not_served_from_cache() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    cache.answer(_history("what is the vpn policy"), _auth(principal="alice"))
    cache.answer(_history("what is the pto policy"), _auth(principal="alice"))

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
    cache.answer(history_a, _auth(principal="alice"))
    cache.answer(history_b, _auth(principal="alice"))

    assert len(inner.calls) == 2


def test_expired_entry_recomputes(monkeypatch) -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=10.0)
    clock = [1000.0]
    monkeypatch.setattr("app.shared.ttl_cache.time.monotonic", lambda: clock[0])

    cache.answer(_history("what is the vpn policy"), _auth(principal="alice"))
    clock[0] += 10.1
    cache.answer(_history("what is the vpn policy"), _auth(principal="alice"))

    assert len(inner.calls) == 2


def test_identical_history_scope_and_knowledge_scope_is_served_from_cache() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    scopes = ("obi-general-test", "obi-mews-test")
    first = cache.answer(
        _history("what is the vpn policy"), _auth(principal="alice", scopes=scopes)
    )
    second = cache.answer(
        _history("what is the vpn policy"), _auth(principal="alice", scopes=scopes)
    )

    assert len(inner.calls) == 1
    assert first == second


def test_different_knowledge_scope_is_not_served_from_cache() -> None:
    """PLAN 10.5/11.1c: a cached answer was retrieved under one knowledge-scope allow-list — a hit
    must never cross a knowledge-scope boundary, mirroring the principal check."""
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    cache.answer(
        _history("what is the vpn policy"),
        _auth(principal="alice", scopes=("obi-general-test", "obi-mews-test")),
    )
    cache.answer(
        _history("what is the vpn policy"),
        _auth(principal="alice", scopes=("obi-general-test", "obi-operacloud-test")),
    )

    assert len(inner.calls) == 2


def test_omitted_knowledge_scope_is_not_conflated_with_a_named_one() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    cache.answer(_history("what is the vpn policy"), _auth(principal="alice"))
    cache.answer(
        _history("what is the vpn policy"),
        _auth(principal="alice", scopes=("obi-general-test", "obi-mews-test")),
    )

    assert len(inner.calls) == 2


def test_different_token_subject_is_not_served_from_cache() -> None:
    """PLAN 11.1c: two verified users (same integration/scopes, different subject) must not share
    a cached answer — the subject is part of the key."""
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    cache.answer(_history("what is the vpn policy"), _auth(token_subject="user-a"))
    cache.answer(_history("what is the vpn policy"), _auth(token_subject="user-b"))

    assert len(inner.calls) == 2


def test_max_entries_bounds_the_cache() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0, max_entries=1)

    cache.answer(_history("question one"), _auth(principal="alice"))
    cache.answer(_history("question two"), _auth(principal="alice"))  # evicts "question one"
    cache.answer(_history("question one"), _auth(principal="alice"))  # cache miss again

    assert len(inner.calls) == 3
