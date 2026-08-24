"""Persist a per-retrieval ``query_trace`` row (PLAN 3.5.4) and its Phase-4 answer fields.

Retrieval reads as the non-owner ``rag_reader`` (RLS-subject), but trace writes run on a separate
WRITER session so RLS never blocks them and the Phase-4 answer runtime can UPDATE the row it
inserted at retrieval time. ``write_query_trace`` now also carries ``retrieved_chunk_ids`` /
``rerank_scores`` (PLAN 4.2 fills in the columns 3.5.4 reserved) and returns the new row's id so
the caller can update it once the answer is grounded and, later, once feedback arrives.
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
    retrieved_chunk_ids: Sequence[int] | None = None,
    rerank_scores: Sequence[float] | None = None,
    allowed_knowledge_scopes: Sequence[str] | None = None,
) -> int:
    """Insert one ``query_trace`` row, commit, and return its id."""
    row = QueryTrace(
        raw_query=raw_query,
        retrieved_page_ids=list(retrieved_page_ids),
        allowed_sources=list(allowed_sources),
        embedding_model=embedding_model,
        reranker_model=reranker_model,
        latency_ms=latency_ms,
        retrieved_chunk_ids=list(retrieved_chunk_ids) if retrieved_chunk_ids is not None else None,
        rerank_scores=list(rerank_scores) if rerank_scores is not None else None,
        allowed_knowledge_scopes=(
            list(allowed_knowledge_scopes) if allowed_knowledge_scopes is not None else None
        ),
    )
    session.add(row)
    session.commit()
    return row.id


def update_query_trace_answer(
    session: Session,
    trace_id: int,
    *,
    rewritten_query: str,
    answer: str,
    citations: list[dict],
) -> None:
    """UPDATE a trace row with the grounded answer (PLAN 4.2). Writer session; RLS never applies."""
    row = session.get(QueryTrace, trace_id)
    if row is None:
        return
    row.rewritten_query = rewritten_query
    row.answer = answer
    row.citations = {"markers": citations}
    session.commit()


def update_query_trace_feedback(session: Session, trace_id: int, feedback: int) -> None:
    """UPDATE a trace row's thumbs up/down (+1/-1) (PLAN 4.4). Writer session."""
    row = session.get(QueryTrace, trace_id)
    if row is None:
        return
    row.feedback = feedback
    session.commit()
