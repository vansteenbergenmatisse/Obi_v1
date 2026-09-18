"""Regression test for panel tg-change ("Change a label"), substep 0.5.2.

An editor swaps one recognized label for another on an already-indexed page (Confluence sends
label_deleted then label_added, no body change). The worker reads the current label set fresh
on every sync (`resolve_knowledge_scope_tags` in `handle_sync_page`), so the page's tags must
converge to exactly the new tag with the old one gone -- never both at once -- and this is a
metadata-only change: no rebuild (the active document_version does not change). The panel's
steps name two equivalent delivery shapes -- coalesced (both events land in one pending job,
covered below by `test_tg_change_label_swap_leaves_no_stale_double_tag`) and uncoalesced (two
distinct jobs, one per event, run in order, covered below by
`test_tg_change_sequential_label_jobs_converge_without_double_tag`) -- because the idempotency
key for a sync_page job includes the event_type (`event_service._enqueue_for_event`), so
label_deleted and label_added always get distinct keys and never dedupe into one job at enqueue
time; both paths are exercised here since they run different code (one job vs. two through the
queue) even though both are expected to converge on the same result.

Not duplicated here: `test_knowledge_scope.py` covers `resolve_knowledge_scope_tags` in isolation;
`test_scope_resolver.py` covers folder/space roots; `test_knowledge_scope_backfill.py` covers an
already-tagged corpus. This file is the only one exercising the real sync path for a label swap.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once
from app.platform.db.engine import session_scope
from app.platform.db.models import PageSource
from app.platform.jobs import enqueue_job

from ._helpers import active_version, enqueue_sync, index_page, read, run_worker

pytestmark = pytest.mark.db


def test_tg_change_label_swap_leaves_no_stale_double_tag(gateway, settings):
    """panel tg-change · substep 0.5.2
    A label swap (mews -> toast) converges to exactly the new tag, with the old tag gone and
    no rebuild (same active document_version)."""
    gateway.set_labels(1001, ["obi-mews-test"])
    index_page(gateway, settings, 1001, version=1)

    with read() as s:
        page_source = s.get(PageSource, 1001)
        assert page_source is not None
        assert page_source.tags == ["obi-mews-test"]
    version_before_row = active_version(1001)
    assert version_before_row is not None
    version_before = version_before_row.id

    gateway.set_labels(1001, ["obi-toast-test"])  # label swap; same page content, no version bump
    enqueue_sync(1001, 1, key="sync:1001:label-swap")
    result = run_once(gateway, settings, owner="test")

    assert result is not None
    outcome = result.outcome
    assert isinstance(outcome, SyncOutcome)
    assert outcome.action == "metadata_only"
    with read() as s:
        page_source = s.get(PageSource, 1001)
        assert page_source is not None
        assert page_source.tags == ["obi-toast-test"]  # old tag gone, no double-tag
    version_after_row = active_version(1001)
    assert version_after_row is not None
    assert version_after_row.id == version_before  # metadata-only: no rebuild


def test_tg_change_sequential_label_jobs_converge_without_double_tag(gateway, settings):
    """panel tg-change · substep 0.5.2
    Without coalescing, label_deleted and label_added arrive as two separate sync_page jobs
    (distinct idempotency keys, per `event_service._enqueue_for_event`) instead of one. Run in
    order through the real queue (`drain`), the worker re-reads the current label set on each
    job, so the result is the same as the coalesced path: tags converge to exactly the new tag,
    the old one is gone, no double-tag, and neither job triggers a rebuild. The first job (whose
    fresh read of the gateway already reflects the swap) does the metadata update; the second is
    a redundant idempotent no-op against the now-already-converged state -- both are non-rebuild
    outcomes (`sync_service.py`'s `_REBUILD_CLASSES` never fires for a labels-only change)."""
    gateway.set_labels(1001, ["obi-mews-test"])
    index_page(gateway, settings, 1001, version=1)

    with read() as s:
        page_source = s.get(PageSource, 1001)
        assert page_source is not None
        assert page_source.tags == ["obi-mews-test"]
    version_before_row = active_version(1001)
    assert version_before_row is not None
    version_before = version_before_row.id

    # label swap; same page content, no version bump
    gateway.set_labels(1001, ["obi-toast-test"])

    # Two separate deliveries -> two separate jobs (as event_service would enqueue for
    # label_deleted then label_added), both immediately available. `claim_job` orders by
    # (priority, available_at), so a lower priority on the first-delivered event forces
    # deterministic in-order claiming without depending on wall-clock timing between inserts.
    now = datetime.now(UTC)
    with session_scope() as s:
        enqueue_job(
            s,
            job_type="sync_page",
            idempotency_key="sync_page:1001:label_deleted:1:v1",
            payload={"event_type": "label_deleted"},
            page_id=1001,
            cf_version=1,
            priority=90,
            available_at=now,
        )
        enqueue_job(
            s,
            job_type="sync_page",
            idempotency_key="sync_page:1001:label_added:1:v1",
            payload={"event_type": "label_added"},
            page_id=1001,
            cf_version=1,
            priority=100,
            available_at=now,
        )

    results = run_worker(gateway, settings, owner="test")

    assert len(results) == 2  # both jobs ran, in order -- no coalescing at the queue
    first_outcome, second_outcome = (r.outcome for r in results)
    assert results[0].status == "succeeded"
    assert results[1].status == "succeeded"
    assert isinstance(first_outcome, SyncOutcome)
    assert isinstance(second_outcome, SyncOutcome)
    assert first_outcome.action == "metadata_only"  # the label_deleted job applies the tag swap
    # the label_added job runs second against an already-converged page: idempotent no-op, never
    # a rebuild and never a second metadata write that could re-introduce the old tag.
    assert second_outcome.action == "no_change"

    with read() as s:
        page_source = s.get(PageSource, 1001)
        assert page_source is not None
        assert page_source.tags == ["obi-toast-test"]  # converged: old tag gone, no double-tag
    version_after_row = active_version(1001)
    assert version_after_row is not None
    assert version_after_row.id == version_before  # metadata-only: no rebuild
