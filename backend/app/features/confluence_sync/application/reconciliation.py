"""Reconciliation: the safety net that repairs drift missed by the webhook stream.

The sweep is pure *trigger*: it discovers candidate pages and enqueues minimal
``(page_id, reason)`` sync jobs — it never chunks, embeds, deactivates, or otherwise touches
ingestion. Every enqueued job flows through the same worker as a webhook event, so the worker's
``decide_command`` (on the page's current state) is the single authority on upsert-vs-delete;
the sweep only decides *which pages to look at*.

Candidates for a space are the union of:

* pages covered by the space's ``source_scope`` roots (``resolve_space_scope``), and
* pages carrying a recognized label found by CQL label discovery
  (``gateway.list_pages_by_label``) — the safety net that surfaces a freshly-tagged page even
  when no root covers it (the original "Mews Page 2 was never ingested" bug).

Two cadences:

* **lightweight** (scheduled daily): enqueue a candidate only on a cheap drift signal
  (version / status / parent / title) or when it is newly discovered.
* **complete** (scheduled every ``complete_recon_interval_days``): enqueue *every* candidate so
  the worker re-checks labels / permissions / attachments even when the version did not move.

Registry pages that are no longer candidates (vanished upstream, or no longer covered by any
active root) are enqueued for re-check; the worker confirms and hard-purges them.

Every sweep is recorded as a :class:`ReconciliationRun` row with counts and a per-bucket report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.confluence_sync.application.event_service import JOB_SYNC_PAGE
from app.features.confluence_sync.application.scope_state import (
    all_scope_roots,
    map_page_status,
    root_space_ids,
    roots_for_space,
)
from app.features.confluence_sync.domain.scope_resolver import resolve_space_scope
from app.platform.clients import ConfluenceGateway, ConfluencePageMeta
from app.platform.config import Settings
from app.platform.jobs import enqueue_job
from app.platform.logging import get_logger
from schema.enums import PageStatus, ReconStatus
from schema.models import PageSource, ReconciliationRun, SourceScope

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
    rows = (
        session.execute(select(PageSource).where(PageSource.space_id == space_id)).scalars().all()
    )
    return {row.page_id: row for row in rows}


def _enqueue_sync(
    session: Session,
    meta: ConfluencePageMeta,
    settings: Settings,
    *,
    key_suffix: str,
    reason: str,
) -> bool:
    """Idempotently enqueue a minimal ``(page_id, reason)`` sync job. Returns True if newly created.

    No tags ride along: the worker re-derives the authoritative scopes from the page's current
    state (``decide_command``), so the sweep carries only the page id and a ``reason`` trace hint.
    """
    schema = settings.retrieval_schema_version
    key = f"{JOB_SYNC_PAGE}:recon:{meta.page_id}:{key_suffix}:{schema}"
    job_id = enqueue_job(
        session,
        job_type=JOB_SYNC_PAGE,
        idempotency_key=key,
        payload={"event_type": "reconcile", "reason": reason},
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
    roots: list[SourceScope] | None = None,
) -> None:
    live = gateway.list_space_pages(space_id)
    registry = _registry_for_space(session, space_id)

    # PLAN 3.5.6: zero source_scope rows ever recorded for this space -> unrestricted
    # (allowed_page_ids=None), the exact byte-for-byte behavior this sweep always had. Once any
    # row exists, coverage is explicit — see resolve_space_scope's docstring for why that
    # includes the "last root deactivated -> fully purge" case.
    scope = resolve_space_scope(live, roots or [])
    allowed_page_ids = scope.allowed_page_ids
    scoped_live = (
        live if allowed_page_ids is None else [m for m in live if m.page_id in allowed_page_ids]
    )

    # CQL safety net: union in every recognized-label page, even one no root covers. It surfaces
    # a freshly-tagged page for the worker to authorize (or reject) — the "Mews Page 2" fix. Only
    # tagged pages come back, so this adds a small, bounded set, not the whole space.
    discovered = gateway.list_pages_by_label(space_id, sorted(settings.knowledge_scope_set))

    candidates: dict[int, ConfluencePageMeta] = {}
    for meta in [*scoped_live, *discovered]:
        candidates.setdefault(meta.page_id, meta)

    for meta in candidates.values():
        counters.pages_scanned += 1
        reg = registry.get(meta.page_id)
        is_new = reg is None
        drifted = is_new or _needs_sync(reg, meta)
        if drifted:
            counters.drift += 1
            (counters.new_pages if is_new else counters.drifted_pages).append(meta.page_id)

        reason = "sweep_discovery" if is_new else "sweep_drift"
        if kind == KIND_COMPLETE:
            # re-verify every candidate; run_id in the key forces one sync per page per run
            suffix = f"complete:{run_id}"
            enqueue = True
        else:
            # lightweight: only enqueue on a cheap drift signal (or first discovery)
            suffix = f"v{meta.version_number}:s{meta.status}:p{meta.parent_id}"
            enqueue = drifted

        if enqueue and _enqueue_sync(session, meta, settings, key_suffix=suffix, reason=reason):
            counters.jobs_enqueued += 1

    # Orphans: registry rows that are no longer candidates — vanished upstream, or no longer
    # covered by any active root (a root was removed/narrowed). Enqueue a re-check; the worker's
    # decide_command confirms the current state and hard-purges (get_page_meta None, non-current
    # status, or no covering authorization). No direct deactivation here — the sweep is pure
    # trigger, the worker owns every delete.
    for page_id, reg in registry.items():
        if page_id in candidates:
            continue
        if reg.page_status != PageStatus.current:
            continue
        counters.orphan_pages.append(page_id)
        suffix = f"orphan:{run_id}" if kind == KIND_COMPLETE else "orphan"
        meta_stub = gateway.get_page_meta(page_id) or ConfluencePageMeta(
            page_id=page_id,
            space_id=space_id,
            parent_id=reg.parent_id,
            title=reg.title,
            status="deleted",
            version_number=reg.current_cf_version,
            version_created_at=datetime.now(UTC),
            source_url=reg.source_url or "",
        )
        if _enqueue_sync(session, meta_stub, settings, key_suffix=suffix, reason="page_gone"):
            counters.jobs_enqueued += 1
            counters.orphans_deleted += 1


def _run(
    session: Session,
    *,
    scope: str,
    space_ids: list[int],
    gateway: ConfluenceGateway,
    settings: Settings,
    kind: str,
    roots: list[SourceScope] | None = None,
    root_space_map: dict[int, int] | None = None,
) -> ReconciliationRun:
    run = ReconciliationRun(scope=scope, kind=kind, status=ReconStatus.running)
    session.add(run)
    session.flush()  # assign run.id

    if roots is None:
        roots = all_scope_roots(session)
    if root_space_map is None:
        root_space_map = root_space_ids(gateway, roots)

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
                roots=roots_for_space(roots, root_space_map, space_id),
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
    """Sweep all known (or the given) spaces — the scheduled entry point.

    "Known" spaces are the union of (a) spaces already in the ``page_source`` registry and
    (b) spaces implied by any recorded ``source_scope`` row, active or not — (b) is what lets a
    *brand-new* space or page-subtree get its first sweep at all, and what lets a space whose
    only root was just deactivated still get visited so it can actually be purged. Without (b),
    a space with zero existing registry rows was never reconciled no matter what was configured
    (the old ``CONFLUENCE_SPACES`` gap this replaces).
    """
    roots = all_scope_roots(session)
    root_space_map = root_space_ids(gateway, roots)
    ids = (
        space_ids
        if space_ids is not None
        else sorted(set(_known_space_ids(session)) | set(root_space_map.values()))
    )
    return _run(
        session,
        scope="all",
        space_ids=ids,
        gateway=gateway,
        settings=settings,
        kind=kind,
        roots=roots,
        root_space_map=root_space_map,
    )
