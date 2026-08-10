"""rag_agent feature: the grounded answer runtime over the Phase 3.5 retrieval spine.

A fixed, testable workflow (not an agent loop, ADR-0005 §5): conversational rewrite →
RLS-scoped retrieve → RRF → cross-encoder rerank → parent-context expansion → grounded
generation with forced citations → refusal threshold → at most one CRAG retry → SSE.

Public surface: the DTOs `POST /chat` serialises (`Answer`/`ChatMessage`/`Citation`), the
`AnswerService` orchestrator (Phase 4.2), the `AnswerProvider` protocol it satisfies (the shape
`router.py` actually depends on) plus `CachingAnswerService` (Phase 5, an exact-match cache
decorator around any `AnswerProvider`), the `QueryRewriter`/`AnswerGenerator` collaborator
protocols + their Anthropic-backed implementations, and — as of Phase 4.4 — `router` (the
`POST /chat` + `PATCH /chat/{trace_id}/feedback` HTTP surface `app.main` includes). The refusal /
citation / prompt / PII-redaction domain logic stays internal.

Status (Phase 4.4): the answer workflow (4.2) and persisted principal ACL (4.3) are wired to a
real HTTP surface with the full `securing-http-and-llm-endpoints` control set applied (auth, rate
limit, input validation, LLM timeout/retry/breaker, output pacing, PII redaction, idempotency,
audit logging, abuse caps) — see `server/router.py`'s `security_baseline` docstring.

Internal rule: modules inside this feature MUST NOT import through this root
(`from app.features.rag_agent import X`) — that raises ImportError during init. They deep-
import each other by full submodule path.
"""

from __future__ import annotations

from .application.answer_cache import CachingAnswerService
from .application.answer_service import AnswerProvider, AnswerService
from .infrastructure.llm_client import (
    AnswerGenerator,
    AnthropicAnswerGenerator,
    AnthropicQueryRewriter,
    QueryRewriter,
)
from .schemas import Answer, ChatMessage, Citation
from .server import router

__all__ = [
    "Answer",
    "ChatMessage",
    "Citation",
    "AnswerService",
    "AnswerProvider",
    "CachingAnswerService",
    "QueryRewriter",
    "AnswerGenerator",
    "AnthropicQueryRewriter",
    "AnthropicAnswerGenerator",
    "router",
]
