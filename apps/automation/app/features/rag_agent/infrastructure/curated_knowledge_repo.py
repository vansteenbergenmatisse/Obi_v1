"""Curated-knowledge query (PLAN 10.6): the one place this feature's answer workflow reads
`curated_knowledge_entry` directly, mirroring `infrastructure/llm_client.py`'s role as this
feature's I/O boundary and `retrieval/infrastructure/search_repo.py`'s bound-array-parameter
pattern for the identical `tags && :scopes` predicate (PLAN 10.4) — the list is always bound as a
parameter, never string-interpolated into the SQL text.

Access control (Phase 11.1a / ADR-0014): as of migration 0009 the table has an `anon`-denied RLS
posture (reader-scoped `*_reader_read` policy), and this read now also sets the customer-scope RLS
GUC (`app.allowed_knowledge_scopes`) via `apply_knowledge_scope` before the query, so the DB
enforces the same `curated_knowledge_entry_scope_read` RESTRICTIVE policy the retriever enforces on
`chunk`. The app-layer `tags && :allowed_scopes` predicate below is retained as defense-in-depth and
for deterministic ordering/limit; it is no longer the *only* access control.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.rag_agent.domain.curated_knowledge import CuratedEntry
from app.features.retrieval import apply_knowledge_scope

_QUERY = text(
    "SELECT id, tags, title, body FROM curated_knowledge_entry "
    "WHERE is_active AND (tags = '{}' OR tags && :allowed_scopes) "
    "ORDER BY id LIMIT :limit"
)


def fetch_curated_entries(
    session: Session, allowed_scopes: Sequence[str], limit: int
) -> list[CuratedEntry]:
    """Active entries with empty tags (always included) or overlapping `allowed_scopes`, capped at
    `limit`, ordered by id for deterministic citation numbering. Sets the customer-scope RLS GUC
    first (ADR-0014), so a bypassed app predicate cannot leak a cross-customer curated entry."""
    apply_knowledge_scope(session, list(allowed_scopes))
    rows = session.execute(_QUERY, {"allowed_scopes": list(allowed_scopes), "limit": limit}).all()
    return [CuratedEntry(id=r.id, tags=tuple(r.tags), title=r.title, body=r.body) for r in rows]
