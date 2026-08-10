"""Confluence sync feature: webhook ingress, job queue/worker, and reconciliation.

Public surface. `app.main` and any other external code wire this feature through
`app.features.confluence_sync` — never through a deeper module. Composes the
`server` sub-facade (router, SlidingWindowRateLimiter) with the worker and
reconciliation operations.

Internal rule: modules inside this feature MUST NOT import through this root
(`from app.features.confluence_sync import X`) — that raises ImportError during
init. In particular worker.py keeps its function-local deep import of
reconciliation (the worker<->reconciliation cycle-breaker); do not hoist it.
"""

from __future__ import annotations

from .application.reconciliation import (
    KIND_COMPLETE,
    KIND_LIGHTWEIGHT,
    run_reconciliation,
)
from .application.worker import drain, reap
from .domain.scope_resolver import (
    ROOT_TYPE_PAGE,
    ROOT_TYPE_SPACE,
    ScopeResolution,
    resolve_scope_roots,
    resolve_space_scope,
)
from .server import SlidingWindowRateLimiter, router

__all__ = [
    "KIND_COMPLETE",
    "KIND_LIGHTWEIGHT",
    "ROOT_TYPE_PAGE",
    "ROOT_TYPE_SPACE",
    "ScopeResolution",
    "SlidingWindowRateLimiter",
    "drain",
    "reap",
    "resolve_scope_roots",
    "resolve_space_scope",
    "router",
    "run_reconciliation",
]
