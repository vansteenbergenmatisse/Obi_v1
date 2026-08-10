"""Reconciliation: complete sweep deactivates orphans + finds new pages; lightweight sweep
enqueues drift that the worker then repairs."""

from __future__ import annotations

from app.features.confluence_sync.application.reconciliation import (
    KIND_COMPLETE,
    KIND_LIGHTWEIGHT,
    run_reconciliation,
)
from app.platform.db.engine import session_scope
from app.platform.db.models import PageSource, SourceScope

from ._helpers import (
    active_child_chunks,
    active_version,
    index_page,
    run_worker,
)


def _add_scope_root(root_type: str, root_id: str, *, tags: list[str] | None = None) -> int:
    with session_scope() as s:
        row = SourceScope(root_type=root_type, root_id=root_id, tags=tags or [])
        s.add(row)
        s.flush()
        return row.id


def _deactivate_scope_root(root_id: int) -> None:
    with session_scope() as s:
        row = s.get(SourceScope, root_id)
        assert row is not None
        row.is_active = False


def test_complete_reconcile_deactivates_orphan_and_enqueues_new(gateway, settings):
    index_page(gateway, settings, 1001, version=3)  # now tracked in space 100
    assert active_child_chunks(1001)

    gateway.hide(1001)  # page vanished from source → orphan in the registry

    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_COMPLETE, space_ids=[100]
        )
        orphans_deleted = run.orphans_deleted
        jobs_enqueued = run.jobs_enqueued

    assert orphans_deleted == 1  # 1001 deactivated
    assert jobs_enqueued >= 1  # 1002 (live, unindexed) enqueued for sync
    assert active_child_chunks(1001) == []


def test_lightweight_reconcile_repairs_version_drift(gateway, settings):
    index_page(gateway, settings, 1001, version=1)
    assert active_version(1001).cf_version == 1

    gateway.set_version(1001, 3)  # source advanced, event was missed

    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_LIGHTWEIGHT, space_ids=[100]
        )
        assert run.drift_detected >= 1
        assert run.jobs_enqueued >= 1

    run_worker(gateway, settings)  # drain the enqueued sync jobs
    assert active_version(1001).cf_version == 3


def test_page_root_scopes_reconciliation_to_its_subtree_and_tags_it(gateway, settings):
    """PLAN 3.5.6: a page-type source_scope root syncs only its subtree, tags what it syncs,
    and — since nothing was ever indexed for space 100 before this — proves a brand-new space
    gets its first sweep from scope-implied discovery alone (no explicit space_ids, no prior
    page_source rows)."""
    _add_scope_root("page", "1002", tags=["eng"])  # 1002's only live child is itself (no
    # current descendants in the fixture); 1001 is its parent, in the same space, out of scope.

    with session_scope() as s:
        run = run_reconciliation(s, gateway=gateway, settings=settings, kind=KIND_COMPLETE)
        assert run.jobs_enqueued >= 1

    run_worker(gateway, settings)

    with session_scope() as s:
        assert s.get(PageSource, 1002) is not None  # in scope: synced
        assert s.get(PageSource, 1001) is None  # out of scope: never touched

    assert active_child_chunks(1001) == []
    chunks = active_child_chunks(1002)
    assert chunks
    assert all(c.tags == ["eng"] for c in chunks)
    with session_scope() as s:
        ps = s.get(PageSource, 1002)
        assert ps is not None
        assert ps.tags == ["eng"]


def test_deactivating_root_purges_previously_synced_now_uncovered_pages(gateway, settings):
    """PLAN 3.5.6: removing coverage purges via the same deactivate_page path as an
    upstream deletion — regardless of whether the page still exists on Confluence."""
    root_id = _add_scope_root("page", "1001", tags=["eng"])  # covers {1001, 1002}

    with session_scope() as s:
        run_reconciliation(s, gateway=gateway, settings=settings, kind=KIND_COMPLETE)
    run_worker(gateway, settings)
    assert active_child_chunks(1001) and active_child_chunks(1002)

    _deactivate_scope_root(root_id)

    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_COMPLETE, space_ids=[100]
        )
        assert run.orphans_deleted == 2  # both 1001 and 1002 purged; root covers nothing now

    assert active_child_chunks(1001) == []
    assert active_child_chunks(1002) == []
