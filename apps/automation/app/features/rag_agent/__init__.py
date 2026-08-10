"""rag_agent feature: the grounded answer runtime over the Phase 3.5 retrieval spine.

A fixed, testable workflow (not an agent loop, ADR-0005 §5): conversational rewrite →
RLS-scoped retrieve → RRF → cross-encoder rerank → parent-context expansion → grounded
generation with forced citations → refusal threshold → at most one CRAG retry → SSE.

Public surface: the DTOs `POST /chat` (Phase 4.4) will serialise (`Answer`/`ChatMessage`/
`Citation`), the `AnswerService` orchestrator (Phase 4.2), and the `QueryRewriter`/
`AnswerGenerator` collaborator protocols + their Anthropic-backed implementations, so Phase 4.4
can wire real dependencies without reaching past this root. The refusal / citation / prompt
domain logic stays internal.

Status (Phase 4.2): the answer workflow is built and unit/integration-tested against the
fixture corpus (fake LLM collaborators — no network in tests). No HTTP surface yet (that's 4.4,
which also applies the `securing-http-and-llm-endpoints` control set this internal workflow does
not need yet).

Internal rule: modules inside this feature MUST NOT import through this root
(`from app.features.rag_agent import X`) — that raises ImportError during init. They deep-
import each other by full submodule path.
"""

from __future__ import annotations

from .application.answer_service import AnswerService
from .infrastructure.llm_client import (
    AnswerGenerator,
    AnthropicAnswerGenerator,
    AnthropicQueryRewriter,
    QueryRewriter,
)
from .schemas import Answer, ChatMessage, Citation

__all__ = [
    "Answer",
    "ChatMessage",
    "Citation",
    "AnswerService",
    "QueryRewriter",
    "AnswerGenerator",
    "AnthropicQueryRewriter",
    "AnthropicAnswerGenerator",
]
