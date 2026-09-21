"""Access-scope permission policy (pure, data-driven).

Decides whether a caller scope may see a page, and derives the space filter from a scope. Two
scope kinds:

* **space scope** (numeric, e.g. ``"100"``) — space-level trust: every page in that space is
  visible (this is how the retrieval smoke set is scoped).
* **principal scope** (e.g. ``"acct-alice"``) — a page is visible only if it is unrestricted or
  the principal is in its read-restriction set. This is what stops cross-scope leaks.

The policy is fed plain data (space-of-page, restrictions-of-page) so it stays framework-free and
testable; callers build it from whatever ACL source they have. In production, ``HybridRetriever``
(PLAN 4.3) builds a fresh instance per search from ``page_source``/``page_restriction`` via
``search_repo.fetch_page_scopes``; tests still build one directly from fixture data.

PLAN 4.6.6: a raw caller ``scope`` string used to be reinterpreted as space-vs-principal trust in
two different places (``space_id()`` and ``allowed()``, both via ``.isdigit()``) — the exact
duplication that let the 5.3 numeric-principal bypass slip through one caller
(``ChatRequestBody.principal``) while the domain layer stayed silently able to reproduce the same
bug for any *other* caller. ``classify_scope`` now does that classification exactly once, at the
boundary; ``allowed()`` takes the already-classified ``space_id``/``principal`` pair and never
re-derives trust from string shape again.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def classify_scope(scope: str | None) -> tuple[int | None, str | None]:
    """Classify a raw caller scope exactly once. An all-digit string is space-level trust
    (returns ``(space_id, None)``); anything else — including ``None`` — is a principal identity
    (returns ``(None, principal)``). Callers must classify at the boundary and pass the explicit
    pair onward; nothing downstream re-derives trust kind from string shape."""
    if scope is not None and scope.isdigit():
        return int(scope), None
    return None, scope


@dataclass
class PrincipalPermissionPolicy:
    space_of: dict[int, int] = field(default_factory=dict)
    # page_id -> set of principals allowed to read; missing/empty means unrestricted
    restrictions: dict[int, set[str]] = field(default_factory=dict)

    def allowed(self, page_id: int, *, space_id: int | None, principal: str | None) -> bool:
        principals = self.restrictions.get(page_id)
        if space_id is not None:
            return self.space_of.get(page_id) == space_id  # space-level trust
        if principal is None:
            return not principals  # no identity -> only unrestricted pages
        return (not principals) or (principal in principals)
