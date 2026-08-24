"""Retrieval feature: hybrid (dense + keyword) search with permission filtering.

Public surface: `HybridRetriever` (the entry point), `PrincipalPermissionPolicy` (the policy
callers construct), the `RetrievedHit`/`RetrievalResult` DTOs `retrieve_with_context` returns
(the Phase 4.2 answer workflow's real external consumer), the `query_trace` answer/feedback
writers Phase 4 UPDATEs with once an answer is grounded, and `resolve_allowed_scopes` (PLAN 10.4)
which `rag_agent` will call once a chat request carries a `knowledge_scope` field (PLAN 10.5).
Fusion and the low-level search functions stay internal — no consumer needs them directly.

Status: wired into `app.main` transitively — `rag_agent`'s router is the mounted HTTP surface and
this feature's only production consumer (since Phase 4.2); also exercised directly by the
evaluation integration test. Internal modules import each other by full submodule path, never
through this root.

Internal rule: modules inside this feature MUST NOT import through this root
(`from app.features.retrieval import X`) — that raises ImportError during init.
"""

from __future__ import annotations

from .application.retriever import HybridRetriever, RetrievalResult, RetrievedHit
from .domain.knowledge_scope import resolve_allowed_scopes
from .domain.permission import PrincipalPermissionPolicy, classify_scope
from .infrastructure.trace_repo import update_query_trace_answer, update_query_trace_feedback

__all__ = [
    "HybridRetriever",
    "PrincipalPermissionPolicy",
    "RetrievedHit",
    "RetrievalResult",
    "classify_scope",
    "resolve_allowed_scopes",
    "update_query_trace_answer",
    "update_query_trace_feedback",
]
