"""rag_agent feature: the grounded answer runtime over the Phase 3.5 retrieval spine.

A fixed, testable workflow (not an agent loop, ADR-0005 §5): conversational rewrite →
RLS-scoped retrieve → RRF → cross-encoder rerank → parent-context expansion → grounded
generation with forced citations → refusal threshold → at most one CRAG retry → SSE.

Public surface. Only the answer contract crosses this boundary today: the DTOs that
`POST /chat` (Phase 4.4) serialises. The answer service is added to this root in Phase 4.2
once its pipeline exists; the refusal / citation domain logic stays internal.

Status (Phase 4.1): scaffold — DTO contract + pure domain core (refusal, citation
enforcement) with unit tests. No LLM, DB, or HTTP surface yet.

Internal rule: modules inside this feature MUST NOT import through this root
(`from app.features.rag_agent import X`) — that raises ImportError during init. They deep-
import each other by full submodule path.
"""

from __future__ import annotations

from .schemas import Answer, ChatMessage, Citation

__all__ = ["Answer", "ChatMessage", "Citation"]
