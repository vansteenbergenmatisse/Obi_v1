"""Background worker: claim a queued job, run its handler, complete or fail it.

Transaction discipline (ADR-0002 / decision D5) — three separate transactions per job:

1. **Claim** in its own committed transaction, so the lease + attempts increment are durable
   before any work runs. A crash after this point leaves a leased job the reaper reclaims.
2. **Handle + complete** in a single transaction: the index mutation and the ``succeeded``
   transition commit together, so a job is never marked done with its work rolled back.
3. **Fail** in a third transaction: if the handler raises, transaction 2 rolls back cleanly and
   the failure (backoff / dead-letter) is recorded independently, so the attempts increment and
   error are never lost to the same rollback that undid the work.

Because every handler is idempotent and version-guarded, re-running a reclaimed or retried job
is always safe.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.features.confluence_sync.application.event_service import (
    JOB_DELETE_PAGE,
    JOB_RECONCILE_SPACE,
    JOB_SYNC_PAGE,
)
from app.features.confluence_sync.application.sync_service import (
    SyncOutcome,
    handle_delete_page,
    handle_sync_page,
)
from app.platform.clients import ConfluenceGateway
from app.platform.config import Settings
from app.platform.db.engine import session_scope
from app.platform.db.models import Job
from app.platform.jobs import claim_job, complete_job, fail_job, reap_expired
from app.platform.logging import get_logger

log = get_logger("sync_worker")

# a handler takes the live session + the claimed job and performs the (idempotent) work
JobHandler = Callable[[Session, Job, ConfluenceGateway, Settings], object]


@dataclass
class RunResult:
    job_id: int
    job_type: str
    status: str  # succeeded | failed
    outcome: object | None = None
    error: str | None = None


def _handle_sync_page(session, job, gateway, settings) -> SyncOutcome:
    return handle_sync_page(session, page_id=job.page_id, gateway=gateway, settings=settings)


def _handle_delete_page(session, job, gateway, settings) -> SyncOutcome:
    status = (job.payload or {}).get("status", "trashed")
    return handle_delete_page(session, page_id=job.page_id, status=status)


def _handle_reconcile_space(session, job, gateway, settings):
    # lazy import avoids a module import cycle (reconciliation enqueues jobs via job consts)
    from app.features.confluence_sync.application.reconciliation import reconcile_space

    space_id = (job.payload or {}).get("space_id")
    if space_id is None:
        raise ValueError(f"reconcile_space job {job.id} missing space_id in payload")
    return reconcile_space(
        session, space_id=int(space_id), gateway=gateway, settings=settings
    )


HANDLERS: dict[str, JobHandler] = {
    JOB_SYNC_PAGE: _handle_sync_page,
    JOB_DELETE_PAGE: _handle_delete_page,
    JOB_RECONCILE_SPACE: _handle_reconcile_space,
}


def run_once(
    gateway: ConfluenceGateway,
    settings: Settings,
    *,
    owner: str,
    lease_seconds: int = 120,
    job_types: list[str] | None = None,
) -> RunResult | None:
    """Claim and process at most one job. Returns None when the queue is empty."""
    # transaction 1: claim (committed on context exit)
    with session_scope() as session:
        job = claim_job(
            session, owner=owner, lease_seconds=lease_seconds, job_types=job_types
        )
        if job is None:
            return None
        job_id = job.id
        job_type = job.job_type

    handler = HANDLERS.get(job_type)
    if handler is None:
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is not None:
                fail_job(session, job, error=f"no handler for job_type={job_type!r}")
        log.warning("job_no_handler", job_id=job_id, job_type=job_type)
        return RunResult(job_id, job_type, status="failed", error="no_handler")

    # transaction 2: handle + complete atomically
    try:
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise RuntimeError(f"claimed job {job_id} vanished before handling")
            outcome = handler(session, job, gateway, settings)
            complete_job(session, job)
        log.info("job_succeeded", job_id=job_id, job_type=job_type)
        return RunResult(job_id, job_type, status="succeeded", outcome=outcome)
    except Exception as exc:  # noqa: BLE001 — the queue is the failure boundary
        # transaction 3: record the failure independently of the rolled-back work
        with session_scope() as session:
            job = session.get(Job, job_id)
            if job is not None:
                fail_job(session, job, error=repr(exc))
        log.warning("job_failed", job_id=job_id, job_type=job_type, error=repr(exc))
        return RunResult(job_id, job_type, status="failed", error=repr(exc))


def drain(
    gateway: ConfluenceGateway,
    settings: Settings,
    *,
    owner: str,
    max_jobs: int = 100,
    job_types: list[str] | None = None,
) -> list[RunResult]:
    """Process jobs until the queue is empty or ``max_jobs`` is reached (bounded, non-blocking)."""
    results: list[RunResult] = []
    for _ in range(max_jobs):
        result = run_once(
            gateway, settings, owner=owner, job_types=job_types
        )
        if result is None:
            break
        results.append(result)
    return results


def reap(now=None) -> int:
    """Reclaim jobs whose lease expired (crashed worker). Returns count reclaimed."""
    with session_scope() as session:
        return reap_expired(session, now=now)
