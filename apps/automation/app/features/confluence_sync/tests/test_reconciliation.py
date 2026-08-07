"""Reconciliation: complete sweep deactivates orphans + finds new pages; lightweight sweep
enqueues drift that the worker then repairs."""

from __future__ import annotations

from app.features.confluence_sync.application.reconciliation import (
    KIND_COMPLETE,
    KIND_LIGHTWEIGHT,
    run_reconciliation,
)
from app.platform.db.engine import session_scope

from ._helpers import (
    active_child_chunks,
    active_version,
    index_page,
    run_worker,
)


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
