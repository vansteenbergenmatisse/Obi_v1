"""Curated-knowledge query (PLAN 10.6): the one place this feature's answer workflow reads
`curated_knowledge_entry` directly, mirroring `infrastructure/llm_client.py`'s role as this
feature's I/O boundary and `retrieval/infrastructure/search_repo.py`'s bound-array-parameter
pattern for the identical `tags && :scopes` predicate (PLAN 10.4) — the list is always bound as a
parameter, never string-interpolated into the SQL text. `curated_knowledge_entry` carries no RLS
(PLAN 10.3's migration only added the table/index/column, not a policy) — tag filtering is the only
access control this query needs.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.rag_agent.domain.curated_knowledge import CuratedEntry

_QUERY = text(
    "SELECT id, tags, title, body FROM curated_knowledge_entry "
    "WHERE is_active AND (tags = '{}' OR tags && :allowed_scopes) "
    "ORDER BY id LIMIT :limit"
)


def fetch_curated_entries(
    session: Session, allowed_scopes: Sequence[str], limit: int
) -> list[CuratedEntry]:
    """Active entries with empty tags (always included) or overlapping `allowed_scopes`, capped at
    `limit`, ordered by id for deterministic citation numbering."""
    rows = session.execute(_QUERY, {"allowed_scopes": list(allowed_scopes), "limit": limit}).all()
    return [CuratedEntry(id=r.id, tags=tuple(r.tags), title=r.title, body=r.body) for r in rows]
