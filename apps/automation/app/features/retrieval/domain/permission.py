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
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PrincipalPermissionPolicy:
    space_of: dict[int, int] = field(default_factory=dict)
    # page_id -> set of principals allowed to read; missing/empty means unrestricted
    restrictions: dict[int, set[str]] = field(default_factory=dict)

    def space_id(self, scope: str | None) -> int | None:
        if scope is not None and scope.isdigit():
            return int(scope)
        return None

    def allowed(self, page_id: int, scope: str | None) -> bool:
        principals = self.restrictions.get(page_id)
        if scope is None:
            return not principals  # no identity -> only unrestricted pages
        if scope.isdigit():
            return self.space_of.get(page_id) == int(scope)  # space-level trust
        return (not principals) or (scope in principals)
