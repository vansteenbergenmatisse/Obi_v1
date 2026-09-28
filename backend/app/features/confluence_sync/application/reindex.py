"""The full re-index job (PLAN 2.0.3): rebuild every tagged page under one resumable job.

When a pipeline stamp changes (parser / chunker / contextualization / embedding model / schema),
every tagged page must be rebuilt — instead of waiting for the daily sweep to notice. This module
is the orchestration only: it enumerates every tagged page and idempotently enqueues a ``sync_page``
job for each, exactly the same version/config-guarded path a live webhook event takes. The per-page
rebuild itself (``handle_sync_page`` → ``stage_and_activate``) is unchanged and reused, so the
reindex never deep-imports ingestion and a rebuild still embeds the whole page (never a reused
vector).

Modelled as a :class:`ReconciliationRun` with ``kind='reindex'`` so "the job row shows progress" is
literally true: ``total_pages`` / ``pages_done`` are the counter and ``cursor`` is the resumable
batch cursor (the last tagged ``page_id`` enqueued). A crash mid-run resumes from the persisted
cursor and never re-enqueues a completed page. The enqueue idempotency key embeds the pipeline
stamp, so a *second* run at the same stamp enqueues nothing (a no-op) while bumping any stamp yields
fresh keys and rebuilds every page.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.features.confluence_sync.application.event_service import JOB_REINDEX, JOB_SYNC_PAGE
from app.platform.config import Settings
from app.platform.jobs import enqueue_job
from app.platform.logging import get_logger
from schema.enums import PageStatus, ReconStatus
from schema.models import PageSource, ReconciliationRun

log = get_logger("reindex")

KIND_REINDEX = "reindex"

_DEFAULT_BATCH_SIZE = 100  # reuse the worker drain-cap convention


def _stamp_signature(settings: Settings) -> str:
    """A deterministic fingerprint of the whole pipeline stamp.

    Any of the five rebuild triggers changing yields a new signature, which changes every
    per-page idempotency key — so bumping a stamp enqueues fresh rebuild jobs while re-running at
    the same stamp collides on the existing keys (a no-op).
    """
    return (
        f"p{settings.parser_version}"
        f":c{settings.chunker_version}"
        f":x{settings.contextualization_version}"
        f":s{settings.retrieval_schema_version}"
        f":e{settings.embedding_model}"
    )


def _tagged_pages(session: Session) -> list[tuple[int, list[str]]]:
    """Every live (current) page carrying at least one tag, ordered by page_id for a stable
    resumable cursor."""
    rows = session.execute(
        select(PageSource.page_id, PageSource.tags)
        .where(
            PageSource.page_status == PageStatus.current,
            func.cardinality(PageSource.tags) > 0,
        )
        .order_by(PageSource.page_id.asc())
    ).all()
    return [(int(pid), list(tags)) for pid, tags in rows]


def _enqueue_reindex_sync(session: Session, page_id: int, *, sig: str, tags: list[str]) -> bool:
    """Idempotently enqueue one ``sync_page`` rebuild. Returns True iff a new job was created.

    The page's persisted tags ride in the payload so a rebuild preserves source_scope tags (label
    tags are re-derived by the handler regardless). The key embeds the stamp signature so the
    second run at the same stamp is a no-op.
    """
    key = f"{JOB_SYNC_PAGE}:reindex:{page_id}:{sig}"
    payload: dict = {"event_type": "reindex"}
    if tags:
        payload["tags"] = list(tags)
    job_id = enqueue_job(
        session,
        job_type=JOB_SYNC_PAGE,
        idempotency_key=key,
        payload=payload,
        page_id=page_id,
    )
    return job_id is not None


def _resume_or_start(session: Session, sig: str) -> ReconciliationRun:
    """Resume the latest ``reindex`` run when it matches this stamp, else start a fresh one.

    A running run at this stamp is resumed from its cursor; a completed run at this stamp is
    returned as-is (the second-run no-op). A run at a *different* stamp (an older reindex) never
    blocks a new one — bumping a stamp always starts a fresh run.
    """
    latest = session.execute(
        select(ReconciliationRun)
        .where(ReconciliationRun.kind == KIND_REINDEX)
        .order_by(ReconciliationRun.started_at.desc(), ReconciliationRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if (
        latest is not None
        and (latest.report or {}).get("stamp") == sig
        and latest.status in (ReconStatus.running, ReconStatus.completed)
    ):
        return latest
    run = ReconciliationRun(
        scope="reindex",
        kind=KIND_REINDEX,
        status=ReconStatus.running,
        report={"stamp": sig},
    )
    session.add(run)
    session.flush()  # assign run.id
    return run


def run_reindex(
    session: Session,
    *,
    settings: Settings,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    max_batches: int | None = None,
) -> ReconciliationRun:
    """Enqueue a ``sync_page`` rebuild for every tagged page, in resumable batches.

    ``max_batches`` bounds one invocation (a crash / restart boundary); with it unset the run
    drains to completion. Progress is persisted (flushed) after every batch so a restart re-reads
    ``cursor`` / ``pages_done`` and continues from the next page.
    """
    sig = _stamp_signature(settings)
    run = _resume_or_start(session, sig)
    if run.status == ReconStatus.completed:
        return run  # second run at the same stamp: nothing to do

    pages = _tagged_pages(session)
    run.total_pages = len(pages)
    # resume: everything after the persisted cursor (pages are ordered by page_id)
    remaining = [p for p in pages if run.cursor is None or p[0] > run.cursor]

    for batches_done, start in enumerate(range(0, len(remaining), batch_size)):
        if max_batches is not None and batches_done >= max_batches:
            session.flush()  # persist partial progress; stays 'running' for the next invocation
            log.info(
                "reindex_partial",
                run_id=run.id,
                pages_done=run.pages_done,
                total_pages=run.total_pages,
                cursor=run.cursor,
            )
            return run
        for page_id, tags in remaining[start : start + batch_size]:
            if _enqueue_reindex_sync(session, page_id, sig=sig, tags=tags):
                run.jobs_enqueued += 1
            run.pages_done += 1
            run.cursor = page_id
        session.flush()

    run.status = ReconStatus.completed
    run.finished_at = datetime.now(UTC)
    session.flush()
    log.info(
        "reindex_done",
        run_id=run.id,
        total_pages=run.total_pages,
        pages_done=run.pages_done,
        jobs_enqueued=run.jobs_enqueued,
    )
    return run


def enqueue_reindex_job(session: Session, settings: Settings) -> int | None:
    """Enqueue the single ``reindex`` job (the operator/scheduler entry point).

    Idempotent on the stamp signature: enqueuing again at the same stamp is a no-op; a stamp bump
    enqueues a fresh reindex job. The worker's handler runs it via :func:`run_reindex`.
    """
    sig = _stamp_signature(settings)
    return enqueue_job(
        session,
        job_type=JOB_REINDEX,
        idempotency_key=f"{JOB_REINDEX}:{sig}",
        payload={"stamp": sig},
    )
