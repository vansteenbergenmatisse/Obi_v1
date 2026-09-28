"""The full re-index job (2.0.3): one job rebuilds every tagged page in resumable batches with a
progress counter on the reconciliation row.

Protects design panels **i1-sweep** (a pipeline-stamp change reaches every tagged page via one
job instead of waiting for the daily sweep) and **i2-classify** (the enqueued sync_page work is
version/config classified — a stamp bump rebuilds, an unchanged page is a no_change no-op).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.features.confluence_sync.application.reindex import (
    KIND_REINDEX,
    run_reindex,
)
from schema.engine import session_scope
from schema.enums import ReconStatus
from schema.models import Job, PageSource, ReconciliationRun

from ._helpers import count_versions, enqueue_sync, index_page, run_worker

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres via this dir's conftest


def _reindex_jobs() -> list[Job]:
    """Every sync_page job the reindex orchestration enqueued (keyed `sync_page:reindex:...`)."""
    with session_scope() as s:
        return list(
            s.execute(select(Job).where(Job.idempotency_key.like("sync_page:reindex:%")))
            .scalars()
            .all()
        )


def _count_all_jobs() -> int:
    with session_scope() as s:
        return int(s.execute(select(func.count(Job.id))).scalar_one())


def test_reindex_batches_enqueue_every_tagged_page(gateway, settings):
    """panel i1-sweep · substep 2.0.3
    One reindex job enqueues a sync_page rebuild for every tagged page, across multiple batches;
    an untagged page is left alone."""
    # 3001..3004 carry a recognized knowledge-scope label → indexed with a tag.
    for pid in (3001, 3002, 3003, 3004):
        index_page(gateway, settings, pid, version=1)
    # 3005's labels (changelog/internal) are not recognized scopes → the 2.2.4 membership gate
    # never indexes it (no page_source row at all), so the reindex sweep can't touch it.
    gateway.set_version(3005, 1)
    enqueue_sync(3005, 1, key="seed-untagged:3005")
    run_worker(gateway, settings, owner="seed")

    with session_scope() as s:
        assert s.get(PageSource, 3005) is None  # control: unlabeled -> never indexed
        run = run_reindex(s, settings=settings, batch_size=2)  # 4 pages -> 2 batches
        assert run.kind == KIND_REINDEX
        assert run.status == ReconStatus.completed
        assert run.total_pages == 4
        assert run.pages_done == 4
        assert run.jobs_enqueued == 4
        assert run.cursor == 3004

    jobs = _reindex_jobs()
    assert {j.page_id for j in jobs} == {3001, 3002, 3003, 3004}  # 3005 excluded


def test_reindex_resume_after_crash_does_not_reenqueue_completed_pages(gateway, settings):
    """panel i1-sweep · substep 2.0.3
    A reindex interrupted after one batch resumes from the persisted cursor and enqueues each
    remaining page exactly once — a completed page is never re-enqueued."""
    for pid in (3001, 3002, 3003, 3004):
        index_page(gateway, settings, pid, version=1)

    # first invocation: one page, then "crash" (session commits, process stops).
    with session_scope() as s:
        run = run_reindex(s, settings=settings, batch_size=1, max_batches=1)
        run_id = run.id
        assert run.status == ReconStatus.running
        assert run.pages_done == 1
        assert run.cursor == 3001

    assert {j.page_id for j in _reindex_jobs()} == {3001}

    # restart: a fresh invocation resumes the same run from the cursor and finishes.
    with session_scope() as s:
        run = run_reindex(s, settings=settings, batch_size=1)
        assert run.id == run_id  # same run resumed, not a new one
        assert run.status == ReconStatus.completed
        assert run.pages_done == 4
        assert run.cursor == 3004

    jobs = _reindex_jobs()
    assert {j.page_id for j in jobs} == {3001, 3002, 3003, 3004}
    assert len(jobs) == 4  # exactly one per page — 3001 was not re-enqueued


def test_reindex_progress_counter_survives_a_restart(gateway, settings):
    """panel i1-sweep · substep 2.0.3
    The progress counter lives on the reconciliation_run row: after a crash it is re-read from
    the database (total_pages/pages_done/cursor persisted) and the run continues to completion."""
    for pid in (3001, 3002, 3003, 3004):
        index_page(gateway, settings, pid, version=1)

    with session_scope() as s:
        run = run_reindex(s, settings=settings, batch_size=1, max_batches=2)
        run_id = run.id

    # simulate a restart: read the row back from the DB in a brand-new session.
    with session_scope() as s:
        row = s.get(ReconciliationRun, run_id)
        assert row is not None
        assert row.kind == KIND_REINDEX
        assert row.status == ReconStatus.running
        assert row.total_pages == 4
        assert row.pages_done == 2  # two batches of one page each
        assert row.cursor == 3002

    with session_scope() as s:
        row = run_reindex(s, settings=settings, batch_size=1)
        assert row.id == run_id
        assert row.status == ReconStatus.completed
        assert row.pages_done == 4
        assert row.cursor == 3004


def test_reindex_stamp_bump_rebuilds_every_tagged_page_with_a_new_version(gateway, settings):
    """panel i2-classify · substep 2.0.3
    Bumping a pipeline stamp and running the reindex job rebuilds every tagged page with a new
    document_version — the config change routes each enqueued sync_page to a rebuild."""
    for pid in (3001, 3002, 3003, 3004):
        index_page(gateway, settings, pid, version=1)
        assert count_versions(pid) == 1

    bumped = settings.model_copy(
        update={"contextualization_version": settings.contextualization_version + 1}
    )
    with session_scope() as s:
        run = run_reindex(s, settings=bumped)
        assert run.jobs_enqueued == 4

    run_worker(gateway, bumped)  # drain the enqueued sync_page rebuilds under the new stamp

    for pid in (3001, 3002, 3003, 3004):
        assert count_versions(pid) == 1  # a fresh version per page; retain 0 GC's the old one


def test_reindex_second_run_is_a_noop(gateway, settings):
    """panel i2-classify · substep 2.0.3
    After a reindex completes at a stamp, running it again at the same stamp enqueues no new work
    — idempotent keys plus the completed run make the second run a no-op."""
    for pid in (3001, 3002):
        index_page(gateway, settings, pid, version=1)

    with session_scope() as s:
        run1 = run_reindex(s, settings=settings)
        run1_id = run1.id
        assert run1.jobs_enqueued == 2
    run_worker(gateway, settings)  # drain the enqueued jobs

    jobs_before = _count_all_jobs()
    versions_before = (count_versions(3001), count_versions(3002))

    with session_scope() as s:
        run2 = run_reindex(s, settings=settings)
        assert run2.id == run1_id  # same completed run, not a fresh sweep
        assert run2.status == ReconStatus.completed
    run_worker(gateway, settings)

    assert _count_all_jobs() == jobs_before  # no new jobs enqueued
    assert (count_versions(3001), count_versions(3002)) == versions_before  # no new versions
