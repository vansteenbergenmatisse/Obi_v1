"""Retrieval feature: hybrid (dense + keyword) search with permission filtering.

Public surface. Only the two symbols that cross the boundary are exported:
`HybridRetriever` (the entry point) and `PrincipalPermissionPolicy` (the policy
callers construct). Fusion and the low-level search functions stay internal
until a real external consumer needs them (the Phase 4 agent).

Status: not yet wired into `app.main`; exercised today only by the evaluation
integration test. Internal modules import each other by full submodule path,
never through this root.

Internal rule: modules inside this feature MUST NOT import through this root
(`from app.features.retrieval import X`) — that raises ImportError during init.
"""

from __future__ import annotations

from .application.retriever import HybridRetriever
from .domain.permission import PrincipalPermissionPolicy

__all__ = ["HybridRetriever", "PrincipalPermissionPolicy"]
