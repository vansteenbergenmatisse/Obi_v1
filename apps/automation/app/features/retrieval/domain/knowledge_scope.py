"""Resolve a request-shaped knowledge-scope value into the allowed-scopes set (PLAN 10.4,
ADR-0011). Pure, no I/O — co-located with `permission.classify_scope`, which already plays this
"interpret an incoming request-shaped value" role for `principal`.
"""

from __future__ import annotations


def resolve_allowed_scopes(
    requested: str | None, recognized: frozenset[str], default: str | None
) -> list[str]:
    """``obi-general-test`` is always allowed (ADR-0011 Decision 1 — always-included, never
    inferred from an untagged chunk). A recognized ``requested`` scope is added; an unrecognized
    one degrades silently to the deployment ``default`` (if that is itself recognized), never a
    hard failure — a stale/misconfigured embed should not break chat entirely. The caller logs
    the degradation.
    """
    scopes = {"obi-general-test"}
    if requested and requested.lower() in recognized:
        scopes.add(requested.lower())
    elif default and default.lower() in recognized:
        scopes.add(default.lower())
    return sorted(scopes)
