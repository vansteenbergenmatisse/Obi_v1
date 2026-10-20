"""SUPERSEDED by ADR-routing-labels-sole-content-axis. This was PLAN 10.7's read-only guard: verify every live chunk carried a
recognized knowledge-scope tag before the (now-retired) knowledge-scope filter was turned on.

ADR-routing-labels-sole-content-axis retired the knowledge-scope axis entirely — retrieval no longer filters on ``tags`` and the
``recognized`` set is empty — so this check no longer gates anything. It is kept only so its callers
and tests still import, and it now reports every active chunk as "unscoped" against the empty set,
which is expected. The routing-label membership/backfill equivalent is
``ingestion/application/backfill_labels.py``. It counts only ``is_active`` chunks: retrieval reads
only active chunks and superseded rows are GC'd, so historical rows need no backfill.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from schema.models import Chunk


@dataclass(frozen=True)
class KnowledgeScopeCoverage:
    """Result of the 10.7 pre-flip readiness check over the live corpus."""

    recognized_scopes: list[str]
    total_active_chunks: int
    untagged_active_chunks: int
    untagged_page_ids: list[int]

    @property
    def is_ready(self) -> bool:
        """Ready to flip the filter flag iff no live chunk lacks a recognized scope tag.

        An empty corpus is vacuously ready — with nothing live, flipping the flag excludes
        nothing.
        """
        return self.untagged_active_chunks == 0


def verify_knowledge_scope_coverage(
    session: Session, *, recognized_scopes: Collection[str]
) -> KnowledgeScopeCoverage:
    """Count live chunks whose tags overlap none of ``recognized_scopes``, grouped by page.

    Uses the same bound-array ``tags && :param`` overlap predicate as ``search_repo`` (PLAN 10.4),
    never a literal ``ARRAY[...]`` — the scope values are data, not SQL.
    """
    scopes = sorted(recognized_scopes)

    total = session.execute(
        select(func.count()).select_from(Chunk).where(Chunk.is_active)
    ).scalar_one()

    untagged_rows = session.execute(
        select(Chunk.page_id, func.count())
        .where(Chunk.is_active, ~Chunk.tags.overlap(scopes))
        .group_by(Chunk.page_id)
        .order_by(Chunk.page_id)
    ).all()

    return KnowledgeScopeCoverage(
        recognized_scopes=scopes,
        total_active_chunks=int(total),
        untagged_active_chunks=sum(int(count) for _page_id, count in untagged_rows),
        untagged_page_ids=[int(page_id) for page_id, _count in untagged_rows],
    )
