"""Persist a per-retrieval ``query_trace`` row (PLAN 3.5.4).

Retrieval reads as the non-owner ``rag_reader`` (RLS-subject), but the trace insert runs on a
separate WRITER session so RLS never blocks it and the Phase-4 answer runtime can UPDATE the same
row later. 3.5.4 writes only the retrieval columns; the rest stay NULL until Phase 4.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.platform.db.models import QueryTrace


def write_query_trace(
    session: Session,
    *,
    raw_query: str,
    retrieved_page_ids: Sequence[int],
    allowed_sources: Sequence[str],
    embedding_model: str,
    reranker_model: str,
    latency_ms: int,
) -> None:
    """Insert one partial ``query_trace`` row and commit."""
    session.add(
        QueryTrace(
            raw_query=raw_query,
            retrieved_page_ids=list(retrieved_page_ids),
            allowed_sources=list(allowed_sources),
            embedding_model=embedding_model,
            reranker_model=reranker_model,
            latency_ms=latency_ms,
        )
    )
    session.commit()
