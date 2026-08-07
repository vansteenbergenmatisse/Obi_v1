"""Dense (pgvector) and keyword (tsvector) candidate search over the active child index.

Both paths enforce the mandatory pre-model filters (active, child, current status, optional space)
in SQL. Dense search casts to ``halfvec`` for >2000-dim models to match the index. Results are
returned as ``(page_id, score)`` rows in rank order; a page may appear multiple times (once per
matching child) and is de-duplicated by the caller.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

_HALFVEC_MIN_DIM = 2001


def _base_filters(space_id: int | None) -> str:
    clause = "is_active AND kind = 1 AND page_status = 'current'"
    if space_id is not None:
        clause += " AND space_id = :space_id"
    return clause


# Natural-language questions rarely have every term in one short chunk, so plainto_tsquery's
# implicit AND matches nothing. Convert it to an OR query (any term matches) and let ts_rank order
# by how well each chunk matches — Postgres does the lexemization, so this stays injection-safe.
_OR_TSQUERY = "replace(plainto_tsquery('english', :q)::text, '&', '|')::tsquery"


def keyword_search(
    session: Session, query: str, space_id: int | None, limit: int
) -> list[tuple[int, float]]:
    sql = text(
        f"SELECT page_id, ts_rank(tsv, {_OR_TSQUERY}) AS score "
        f"FROM chunk "
        f"WHERE {_base_filters(space_id)} AND tsv @@ {_OR_TSQUERY} "
        f"ORDER BY score DESC, page_id ASC LIMIT :limit"
    )
    params = {"q": query, "limit": limit}
    if space_id is not None:
        params["space_id"] = space_id
    return [(int(pid), float(score)) for pid, score in session.execute(sql, params)]


def _vector_literal(vec: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def dense_search(
    session: Session, query_vec: Sequence[float], space_id: int | None, limit: int, dim: int
) -> list[tuple[int, float]]:
    # >2000-dim models are indexed as halfvec; cast both sides so the ANN index is used.
    if dim >= _HALFVEC_MIN_DIM:
        lhs = f"embedding::halfvec({dim})"
        rhs = f"CAST(:qvec AS halfvec({dim}))"
    else:
        lhs = "embedding"
        rhs = "CAST(:qvec AS vector)"
    sql = text(
        f"SELECT page_id, ({lhs} <=> {rhs}) AS dist "
        f"FROM chunk "
        f"WHERE {_base_filters(space_id)} AND embedding IS NOT NULL "
        f"ORDER BY dist ASC, page_id ASC LIMIT :limit"
    )
    params = {"qvec": _vector_literal(query_vec), "limit": limit}
    if space_id is not None:
        params["space_id"] = space_id
    return [(int(pid), float(dist)) for pid, dist in session.execute(sql, params)]
