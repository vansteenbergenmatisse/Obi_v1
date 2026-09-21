"""Exact-match answer cache (PLAN 5 caching): a `CachingAnswerService` decorator wrapping any
`AnswerProvider` (normally the real `AnswerService`) so a byte-for-byte repeat of the same
conversation, from the same principal, skips retrieval + generation entirely and replays the
cached `Answer`.

Deliberately scoped to *exact* match only. The plan text also names a semantic cache (similarity
search over past queries); that is not built here — a similarity-threshold match risks serving a
plausible-but-wrong cached answer for a query that actually needed fresh retrieval, which conflicts
with this project's accuracy-first mandate, and there is no production traffic yet to tune a safe
threshold against (no invented number). Deferred, not forgotten — see PLAN.md §Phase 5.

Cache key is
`sha256(json([(role, content) for turn in history]) + "|" + (scope or "") + "|" + (knowledge_scope
or ""))` — the *full* history, not just the final turn, because the rewrite stage can use earlier
turns as context; two calls with different earlier turns are not guaranteed to produce the same
answer even if their final turn matches. `scope` (the caller's `principal`) is part of the key so
a cache hit can never leak one principal's answer to another — `AnswerService.answer`'s own ACL
enforcement already runs once, at write time, before this cache ever sees the result.
`knowledge_scope` (PLAN 10.5) is part of the key for the identical reason: a cached answer was
retrieved under one resolved knowledge-scope allow-list, so a later request naming a *different*
`knowledge_scope` with otherwise-identical history/principal must not replay evidence scoped to a
provider it never asked for — not named in PLAN 10.5's own file list, but required by the same
correctness argument as the pre-existing `scope` binding above.

Same staleness shape as the pre-existing `Idempotency-Key` replay cache (PLAN 4.4): a cached answer
reflects the corpus/ACL state at the moment it was generated and can be up to `ttl_seconds` stale if
a page's restrictions or content change during that window. That is an accepted, bounded tradeoff
already made for idempotency; this reuses the identical `TTLCache` mechanism and a comparable
default TTL.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from app.features.rag_agent.application.answer_service import AnswerProvider
from app.features.rag_agent.application.auth_context import AuthContext
from app.features.rag_agent.schemas import Answer, ChatMessage
from app.platform.logging import get_logger
from app.shared.ttl_cache import TTLCache

log = get_logger("rag_agent.answer_cache")


def _cache_key(history: Sequence[ChatMessage], auth: AuthContext) -> str:
    """PLAN 11.1c (ADR-0014): the key binds the full history to the verified edge identity —
    `principal` (page-ACL), `allowed_scopes` (knowledge scope), and `token_subject`. A cache hit
    can therefore never cross a principal, a scope allow-list, or a subject boundary; the raw
    token is never part of the key (only its verified subject)."""
    turns = [(m.role, m.content) for m in history]
    payload = (
        json.dumps(turns, separators=(",", ":"))
        + "|"
        + (auth.principal or "")
        + "|"
        + ",".join(auth.allowed_scopes)
        + "|"
        + (auth.token_subject or "")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CachingAnswerService:
    """Wraps an `AnswerProvider` with an in-process exact-match TTL cache in front of it."""

    def __init__(
        self,
        inner: AnswerProvider,
        *,
        ttl_seconds: float,
        max_entries: int | None = None,
    ) -> None:
        self._inner = inner
        self._cache: TTLCache[str, Answer] = TTLCache(ttl_seconds, max_entries)

    def answer(self, history: Sequence[ChatMessage], auth: AuthContext) -> Answer:
        key = _cache_key(history, auth)
        cached = self._cache.get(key)
        if cached is not None:
            log.info("chat_answer_cache_hit", trace_id=cached.trace_id)
            return cached
        result = self._inner.answer(history, auth)
        self._cache.set(key, result)
        return result
