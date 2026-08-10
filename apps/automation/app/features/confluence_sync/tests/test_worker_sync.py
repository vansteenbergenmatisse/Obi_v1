"""Worker + sync-service guarantees: first index, atomic re-index, version guard, metadata-only,
delete/deactivate."""

from __future__ import annotations

from app.features.confluence_sync.application.worker import run_once
from app.platform.db.enums import PageStatus
from app.platform.db.models import PageSource

from ._helpers import (
    active_child_chunks,
    active_version,
    active_versions_count,
    count_versions,
    enqueue_delete,
    enqueue_sync,
    index_page,
    read,
    restricted_principals,
)


def test_first_index_creates_active_version_and_chunks(gateway, settings):
    index_page(gateway, settings, 1001, version=3)

    av = active_version(1001)
    assert av is not None
    assert av.cf_version == 3
    assert active_versions_count(1001) == 1
    chunks = active_child_chunks(1001)
    assert len(chunks) > 0
    with read() as s:
        assert s.get(PageSource, 1001) is not None


def test_content_change_swaps_version_atomically(gateway, settings):
    index_page(gateway, settings, 1001, version=1)
    assert active_version(1001).cf_version == 1
    assert count_versions(1001) == 1

    gateway.set_version(1001, 3)
    enqueue_sync(1001, 3, key="sync:1001:v3")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and result.status == "succeeded"
    assert result.outcome.action == "indexed"
    assert active_version(1001).cf_version == 3
    assert count_versions(1001) == 2  # old retained for rollback
    assert active_versions_count(1001) == 1  # exactly one active — no mixed versions
    # every active child chunk belongs to the new active version
    new_id = active_version(1001).id
    assert {c.doc_version_id for c in active_child_chunks(1001)} == {new_id}


def test_version_guard_drops_stale_update(gateway, settings):
    index_page(gateway, settings, 1001, version=3)
    assert count_versions(1001) == 1

    # a delayed/out-of-order delivery carrying an older version; source is still at v3
    enqueue_sync(1001, 2, key="sync:1001:stale-v2")
    result = run_once(gateway, settings, owner="test")

    assert result.status == "succeeded"
    assert result.outcome.action == "no_change"
    assert count_versions(1001) == 1  # no downgrade, no new version


def test_first_index_persists_restrictions(gateway, settings):
    """PLAN 4.3: the real principal list, not just its hash, lands in page_restriction."""
    index_page(gateway, settings, 2002, version=1)
    assert restricted_principals(2002) == {"acct-carol"}  # fixture: page-2002.json


def test_permission_change_is_metadata_only(gateway, settings):
    index_page(gateway, settings, 2002, version=1)
    before = active_child_chunks(2002)
    assert before, "expected active chunks after first index"
    scope_before = before[0].access_scope
    assert restricted_principals(2002) == {"acct-carol"}

    gateway.set_restrictions(2002, ["acct-brand-new-person"])  # no version bump
    enqueue_sync(2002, 1, key="sync:2002:perm")
    result = run_once(gateway, settings, owner="test")

    assert result.outcome.action == "metadata_only"
    assert count_versions(2002) == 1  # NO re-embed / new version
    after = active_child_chunks(2002)
    assert after and after[0].access_scope != scope_before  # scope propagated to chunks
    # PLAN 4.3: the persisted ACL is a full replace, not an append — the old principal is gone
    assert restricted_principals(2002) == {"acct-brand-new-person"}


def test_dropped_restriction_leaves_page_unrestricted(gateway, settings):
    """PLAN 4.3: clearing a page's restrictions removes its page_restriction rows entirely."""
    index_page(gateway, settings, 2002, version=1)
    assert restricted_principals(2002)  # starts restricted

    gateway.set_restrictions(2002, [])  # no version bump
    enqueue_sync(2002, 1, key="sync:2002:perm-cleared")
    result = run_once(gateway, settings, owner="test")

    assert result.outcome.action == "metadata_only"
    assert restricted_principals(2002) == set()  # unrestricted now (no rows, not empty-set rows)


def test_delete_deactivates_page(gateway, settings):
    index_page(gateway, settings, 1001, version=3)
    assert active_child_chunks(1001)

    enqueue_delete(1001, "trashed", key="del:1001")
    result = run_once(gateway, settings, owner="test")

    assert result.outcome.action == "deactivated"
    assert active_child_chunks(1001) == []
    with read() as s:
        assert s.get(PageSource, 1001).page_status == PageStatus.trashed
