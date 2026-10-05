"""`CachingAnswerService` (PLAN 5): exact-match cache decorator, unit-tested with a fake
`AnswerProvider` — no network, no DB. Asserts on *call count* into the inner provider, not just
the returned `Answer`, since the whole point of the cache is to skip that work.

PLAN 11.1c (ADR-0014): the cache is now keyed off the frozen `AuthContext` — a hit can never
cross a principal, a knowledge-scope allow-list, or a token-subject boundary."""

from __future__ import annotations

from app.features.rag_agent.application.answer_cache import CachingAnswerService, _cache_key
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


def test_cip3_distinct_token_subjects_never_share_a_cache_key_or_entry() -> None:
    """gap CIP-3 · ADR-0014. Two verified users with byte-for-byte identical history (and identical
    principal/scopes) must never collide in the answer cache: the `token_subject` is part of the
    key, so their keys differ AND a first user's entry is never replayed to the second. Asserts BOTH
    the key-level property (no collision by construction) and the behavioral one (no cross-subject
    hit through `CachingAnswerService`), so a regression in either the key or its use is caught."""
    history = _history("what is the vpn policy")
    user_a = _auth(token_subject="user-a")
    user_b = _auth(token_subject="user-b")

    # key level: same history/principal/scopes, different subject -> different cache key.
    assert _cache_key(history, user_a) != _cache_key(history, user_b)

    # behavioral level: user B's identical question is a miss, never user A's cached Answer.
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)
    first = cache.answer(history, user_a)
    second = cache.answer(history, user_b)
    assert len(inner.calls) == 2  # recomputed for B, not served from A's entry
    assert first != second  # distinct Answers (distinct trace ids), no cross-subject replay


class _FixedAnswerProvider:
    """Counts calls and returns one fixed `Answer` — lets a test push a small-talk or refusal
    shape through the cache (gap G17: the single `answer()` entrypoint has no bypass)."""

    def __init__(self, fixed: Answer) -> None:
        self.fixed = fixed
        self.calls = 0

    def answer(self, history, auth: AuthContext) -> Answer:
        self.calls += 1
        return self.fixed


def test_g17_small_talk_answer_is_served_from_cache() -> None:
    """gap G17 (4.2 coverage audit) · PLAN 5 cache. A small-talk Answer (`trace_id=None` — no
    retrieval ran, no trace row) still flows through the one cached `answer()` entrypoint: an
    identical repeat replays it and the inner provider runs exactly once."""
    inner = _FixedAnswerProvider(
        Answer(text="Hi! Ask me about Omniboost.", refused=False, trace_id=None)
    )
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    first = cache.answer(_history("hello"), _auth(principal="alice"))
    second = cache.answer(_history("hello"), _auth(principal="alice"))

    assert inner.calls == 1
    assert second == first
    assert second.trace_id is None and second.refused is False


def test_g17_refused_answer_is_served_from_cache() -> None:
    """gap G17 (4.2 coverage audit) · PLAN 5 cache. A refusal (`refused=True`) is cached like any
    other Answer: the identical repeat (same identity, same history) is a hit, so a refusal never
    re-runs retrieval + generation just to refuse again."""
    inner = _FixedAnswerProvider(
        Answer(text="I can't answer that from the documentation.", refused=True, trace_id="42")
    )
    cache = CachingAnswerService(inner, ttl_seconds=60.0)

    first = cache.answer(_history("what is the launch code"), _auth(principal="alice"))
    second = cache.answer(_history("what is the launch code"), _auth(principal="alice"))

    assert inner.calls == 1
    assert second == first
    assert second.refused is True


def test_g19_cache_key_and_cached_value_carry_no_raw_token_material() -> None:
    """gap G19 (4.2 coverage audit) · regression lock on `_cache_key` + the stored entry.
    The key binds identity through the DERIVED `token_subject` (issuer-NUL-subject, never the raw
    bearer token) and is a pure sha256 hex digest: neither the raw token string nor any plaintext
    key input (subject, principal, history) is readable in it, and the stored Answer carries no
    token material either — a change that made the key a readable concatenation, or stored the
    token on the Answer, goes red here."""
    raw_token = "eyJhbGciOiJSUzI1NiIsImtpZCI6ImsxIn0.c2VjcmV0LWJvZHk.raw-bearer-signature-material"
    # What actually reaches the cache: the derived identity (auth_context._identity_key shape),
    # never `raw_token` itself — AuthContext has no field that could carry it.
    token_subject = "https://app.mews.com\x00user-7"
    history = _history("what is the vpn policy")
    auth = _auth(principal="alice", token_subject=token_subject)

    key = _cache_key(history, auth)

    assert len(key) == 64 and set(key) <= set("0123456789abcdef")  # a bare sha256 hex digest
    assert raw_token not in key
    assert token_subject not in key and "user-7" not in key  # hashed, never concatenated
    assert "alice" not in key and "vpn" not in key

    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0)
    cache.answer(history, auth)
    replayed = cache.answer(history, auth)  # the stored entry, replayed verbatim
    assert len(inner.calls) == 1
    stored = replayed.model_dump_json()
    assert raw_token not in stored and token_subject not in stored and "user-7" not in stored


def test_max_entries_bounds_the_cache() -> None:
    inner = _CountingProvider()
    cache = CachingAnswerService(inner, ttl_seconds=60.0, max_entries=1)

    cache.answer(_history("question one"), _auth(principal="alice"))
    cache.answer(_history("question two"), _auth(principal="alice"))  # evicts "question one"
    cache.answer(_history("question one"), _auth(principal="alice"))  # cache miss again

    assert len(inner.calls) == 3
