"""Resolve a request-shaped knowledge-scope value into the allowed-scopes set. Pure, no I/O.

ADR-routing-labels-sole-content-axis retired the knowledge-scope axis, so `recognized` is normally empty and this resolver
returns an empty list (no base scope, no `-test` tag). It is kept as the interpreter of an incoming
request-shaped value so the router keeps a single place to normalise/degrade one; a recognized
`requested` or `default` scope (if any are ever reintroduced) is still honoured.
"""

from __future__ import annotations


def resolve_allowed_scopes(
    requested: str | None, recognized: frozenset[str], default: str | None
) -> list[str]:
    """Return the recognized subset of ``requested`` (else ``default``), or ``[]``. An unrecognized
    value degrades silently rather than failing the chat — a stale/misconfigured embed should not
    break it. With the axis retired, ``recognized`` is empty and this returns ``[]``.
    """
    scopes: set[str] = set()
    if requested and requested.lower() in recognized:
        scopes.add(requested.lower())
    elif default and default.lower() in recognized:
        scopes.add(default.lower())
    return sorted(scopes)
