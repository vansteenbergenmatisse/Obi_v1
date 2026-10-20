"""Curated-knowledge query (PLAN 10.6): the one place this feature's answer workflow reads
`curated_knowledge_entry` directly, mirroring `infrastructure/llm_client.py`'s role as this
feature's I/O boundary and `retrieval/infrastructure/search_repo.py`'s bound-array-parameter
pattern for the identical `tags && :scopes` predicate (PLAN 10.4) — the list is always bound as a
parameter, never string-interpolated into the SQL text.

Access control: as of migration 0009 the table has an `anon`-denied RLS posture (reader-scoped
`*_reader_read` policy). The knowledge-scope policy (`curated_knowledge_entry_scope_read`,
ADR-db-level-customer-scope-isolation-backstop) is RETIRED: migration 0018 dropped it
(ADR-routing-labels-sole-content-axis). `apply_knowledge_scope(session, None)` still runs, but it
only sets the `'*'` wildcard on a GUC no policy reads. The app-layer
`tags = '{}' OR tags && :allowed_scopes` predicate below is unchanged, and because every gate
builds `allowed_scopes` empty, the query returns ONLY untagged curated entries (`tags = '{}'`);
tagged entries are currently never returned.
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
    `limit`, ordered by id for deterministic citation numbering.
    ADR-routing-labels-sole-content-axis retired the knowledge
    scope axis, so the scope GUC is opted out (wildcard None) and the curated query matches on the
    `allowed_scopes` overlap (empty → entries with empty tags, always included)."""
    apply_knowledge_scope(session, None)
    rows = session.execute(_QUERY, {"allowed_scopes": list(allowed_scopes), "limit": limit}).all()
    return [CuratedEntry(id=r.id, tags=tuple(r.tags), title=r.title, body=r.body) for r in rows]
