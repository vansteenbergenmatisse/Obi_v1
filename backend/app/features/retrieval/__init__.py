"""Retrieval feature: hybrid (dense + keyword) search with permission filtering.

Public surface: `HybridRetriever` (the entry point), `PrincipalPermissionPolicy` (the policy
callers construct), the `RetrievedHit`/`RetrievalResult` DTOs `retrieve_with_context` returns
(the Phase 4.2 answer workflow's real external consumer), the `query_trace` answer/feedback
writers Phase 4 UPDATEs with once an answer is grounded, and `apply_knowledge_scope` (a no-op
wildcard GUC setter kept only because the migration-0018 downgrade re-applies policies that read
it).
Since substep 8.2.3 it also exposes the deterministic applicability matcher (panel mi-match):
`match_applicability`/`derive_connections` with their `CustomerContext`/`ConnectionRecord`/
`MatchResult` types — the pure §D.4 predicate 8.3.1 mirrors in SQL and 8.3.4 reads reasons from.
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
from .domain.applicability_match import (
    AttributionValue,
    ConnectionRecord,
    CustomerContext,
    EligibilityParams,
    MatchResult,
    attribution_for_reason,
    derive_connections,
    eligibility_params,
    match_applicability,
)
from .domain.permission import PrincipalPermissionPolicy, classify_scope
from .infrastructure.search_repo import apply_knowledge_scope
from .infrastructure.trace_repo import update_query_trace_answer, update_query_trace_feedback

__all__ = [
    "AttributionValue",
    "ConnectionRecord",
    "CustomerContext",
    "EligibilityParams",
    "HybridRetriever",
    "MatchResult",
    "PrincipalPermissionPolicy",
    "RetrievedHit",
    "RetrievalResult",
    "apply_knowledge_scope",
    "attribution_for_reason",
    "classify_scope",
    "derive_connections",
    "eligibility_params",
    "match_applicability",
    "update_query_trace_answer",
    "update_query_trace_feedback",
]
