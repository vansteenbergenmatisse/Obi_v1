"""Idempotent, crash-safe job queue backed by the ``job`` table.

- enqueue is idempotent on ``idempotency_key`` (ON CONFLICT DO NOTHING)
- claim uses ``FOR UPDATE SKIP LOCKED`` so multiple workers never grab the same row
- a lease + reaper recovers jobs whose worker crashed mid-run (idempotent handlers make this safe)
- failures back off exponentially and dead-letter after ``max_attempts``
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from schema.enums import JobStatus
from schema.models import Job


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(UTC)


def enqueue_job(
    session: Session,
    *,
    job_type: str,
    idempotency_key: str,
    payload: dict | None = None,
    page_id: int | None = None,
    cf_version: int | None = None,
    priority: int = 100,
    available_at: datetime | None = None,
    source_event_id: int | None = None,
) -> int | None:
    """Insert a job; return its id, or None if an identical key already exists."""
    stmt = (
        pg_insert(Job)
        .values(
            job_type=job_type,
            idempotency_key=idempotency_key,
            payload=payload or {},
            page_id=page_id,
            cf_version=cf_version,
            priority=priority,
            available_at=available_at or _now(),
            source_event_id=source_event_id,
        )
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
        .returning(Job.id)
    )
    return session.execute(stmt).scalar_one_or_none()


def claim_job(
    session: Session,
    *,
    owner: str,
    lease_seconds: int = 120,
    job_types: list[str] | None = None,
    now: datetime | None = None,
) -> Job | None:
    """Atomically claim one runnable job. Caller commits the surrounding transaction."""
    now = _now(now)
    stmt = (
        select(Job)
        .where(
            Job.status.in_([JobStatus.pending, JobStatus.failed]),
            Job.available_at <= now,
        )
        .order_by(Job.priority.asc(), Job.available_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job_types:
        stmt = stmt.where(Job.job_type.in_(job_types))
    job = session.execute(stmt).scalar_one_or_none()
    if job is None:
        return None
    job.status = JobStatus.running
    job.lease_owner = owner
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.attempts += 1
    job.updated_at = now
    session.flush()
    return job


def complete_job(session: Session, job: Job, now: datetime | None = None) -> None:
    job.status = JobStatus.succeeded
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = _now(now)
    session.flush()


def fail_job(
    session: Session,
    job: Job,
    *,
    error: str,
    now: datetime | None = None,
    base_backoff_seconds: int = 5,
) -> None:
    now = _now(now)
    job.last_error = error[:4000]
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = now
    if job.attempts >= job.max_attempts:
        job.status = JobStatus.dead_letter
    else:
        job.status = JobStatus.failed
        backoff = base_backoff_seconds * (2 ** max(0, job.attempts - 1))
        job.available_at = now + timedelta(seconds=min(backoff, 3600))
    session.flush()


def reap_expired(session: Session, *, now: datetime | None = None) -> int:
    """Reclaim jobs whose lease expired (crashed worker). Returns count reclaimed."""
    now = _now(now)
    stmt = (
        update(Job)
        .where(
            Job.status.in_([JobStatus.leased, JobStatus.running]),
            Job.lease_expires_at < now,
        )
        .values(status=JobStatus.pending, lease_owner=None, lease_expires_at=None, updated_at=now)
    )
    return session.execute(stmt).rowcount or 0
