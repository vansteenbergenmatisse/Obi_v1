"""Idempotent backfill of the raw-labels column (ADR-directed-source-target-routing-labels D1, panel mi-labels, substep 9.1.2).

Stamps each indexed page's *raw* Confluence labels (the unresolved ``get_labels`` output) onto its
``page_source`` row and its active chunks, for pages indexed before migration 0016 added the column.
Mirrors how ``_apply_metadata_only`` restamps on a live label change — no re-embed, same version.

Idempotent by construction: a page is only written when its stored ``labels`` drift from the freshly
fetched raw labels, so a second run finds nothing drifted and writes nothing. Confluence is the only
source of a page's raw labels, so the backfill reads them through the passed gateway (the same
``ConfluenceGateway`` sync uses); the operator CLI wrapper lives in ``backend/scripts``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from app.platform.clients import ConfluenceGateway
from schema.engine import session_scope
from schema.models import Chunk, PageSource


@dataclass(frozen=True)
class BackfillReport:
    """What one backfill run did. ``pages_stamped``/``chunks_stamped`` are 0 on a clean re-run."""

    pages_scanned: int
    pages_stamped: int
    chunks_stamped: int


def backfill_labels(gateway: ConfluenceGateway) -> BackfillReport:
    """Stamp raw Confluence labels onto every indexed page's registry row + active chunks.

    Returns a :class:`BackfillReport`. Safe to run twice: only drifted rows are written.
    """
    pages_scanned = 0
    pages_stamped = 0
    chunks_stamped = 0
    with session_scope() as session:
        page_ids = list(session.execute(select(PageSource.page_id)).scalars().all())
        for page_id in page_ids:
            pages_scanned += 1
            ps = session.get(PageSource, page_id)
            if ps is None:  # concurrent purge between the id scan and the load
                continue
            desired = [str(label) for label in gateway.get_labels(page_id)]
            active_chunks = list(
                session.execute(
                    select(Chunk).where(Chunk.page_id == page_id, Chunk.is_active.is_(True))
                )
                .scalars()
                .all()
            )
            drifted_chunks = [c for c in active_chunks if list(c.labels) != desired]
            if list(ps.labels) == desired and not drifted_chunks:
                continue  # already in sync — idempotent no-op
            ps.labels = desired
            for chunk in drifted_chunks:
                chunk.labels = desired
            pages_stamped += 1
            chunks_stamped += len(drifted_chunks)
    return BackfillReport(
        pages_scanned=pages_scanned,
        pages_stamped=pages_stamped,
        chunks_stamped=chunks_stamped,
    )
