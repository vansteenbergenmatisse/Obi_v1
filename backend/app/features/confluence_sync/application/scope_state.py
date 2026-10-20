"""Trigger-layer helpers for reading ``source_scope`` state and page ancestry.

These are the I/O-bearing companions to the pure ``domain.scope_resolver`` /
``domain.ingest_decision``: they fetch the ``source_scope`` rows, resolve which
space each root belongs to, and walk a page's ancestor chain — everything the
decision needs that touches the DB or the gateway. Kept out of ``ingest_decision``
so that module stays pure and unit-testable without either.

``map_page_status`` is a local copy of ingestion's identical mapper: the trigger
layer must not import ``app.features.ingestion`` (forbidden edge), and a
one-line ``PageStatus(...)`` mapping is not worth a shared module. Schema enums
are imported by full path (ADR-features-import-only-through-public-root).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.platform.clients import ConfluenceGateway, ConfluencePageMeta
from app.platform.logging import get_logger
from schema.enums import PageStatus
from schema.models import SourceScope

from ..domain.scope_resolver import ROOT_TYPE_PAGE, ROOT_TYPE_SPACE

log = get_logger("confluence_sync.scope_state")

_MAX_ANCESTOR_DEPTH = 50  # safety bound against a cyclic/pathological parent chain


def map_page_status(status: str) -> PageStatus:
    try:
        return PageStatus(status)
    except ValueError:
        return PageStatus.current


def all_scope_roots(session: Session) -> list[SourceScope]:
    """Every ``source_scope`` row, active or not (inactive presence still scopes a space)."""
    return list(session.execute(select(SourceScope)).scalars().all())


def root_space_ids(gateway: ConfluenceGateway, roots: list[SourceScope]) -> dict[int, int]:
    """Map each root's id -> the space it belongs to.

    ``space`` roots carry their space id directly; a ``page`` root needs one
    ``get_page_meta`` lookup. A root whose page is gone is skipped, not an error.
    """
    out: dict[int, int] = {}
    for root in roots:
        if root.root_type == ROOT_TYPE_SPACE:
            out[root.id] = int(root.root_id)
            continue
        meta = gateway.get_page_meta(int(root.root_id))
        if meta is not None:
            out[root.id] = meta.space_id
        else:
            log.warning("scope_root_page_missing", root_id=root.id, page_id=root.root_id)
    return out


def roots_for_space(
    roots: list[SourceScope], root_space_ids_map: dict[int, int], space_id: int
) -> list[SourceScope]:
    return [r for r in roots if root_space_ids_map.get(r.id) == int(space_id)]


def self_and_ancestor_ids(
    gateway: ConfluenceGateway, meta: ConfluencePageMeta, space_rows: list[SourceScope]
) -> set[int]:
    """The page's own id plus every ancestor id, for page-root subtree coverage.

    Skips the ancestor walk entirely when no ``page`` root is present in ``space_rows`` — a
    space-only scoping needs nothing beyond the page's ``space_id``, so the common case costs
    zero extra gateway calls.
    """
    ids = {meta.page_id}
    if not any(r.root_type == ROOT_TYPE_PAGE for r in space_rows):
        return ids
    current = meta
    depth = 0
    while current.parent_id is not None and depth < _MAX_ANCESTOR_DEPTH:
        pid = current.parent_id
        if pid in ids:
            break
        ids.add(pid)
        parent = gateway.get_page_meta(pid)
        if parent is None:
            break
        current = parent
        depth += 1
    return ids
