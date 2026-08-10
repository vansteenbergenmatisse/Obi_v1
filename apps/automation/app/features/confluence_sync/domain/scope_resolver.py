"""Pure resolution of ``source_scope`` roots against a live page listing (PLAN 3.5.6).

No network calls: everything here walks ``ConfluencePageMeta.parent_id`` chains over a
``list_space_pages()`` result the caller already fetched. Confluence-specific I/O (fetching
that listing, or looking up a ``page``-root's space via ``get_page_meta``) stays in
``application/reconciliation.py`` — this module only does the tree-walk + set/tag math.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.platform.clients import ConfluencePageMeta
from app.platform.db.models import SourceScope

ROOT_TYPE_SPACE = "space"
ROOT_TYPE_PAGE = "page"


def resolve_scope_roots(
    live_pages: list[ConfluencePageMeta], roots: list[SourceScope]
) -> dict[int, set[int]]:
    """Map each root's ``id`` -> the set of live page ids it covers.

    - a ``space`` root covers every page in ``live_pages`` (today's whole-space behavior,
      unchanged).
    - a ``page`` root covers itself + every descendant reachable by walking ``parent_id`` over
      ``live_pages`` — never a sibling, never an ancestor. A root whose page id is not (or no
      longer) in ``live_pages`` resolves to the empty set.

    Overlapping roots (nested ``page`` roots, or a ``page`` root inside an already-covered
    ``space`` root) resolve independently; callers union coverage across roots.
    """
    live_ids = {m.page_id for m in live_pages}
    children_of: dict[int, list[int]] = {}
    for m in live_pages:
        if m.parent_id is not None:
            children_of.setdefault(m.parent_id, []).append(m.page_id)

    resolved: dict[int, set[int]] = {}
    for root in roots:
        if root.root_type == ROOT_TYPE_SPACE:
            resolved[root.id] = set(live_ids)
            continue
        root_page_id = int(root.root_id)
        covered: set[int] = set()
        stack = [root_page_id] if root_page_id in live_ids else []
        while stack:
            pid = stack.pop()
            if pid in covered:
                continue
            covered.add(pid)
            stack.extend(children_of.get(pid, []))
        resolved[root.id] = covered
    return resolved


@dataclass(frozen=True)
class ScopeResolution:
    """``allowed_page_ids=None`` means unrestricted — today's whole-space behavior."""

    allowed_page_ids: set[int] | None
    tags_by_page: dict[int, list[str]]


def resolve_space_scope(
    live_pages: list[ConfluencePageMeta], all_roots: list[SourceScope]
) -> ScopeResolution:
    """Combine every ``source_scope`` row recorded for one space into an allow-set + tags.

    ``all_roots`` is every row for this space, active *or not* — that distinction matters:

    - **Zero rows ever recorded** -> unrestricted, no tags (byte-for-byte today's behavior;
      the common case until a root is seeded for this space at all).
    - **Rows exist, but none are active** -> restricted to the empty set. This is how
      deactivating (or removing) the last root for a space fully purges it, rather than
      silently reverting to "sync everything" — coverage is never implicit once a space has
      been deliberately scoped.
    - Otherwise -> the union of every *active* root's resolved coverage (a ``space`` root's
      resolved set is every live page, so its presence alone yields full coverage). Tags union
      when more than one active root covers the same page.
    """
    if not all_roots:
        return ScopeResolution(allowed_page_ids=None, tags_by_page={})

    active_roots = [r for r in all_roots if r.is_active]
    resolved = resolve_scope_roots(live_pages, active_roots)

    allowed: set[int] = set()
    tags_by_page: dict[int, set[str]] = {}
    for root in active_roots:
        covered = resolved.get(root.id, set())
        allowed |= covered
        for pid in covered:
            tags_by_page.setdefault(pid, set()).update(root.tags)

    return ScopeResolution(
        allowed_page_ids=allowed,
        tags_by_page={pid: sorted(tags) for pid, tags in tags_by_page.items() if tags},
    )
