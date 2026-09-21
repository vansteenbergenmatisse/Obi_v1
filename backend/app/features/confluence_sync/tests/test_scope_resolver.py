"""Pure unit tests for the source_scope resolver (PLAN 3.5.6) — no DB, no gateway."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.features.confluence_sync.domain.scope_resolver import (
    resolve_scope_roots,
    resolve_space_scope,
)
from app.platform.clients import ConfluencePageMeta
from schema.models import SourceScope

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest


def _meta(page_id: int, parent_id: int | None) -> ConfluencePageMeta:
    return ConfluencePageMeta(
        page_id=page_id,
        space_id=100,
        parent_id=parent_id,
        title=f"page-{page_id}",
        status="current",
        version_number=1,
        version_created_at=datetime.now().astimezone(),
        source_url=f"https://example/{page_id}",
    )


def _root(
    root_id: int,
    root_type: str,
    page_or_space_id: str,
    tags: list[str] | None = None,
    is_active: bool = True,
):
    return SourceScope(
        id=root_id,
        root_type=root_type,
        root_id=page_or_space_id,
        tags=tags or [],
        is_active=is_active,
    )


# root(10) -> child(11) -> grandchild(12); sibling(13) is not under root; other(14) is unrelated
ROOT = _meta(10, parent_id=None)
CHILD = _meta(11, parent_id=10)
GRANDCHILD = _meta(12, parent_id=11)
SIBLING = _meta(13, parent_id=None)
OTHER = _meta(14, parent_id=99)
LIVE = [ROOT, CHILD, GRANDCHILD, SIBLING, OTHER]


def test_page_root_resolves_to_self_and_descendants_only():
    root = _root(1, "page", "10")
    resolved = resolve_scope_roots(LIVE, [root])
    assert resolved[1] == {10, 11, 12}


def test_page_root_never_includes_siblings_or_ancestors():
    root = _root(1, "page", "11")  # rooted at the child, not the top
    resolved = resolve_scope_roots(LIVE, [root])
    assert resolved[1] == {11, 12}
    assert 10 not in resolved[1]  # ancestor excluded
    assert 13 not in resolved[1]  # sibling excluded


def test_space_root_resolves_to_every_live_page():
    root = _root(1, "space", "100")
    resolved = resolve_scope_roots(LIVE, [root])
    assert resolved[1] == {10, 11, 12, 13, 14}


def test_page_root_missing_from_live_listing_resolves_to_empty():
    root = _root(1, "page", "999")
    resolved = resolve_scope_roots(LIVE, [root])
    assert resolved[1] == set()


def test_overlapping_page_roots_resolve_independently():
    a = _root(1, "page", "10")
    b = _root(2, "page", "11")
    resolved = resolve_scope_roots(LIVE, [a, b])
    assert resolved[1] == {10, 11, 12}
    assert resolved[2] == {11, 12}  # overlaps with root 1's subtree; each stands on its own


def test_no_roots_is_unrestricted_and_untagged():
    scope = resolve_space_scope(LIVE, [])
    assert scope.allowed_page_ids is None
    assert scope.tags_by_page == {}


def test_only_page_roots_restricts_to_their_union():
    a = _root(1, "page", "10", tags=["eng"])
    scope = resolve_space_scope(LIVE, [a])
    assert scope.allowed_page_ids is not None
    assert scope.allowed_page_ids == {10, 11, 12}
    assert 13 not in scope.allowed_page_ids
    assert scope.tags_by_page == {10: ["eng"], 11: ["eng"], 12: ["eng"]}


def test_overlapping_roots_union_tags_on_shared_pages():
    a = _root(1, "page", "10", tags=["eng"])
    b = _root(2, "page", "11", tags=["support-bot"])
    scope = resolve_space_scope(LIVE, [a, b])
    assert scope.allowed_page_ids == {10, 11, 12}
    assert scope.tags_by_page[10] == ["eng"]
    assert scope.tags_by_page[11] == ["eng", "support-bot"]
    assert scope.tags_by_page[12] == ["eng", "support-bot"]


def test_space_root_present_covers_everything_even_with_page_roots_on_top():
    space_root = _root(1, "space", "100", tags=["all"])
    page_root = _root(2, "page", "10", tags=["eng"])
    scope = resolve_space_scope(LIVE, [space_root, page_root])
    # a space root's resolved set is every live page, so coverage is full (equivalent in
    # effect to the "None = unrestricted" case, just expressed as an explicit set once any
    # source_scope row exists — see resolve_space_scope's docstring on the None/rows-exist split)
    assert scope.allowed_page_ids == {10, 11, 12, 13, 14}
    assert scope.tags_by_page[10] == ["all", "eng"]  # union: covered by both roots
    assert scope.tags_by_page[13] == ["all"]  # only the space root covers this one


def test_page_outside_every_root_resolves_to_nothing():
    a = _root(1, "page", "10")
    scope = resolve_space_scope(LIVE, [a])
    assert scope.allowed_page_ids is not None
    assert 14 not in scope.allowed_page_ids
    assert 14 not in scope.tags_by_page


def test_deactivating_the_last_root_purges_rather_than_reverting_to_unrestricted():
    a = _root(1, "page", "10", is_active=False)
    scope = resolve_space_scope(LIVE, [a])
    assert scope.allowed_page_ids == set()  # restricted to nothing, NOT None/unrestricted
    assert scope.tags_by_page == {}


def test_inactive_roots_do_not_contribute_coverage_or_tags_alongside_active_ones():
    active = _root(1, "page", "10", tags=["eng"], is_active=True)
    inactive = _root(2, "page", "13", tags=["stale"], is_active=False)
    scope = resolve_space_scope(LIVE, [active, inactive])
    assert scope.allowed_page_ids is not None
    assert scope.allowed_page_ids == {10, 11, 12}
    assert 13 not in scope.allowed_page_ids
    assert scope.tags_by_page == {10: ["eng"], 11: ["eng"], 12: ["eng"]}
