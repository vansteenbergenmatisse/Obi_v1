"""Job-queue semantics: SKIP LOCKED claim, fail backoff → dead-letter, expired-lease reaping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.platform.jobs import claim_job, enqueue_job, fail_job, reap_expired
from schema.engine import get_sessionmaker, session_scope
from schema.enums import JobStatus
from schema.models import Job

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest


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
        assert job is not None
        assert job.status == JobStatus.running

    with session_scope() as s:
        assert reap_expired(s, now=t0 + timedelta(hours=1)) == 1

    with session_scope() as s:
        job = _job(s, "q:lease")
        assert job.status == JobStatus.pending
        assert job.lease_owner is None


def test_i1_claim_sets_lease_owner_expiry_and_increments_attempts(session):
    """panel i1-claim · substep p0-s0_5-reg-ingestion-stage-1
    Claim sets lease_owner, a lease 120s past now by default, and increments attempts."""
    _enqueue("q:claim-lease")
    t0 = datetime(2030, 1, 1, tzinfo=UTC)
    with session_scope() as s:
        job = claim_job(s, owner="worker-lease", now=t0)
        assert job is not None
        assert job.lease_owner == "worker-lease"
        assert job.lease_expires_at == t0 + timedelta(seconds=120)
        assert job.attempts == 1


def test_i1_claim_orders_by_priority_then_available_at(session):
    """panel i1-claim · substep p0-s0_5-reg-ingestion-stage-1
    Claim orders by priority ascending then available_at: the lower-priority-value job wins."""
    t0 = datetime(2030, 1, 1, tzinfo=UTC)
    with session_scope() as s:
        enqueue_job(
            s,
            job_type="sync_page",
            idempotency_key="q:prio-low",
            page_id=1,
            priority=200,
            available_at=t0,
        )
        enqueue_job(
            s,
            job_type="sync_page",
            idempotency_key="q:prio-high",
            page_id=1,
            priority=50,
            available_at=t0,
        )

    with session_scope() as s:
        job = claim_job(s, owner="worker-prio", now=t0)
        assert job is not None
        assert job.idempotency_key == "q:prio-high"


def test_i1_claim_commits_in_its_own_transaction_before_handling(session):
    """panel i1-claim · substep p0-s0_5-reg-ingestion-stage-1
    Claim runs and commits in its own transaction, durable before any handling work starts: a
    second, independent session sees the claimed job's running status/lease/attempts immediately,
    with no other write in between."""
    _enqueue("q:claim-commit")
    with session_scope() as s:
        job = claim_job(s, owner="worker-commit")
        assert job is not None
        claimed_id = job.id

    sm = get_sessionmaker()
    reader = sm()
    try:
        seen = reader.execute(select(Job).where(Job.id == claimed_id)).scalar_one()
        assert seen.status == JobStatus.running
        assert seen.lease_owner == "worker-commit"
        assert seen.attempts == 1
    finally:
        reader.close()


def test_i1_reaper_also_reclaims_leased_status_jobs(session):
    """panel i1-reaper · substep p0-s0_5-reg-ingestion-stage-1
    The defensive `leased` status (never assigned by claim_job, but matched by the reaper's
    WHERE clause) is reclaimed to pending just like `running`."""
    _enqueue("q:leased-status")
    t0 = datetime(2030, 1, 1, tzinfo=UTC)
    with session_scope() as s:
        job = _job(s, "q:leased-status")
        job.status = JobStatus.leased
        job.lease_owner = "crashed-leased"
        job.lease_expires_at = t0 - timedelta(minutes=1)

    with session_scope() as s:
        assert reap_expired(s, now=t0) == 1

    with session_scope() as s:
        job = _job(s, "q:leased-status")
        assert job.status == JobStatus.pending
        assert job.lease_owner is None


def test_i1_fail_default_max_attempts_is_five(session):
    """panel i1-fail · substep p0-s0_5-reg-ingestion-stage-1
    Attempts defaults to 5: the 4th failure stays failed, the 5th dead-letters."""
    _enqueue("q:default-attempts")

    base = datetime(2030, 1, 1, tzinfo=UTC)
    for i in range(4):
        t = base + timedelta(hours=2 * i)
        with session_scope() as s:
            job = claim_job(s, owner="x", now=t)
            assert job is not None, f"expected to claim on attempt {i}"
            fail_job(s, job, error="boom", now=t)
            assert job.status == JobStatus.failed

    t = base + timedelta(hours=2 * 4)
    with session_scope() as s:
        job = claim_job(s, owner="x", now=t)
        assert job is not None, "expected to claim on attempt 5"
        fail_job(s, job, error="boom", now=t)
        assert job.status == JobStatus.dead_letter

    with session_scope() as s:
        assert _job(s, "q:default-attempts").attempts == 5


def test_i1_fail_backoff_doubles_and_caps_at_one_hour(session):
    """panel i1-fail · substep p0-s0_5-reg-ingestion-stage-1
    Backoff is 5 * 2^(attempts-1) seconds, capped at 3600."""
    _enqueue("q:backoff")
    now = datetime(2030, 1, 1, tzinfo=UTC)

    with session_scope() as s:
        job = _job(s, "q:backoff")
        job.attempts = 1
        job.max_attempts = 1000  # never dead-letter within this test
        fail_job(s, job, error="boom", now=now)
        assert job.available_at - now == timedelta(seconds=5)

    with session_scope() as s:
        job = _job(s, "q:backoff")
        job.attempts = 4
        fail_job(s, job, error="boom", now=now)
        assert job.available_at - now == timedelta(seconds=40)

    with session_scope() as s:
        job = _job(s, "q:backoff")
        job.attempts = 20
        fail_job(s, job, error="boom", now=now)
        assert job.available_at - now == timedelta(seconds=3600)


def test_i1_fail_error_text_truncated_to_4000_chars(session):
    """panel i1-fail · substep p0-s0_5-reg-ingestion-stage-1
    An error longer than 4000 characters is cut to exactly the first 4000."""
    _enqueue("q:truncate")
    now = datetime(2030, 1, 1, tzinfo=UTC)
    long_error = "e" * 5000

    with session_scope() as s:
        job = _job(s, "q:truncate")
        fail_job(s, job, error=long_error, now=now)
        assert job.last_error is not None
        assert len(job.last_error) == 4000
        assert job.last_error == long_error[:4000]
