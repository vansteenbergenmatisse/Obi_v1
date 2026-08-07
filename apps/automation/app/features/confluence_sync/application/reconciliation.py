"""Reconciliation: the safety net that repairs drift missed by the webhook stream.

Two sweeps, both idempotent and both driven through the same queue the webhook uses, so a
reconciled page follows the identical version-guarded path as a live event (never a blind
re-embed):

* **lightweight** (scheduled daily): cheap signals only. For each live source page, enqueue a
  ``sync_page`` when version / status / parent / title drift from the registry. Registry pages
  that have vanished from the source listing are enqueued for re-check (the handler deactivates
  them if truly gone).
* **complete** (scheduled every ``complete_recon_interval_days``): full re-verification.
  Enqueue a ``sync_page`` for *every* live source page so the handler re-checks
  labels / permissions / attachments even when the version did not move, and orphaned registry
  pages are deactivated directly.

Every sweep is recorded as a :class:`ReconciliationRun` row with counts and a per-bucket report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.confluence_sync.application.event_service import JOB_SYNC_PAGE
from app.features.ingestion import deactivate_page, map_page_status
from app.platform.clients.confluence_client import ConfluenceGateway, ConfluencePageMeta
from app.platform.config import Settings
from app.platform.db.enums import PageStatus, ReconStatus
from app.platform.db.models import PageSource, ReconciliationRun
from app.platform.jobs import enqueue_job
from app.platform.logging import get_logger

log = get_logger("reconciliation")

KIND_LIGHTWEIGHT = "lightweight"
KIND_COMPLETE = "complete"


@dataclass
class _Counters:
    pages_scanned: int = 0
    drift: int = 0
    jobs_enqueued: int = 0
    orphans_deleted: int = 0
    errors: int = 0
    new_pages: list[int] = field(default_factory=list)
    drifted_pages: list[int] = field(default_factory=list)
    orphan_pages: list[int] = field(default_factory=list)


def _needs_sync(reg: PageSource, meta: ConfluencePageMeta) -> bool:
    """Cheap drift signals detectable without fetching the body."""
    return (
        meta.version_number > reg.current_cf_version
        or map_page_status(meta.status) != reg.page_status
        or meta.parent_id != reg.parent_id
        or meta.title != reg.title
    )


def _registry_for_space(session: Session, space_id: int) -> dict[int, PageSource]:
    rows = session.execute(
        select(PageSource).where(PageSource.space_id == space_id)
    ).scalars().all()
    return {row.page_id: row for row in rows}


def _enqueue_sync(
    session: Session,
    meta: ConfluencePageMeta,
    settings: Settings,
    *,
    key_suffix: str,
) -> bool:
    """Idempotently enqueue a sync_page job. Returns True if a new job was created."""
    schema = settings.retrieval_schema_version
    key = f"{JOB_SYNC_PAGE}:recon:{meta.page_id}:{key_suffix}:{schema}"
    job_id = enqueue_job(
        session,
        job_type=JOB_SYNC_PAGE,
        idempotency_key=key,
        payload={"event_type": "reconcile"},
        page_id=meta.page_id,
        cf_version=meta.version_number,
    )
    return job_id is not None


def _sweep_space(
    session: Session,
    *,
    space_id: int,
    gateway: ConfluenceGateway,
    settings: Settings,
    kind: str,
    run_id: int,
    counters: _Counters,
) -> None:
    live = gateway.list_space_pages(space_id)
    live_ids = {m.page_id for m in live}
    registry = _registry_for_space(session, space_id)

    for meta in live:
        counters.pages_scanned += 1
        reg = registry.get(meta.page_id)
        is_new = reg is None
        drifted = is_new or _needs_sync(reg, meta)
        if drifted:
            counters.drift += 1
            (counters.new_pages if is_new else counters.drifted_pages).append(meta.page_id)

        if kind == KIND_COMPLETE:
            # re-verify every live page; run_id in the key forces one sync per page per run
            suffix = f"complete:{run_id}"
            enqueue = True
        else:
            # lightweight: only enqueue on a cheap drift signal
            suffix = f"v{meta.version_number}:s{meta.status}:p{meta.parent_id}"
            enqueue = drifted

        if enqueue and _enqueue_sync(session, meta, settings, key_suffix=suffix):
            counters.jobs_enqueued += 1

    # orphans: pages we still index as current that no longer appear in the live listing
    for page_id, reg in registry.items():
        if page_id in live_ids or reg.page_status != PageStatus.current:
            continue
        counters.orphan_pages.append(page_id)
        if kind == KIND_COMPLETE:
            if deactivate_page(session, page_id=page_id, status=PageStatus.deleted):
                counters.orphans_deleted += 1
        else:
            # lightweight: let the handler confirm-and-deactivate via the normal path
            meta_stub = gateway.get_page_meta(page_id)
            if meta_stub is None:
                if deactivate_page(session, page_id=page_id, status=PageStatus.deleted):
                    counters.orphans_deleted += 1
            elif _enqueue_sync(session, meta_stub, settings, key_suffix="orphan"):
                counters.jobs_enqueued += 1


def _run(
    session: Session,
    *,
    scope: str,
    space_ids: list[int],
    gateway: ConfluenceGateway,
    settings: Settings,
    kind: str,
) -> ReconciliationRun:
    run = ReconciliationRun(scope=scope, kind=kind, status=ReconStatus.running)
    session.add(run)
    session.flush()  # assign run.id

    counters = _Counters()
    for space_id in space_ids:
        try:
            _sweep_space(
                session,
                space_id=space_id,
                gateway=gateway,
                settings=settings,
                kind=kind,
                run_id=run.id,
                counters=counters,
            )
        except Exception as exc:  # noqa: BLE001 — one bad space must not abort the sweep
            counters.errors += 1
            log.warning("reconcile_space_error", space_id=space_id, error=repr(exc))

    run.status = ReconStatus.completed if counters.errors == 0 else ReconStatus.failed
    run.finished_at = datetime.now(UTC)
    run.pages_scanned = counters.pages_scanned
    run.drift_detected = counters.drift
    run.jobs_enqueued = counters.jobs_enqueued
    run.orphans_deleted = counters.orphans_deleted
    run.errors = counters.errors
    run.report = {
        "spaces": space_ids,
        "new_pages": counters.new_pages,
        "drifted_pages": counters.drifted_pages,
        "orphan_pages": counters.orphan_pages,
    }
    session.flush()
    log.info(
        "reconciliation_done",
        scope=scope,
        kind=kind,
        pages_scanned=run.pages_scanned,
        drift=run.drift_detected,
        jobs=run.jobs_enqueued,
        orphans_deleted=run.orphans_deleted,
        errors=run.errors,
    )
    return run


def _known_space_ids(session: Session) -> list[int]:
    rows = session.execute(select(PageSource.space_id).distinct()).scalars().all()
    return sorted(set(rows))


def reconcile_space(
    session: Session,
    *,
    space_id: int,
    gateway: ConfluenceGateway,
    settings: Settings,
    kind: str = KIND_LIGHTWEIGHT,
) -> ReconciliationRun:
    """Reconcile a single space (the ``reconcile_space`` job handler entry point)."""
    return _run(
        session,
        scope=f"space:{space_id}",
        space_ids=[int(space_id)],
        gateway=gateway,
        settings=settings,
        kind=kind,
    )


def run_reconciliation(
    session: Session,
    *,
    gateway: ConfluenceGateway,
    settings: Settings,
    kind: str = KIND_LIGHTWEIGHT,
    space_ids: list[int] | None = None,
) -> ReconciliationRun:
    """Sweep all known (or the given) spaces — the scheduled entry point."""
    ids = space_ids if space_ids is not None else _known_space_ids(session)
    return _run(
        session,
        scope="all",
        space_ids=ids,
        gateway=gateway,
        settings=settings,
        kind=kind,
    )
