"""panel i4-gate · substep 0.5.2 — the zero-child-chunks validation gate.

`stage_and_activate` (ingestion/application/versioning.py:238-242) raises before `_activate(...)`
is ever called when a staged build produces zero KIND_CHILD chunks. The whole handler transaction
(the worker's "transaction 2" in `run_once`) rolls back on that raise — `session_scope` commits on
success and rolls back on any exception — so nothing about the failed build, not even the staged
`DocumentVersion` row itself, survives in the database. The one durable, queryable trace of the
gate firing is the job row: a separate transaction ("transaction 3") records `job.last_error` and
`job.status = failed` for the claimed job, independently of the rolled-back work. That durability
split is exactly what the design panel's note describes: "The failure is visible in
job.last_error, and nothing was activated."
"""

from __future__ import annotations

import types

import pytest

from app.platform.config import Settings
from app.platform.db.engine import session_scope
from app.platform.db.enums import JobStatus
from app.platform.db.models import Job
from app.platform.jobs import enqueue_job

from ._helpers import active_version, count_versions, index_page, run_worker

pytestmark = (
    pytest.mark.db
)  # substep 0.5.2: real local Postgres via this dir's session-scoped conftest — mis-tagged
# as unit-level when this file was first written (found live during 0.5.4's CI-gate proof, when
# `make test-unit` tried to open a real Postgres connection in an environment with none running)


def test_i4_gate_zero_children_marks_version_failed(gateway, settings: Settings) -> None:
    """panel i4-gate · substep 0.5.2
    A page whose body normalizes to zero blocks (an empty Confluence page) fails the build: the
    sync job is marked failed with the gate's reason in job.last_error, and no DocumentVersion row
    for the page survives — the staged version and its (zero) chunks roll back together with it."""
    gateway.set_version(3010, 1)  # page-3010-empty.json: storage body is ""
    with session_scope() as s:
        enqueue_job(
            s,
            job_type="sync_page",
            idempotency_key="seed:3010:1",
            payload={"event_type": "test"},
            page_id=3010,
            cf_version=1,
        )
    results = run_worker(gateway, settings)

    assert len(results) == 1
    assert results[0].status == "failed"
    assert "staging produced no child chunks" in results[0].error

    with session_scope() as s:
        job = s.query(Job).filter(Job.page_id == 3010).one()
    assert job.status == JobStatus.failed
    assert job.last_error is not None
    assert "staging produced no child chunks" in job.last_error

    assert count_versions(3010) == 0  # the staged, now-failed version never persisted
    assert active_version(3010) is None  # nothing was activated


def test_i4_gate_zero_children_leaves_previously_active_version_untouched(
    gateway, settings: Settings, monkeypatch
) -> None:
    """panel i4-gate · substep 0.5.2
    A page indexed successfully at version 1 is later re-synced at a version whose body
    normalizes to zero blocks: the gate fails that build, and the page's active version-1 row is
    untouched (still the active one, unchanged) — "Live version: untouched"."""
    index_page(gateway, settings, 3001, 1)  # obi-general-test fixture: real content, no attachments
    v1 = active_version(3001)
    assert v1 is not None
    assert v1.state.value == "active"

    # Simulate a real Confluence revision whose storage body has been emptied out: a newer
    # version_number (so classify() treats it as a genuine edit needing a rebuild) whose body
    # normalizes to zero blocks. FixtureConfluenceGateway's on-disk corpus has no such per-version
    # snapshot for this page, so the upstream data is substituted directly on the same gateway
    # instance the real sync worker drives — the sync_service/classify/stage_and_activate path
    # itself runs unmodified and unmocked.
    real_get_page_meta = gateway.get_page_meta
    real_get_page = gateway.get_page

    def _bumped_meta(page_id: int):
        meta = real_get_page_meta(page_id)
        if meta is None:
            return None
        return meta.model_copy(update={"version_number": meta.version_number + 1})

    def _empty_body(page_id: int):
        page = real_get_page(page_id)
        return None if page is None else types.SimpleNamespace(body_storage="   ")

    monkeypatch.setattr(gateway, "get_page_meta", _bumped_meta)
    monkeypatch.setattr(gateway, "get_page", _empty_body)

    with session_scope() as s:
        enqueue_job(
            s,
            job_type="sync_page",
            idempotency_key="seed:3001:2",
            payload={"event_type": "test"},
            page_id=3001,
            cf_version=2,
        )
    results = run_worker(gateway, settings)

    assert len(results) == 1
    assert results[0].status == "failed"
    assert "staging produced no child chunks" in results[0].error

    v1_after = active_version(3001)
    assert v1_after is not None
    assert v1_after.id == v1.id  # the same row, not a new one
    assert v1_after.state.value == "active"  # unchanged
    assert count_versions(3001) == 1  # the failed rebuild attempt left no second row
