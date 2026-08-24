"""Confluence sync feature: webhook ingress, job queue/worker, and reconciliation.

Public surface. `app.main` and any other external code wire this feature through
`app.features.confluence_sync` — never through a deeper module. Composes the
`server` sub-facade (router) with the worker and reconciliation operations. The
generic `SlidingWindowRateLimiter` this feature's webhook uses now lives in
`app.shared.rate_limiter` (PLAN 4.4) — it has a second consumer (the chat endpoint)
and no feature-specific behavior, so it moved out of this feature's public surface.

Internal rule: modules inside this feature MUST NOT import through this root
(`from app.features.confluence_sync import X`) — that raises ImportError during
init. In particular worker.py keeps its function-local deep import of
reconciliation (the worker<->reconciliation cycle-breaker); do not hoist it.
"""

from __future__ import annotations

from .application.knowledge_scope_backfill import (
    KnowledgeScopeCoverage,
    verify_knowledge_scope_coverage,
)
from .application.reconciliation import (
    KIND_COMPLETE,
    KIND_LIGHTWEIGHT,
    run_reconciliation,
)
from .application.worker import drain, reap
from .domain.knowledge_scope import KnowledgeScopeResult, resolve_knowledge_scope_tags
from .domain.scope_resolver import (
    ROOT_TYPE_PAGE,
    ROOT_TYPE_SPACE,
    ScopeResolution,
    resolve_scope_roots,
    resolve_space_scope,
)
from .server import router

__all__ = [
    "KIND_COMPLETE",
    "KIND_LIGHTWEIGHT",
    "KnowledgeScopeCoverage",
    "KnowledgeScopeResult",
    "ROOT_TYPE_PAGE",
    "ROOT_TYPE_SPACE",
    "ScopeResolution",
    "drain",
    "reap",
    "resolve_knowledge_scope_tags",
    "resolve_scope_roots",
    "resolve_space_scope",
    "router",
    "run_reconciliation",
    "verify_knowledge_scope_coverage",
]
