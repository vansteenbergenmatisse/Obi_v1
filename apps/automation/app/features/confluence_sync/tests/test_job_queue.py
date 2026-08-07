"""Job-queue semantics: SKIP LOCKED claim, fail backoff → dead-letter, expired-lease reaping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.platform.db.engine import get_sessionmaker, session_scope
from app.platform.db.enums import JobStatus
from app.platform.db.models import Job
from app.platform.jobs import claim_job, enqueue_job, fail_job, reap_expired


def _enqueue(key: str) -> None:
    with session_scope() as s:
        enqueue_job(s, job_type="sync_page", idempotency_key=key, page_id=1)


def _job(session, key: str) -> Job:
    return session.execute(select(Job).where(Job.idempotency_key == key)).scalar_one()


def test_claim_uses_skip_locked(session):
    _enqueue("q:a")
    _enqueue("q:b")

    sm = get_sessionmaker()
    s1, s2 = sm(), sm()
    try:
        j1 = claim_job(s1, owner="worker-1")  # locks its row, tx stays open
        j2 = claim_job(s2, owner="worker-2")  # must skip the locked row
        assert j1 is not None and j2 is not None
        assert j1.id != j2.id
    finally:
        s1.rollback()
        s2.rollback()
        s1.close()
        s2.close()


def test_fail_backs_off_then_dead_letters(session):
    _enqueue("q:dead")
    with session_scope() as s:
        _job(s, "q:dead").max_attempts = 3  # cap attempts low for a fast test

    base = datetime(2030, 1, 1, tzinfo=UTC)
    last_status = None
    for i in range(3):
        t = base + timedelta(hours=2 * i)  # advance past any backoff window
        with session_scope() as s:
            job = claim_job(s, owner="x", now=t)
            assert job is not None, f"expected to claim on attempt {i}"
            fail_job(s, job, error="boom", now=t)
            last_status = job.status

    assert last_status == JobStatus.dead_letter
    with session_scope() as s:
        assert _job(s, "q:dead").attempts == 3


def test_reap_reclaims_expired_lease(session):
    _enqueue("q:lease")
    t0 = datetime(2030, 1, 1, tzinfo=UTC)
    with session_scope() as s:
        job = claim_job(s, owner="crashed", lease_seconds=120, now=t0)
        assert job.status == JobStatus.running

    with session_scope() as s:
        assert reap_expired(s, now=t0 + timedelta(hours=1)) == 1

    with session_scope() as s:
        job = _job(s, "q:lease")
        assert job.status == JobStatus.pending
        assert job.lease_owner is None
