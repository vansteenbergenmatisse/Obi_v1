"""Trigger orchestrator: turn one page's current state into a decided command, then apply it.

This is the trigger half of the two-layer split (``docs/plans/confluence-trigger-layer.md``).
It fetches the page's current state (meta, labels, covering ``source_scope`` rows, ancestry),
calls the pure :func:`decide_command`, and hands the resulting :class:`SyncCommand` to the
injected :class:`IngestionSink`. It never chunks, embeds, or imports ``app.features.ingestion``
— that edge is forbidden by ``tools/check_feature_boundaries.py``.

The same function serves both entry points (webhook worker and reconciliation sweep) on the
page's *current* state, so the two paths always agree; only ``reason`` differs.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.features.confluence_sync.application import scope_state
from app.features.confluence_sync.application.ports import IngestionSink, get_ingestion_sink
from app.features.confluence_sync.domain.ingest_decision import decide_command
from app.platform.clients import ConfluenceGateway
from app.platform.config import Settings
from app.platform.logging import get_logger
from app.shared.sync_command import SyncCommand, SyncOutcome

# Re-exported for continuity: callers and tests import SyncOutcome from this module.
__all__ = ["SyncOutcome", "handle_delete_page", "handle_sync_page"]

log = get_logger("confluence_sync.sync_service")


def handle_sync_page(
    session: Session,
    *,
    page_id: int,
    gateway: ConfluenceGateway,
    settings: Settings,
    reason: str = "edited",
    sink: IngestionSink | None = None,
) -> SyncOutcome:
    """Decide and apply the sync for one page from its current Confluence state."""
    meta = gateway.get_page_meta(page_id)
    labels = gateway.get_labels(page_id) if meta is not None else []

    roots = scope_state.all_scope_roots(session)
    space_rows: list = []
    ancestor_ids: set[int] = {page_id}
    if meta is not None and roots:
        rsi = scope_state.root_space_ids(gateway, roots)
        space_rows = scope_state.roots_for_space(roots, rsi, meta.space_id)
        ancestor_ids = scope_state.self_and_ancestor_ids(gateway, meta, space_rows)

    cmd = decide_command(
        page_id=page_id,
        meta=meta,
        labels=labels,
        space_rows=space_rows,
        self_and_ancestor_ids=ancestor_ids,
        # ADR-routing-labels-sole-content-axis: membership is the routing-label axis (the retired
        # knowledge-scope set is empty).
        recognized=settings.product_catalog.all_routing_labels(),
        reason=reason,
    )
    apply = sink or get_ingestion_sink()
    return apply(session, cmd, gateway, settings)


def handle_delete_page(
    session: Session,
    *,
    page_id: int,
    gateway: ConfluenceGateway,
    settings: Settings,
    reason: str = "page_gone",
    sink: IngestionSink | None = None,
) -> SyncOutcome:
    """A delete-class webhook event: emit an idempotent hard-purge command.

    Delete is idempotent, so this needs no state fetch — a page already gone or never indexed
    is a no-op purge.
    """
    cmd = SyncCommand(page_id=page_id, action="delete", scopes=(), reason=reason)
    apply = sink or get_ingestion_sink()
    return apply(session, cmd, gateway, settings)
