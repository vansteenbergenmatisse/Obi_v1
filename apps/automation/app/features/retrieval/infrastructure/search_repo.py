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

# pgvector 0.8+ iterative-scan modes. Whitelisted because SET LOCAL cannot bind parameters,
# so the value is interpolated into SQL — an unchecked string here would be an injection point.
_ITERATIVE_SCAN_MODES = frozenset({"off", "relaxed_order", "strict_order"})


def apply_hnsw_gucs(session: Session, *, ef_search: int, iterative_scan: str) -> None:
    """Set the per-transaction pgvector HNSW knobs on ``session``.

    ``SET LOCAL`` scopes the change to the current transaction and takes effect only within
    it (the retriever never commits between this call and its searches, so it holds). It cannot
    bind parameters, so values are *validated*, not bound: ``ef_search`` is coerced to ``int``
    and ``iterative_scan`` is whitelisted, defaulting to ``relaxed_order`` on an unknown value.
    """
    ef = int(ef_search)
    mode = iterative_scan if iterative_scan in _ITERATIVE_SCAN_MODES else "relaxed_order"
    session.execute(text(f"SET LOCAL hnsw.ef_search = {ef}"))
    session.execute(text(f"SET LOCAL hnsw.iterative_scan = '{mode}'"))


def apply_source_scope(session: Session, allowed_sources: Sequence[str]) -> None:
    """Set the RLS scope GUC ``app.allowed_sources`` for this transaction (ADR-0004).

    Uses ``set_config(..., is_local=true)`` with a **bound** parameter: ``SET LOCAL`` cannot bind,
    and interpolating the caller's source list would be an injection vector or a silent
    default-deny. Scoped to the transaction, matching the searches that follow. An empty list
    yields an empty string -> the policy matches nothing -> default-deny.
    """
    session.execute(
        text("SELECT set_config('app.allowed_sources', :s, true)"),
        {"s": ",".join(allowed_sources)},
    )


def _base_filters(space_id: int | None, sources: Sequence[str] | None) -> str:
    clause = "is_active AND kind = 1 AND page_status = 'current'"
    if space_id is not None:
        clause += " AND space_id = :space_id"
    if sources is not None:
        # explicit source filter alongside RLS: correctness + recall, and lets the planner use
        # ix_chunk_active_source. RLS is the security net; this is the query's own predicate.
        clause += " AND source_id = ANY(:sources)"
    return clause


# Natural-language questions rarely have every term in one short chunk, so plainto_tsquery's
# implicit AND matches nothing. Convert it to an OR query (any term matches) and let ts_rank order
# by how well each chunk matches — Postgres does the lexemization, so this stays injection-safe.
_OR_TSQUERY = "replace(plainto_tsquery('english', :q)::text, '&', '|')::tsquery"


def keyword_search(
    session: Session,
    query: str,
    space_id: int | None,
    limit: int,
    sources: Sequence[str] | None = None,
) -> list[tuple[int, float]]:
    sql = text(
        f"SELECT page_id, ts_rank(tsv, {_OR_TSQUERY}) AS score "
        f"FROM chunk "
        f"WHERE {_base_filters(space_id, sources)} AND tsv @@ {_OR_TSQUERY} "
        f"ORDER BY score DESC, page_id ASC LIMIT :limit"
    )
    params: dict[str, object] = {"q": query, "limit": limit}
    if space_id is not None:
        params["space_id"] = space_id
    if sources is not None:
        params["sources"] = list(sources)
    return [(int(pid), float(score)) for pid, score in session.execute(sql, params)]


def _vector_literal(vec: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def dense_search(
    session: Session,
    query_vec: Sequence[float],
    space_id: int | None,
    limit: int,
    dim: int,
    sources: Sequence[str] | None = None,
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
        f"WHERE {_base_filters(space_id, sources)} AND embedding IS NOT NULL "
        f"ORDER BY dist ASC, page_id ASC LIMIT :limit"
    )
    params: dict[str, object] = {"qvec": _vector_literal(query_vec), "limit": limit}
    if space_id is not None:
        params["space_id"] = space_id
    if sources is not None:
        params["sources"] = list(sources)
    return [(int(pid), float(dist)) for pid, dist in session.execute(sql, params)]


def fetch_rerank_texts(
    session: Session,
    page_ids: Sequence[int],
    space_id: int | None,
    sources: Sequence[str] | None = None,
) -> dict[int, str]:
    """One representative text per page for the cross-encoder, keyed by page id.

    The retriever deals in page ids; reranking needs text. This returns, per page, the earliest
    active child chunk's ``title + retrieval_content`` (truncated to 4000 chars), under the same
    pre-model filters as search — so a page the filters would exclude never gets reranked in.
    """
    if not page_ids:
        return {}
    sql = text(
        f"SELECT DISTINCT ON (page_id) page_id, "
        f"left(title || ' ' || retrieval_content, 4000) AS txt "
        f"FROM chunk "
        f"WHERE {_base_filters(space_id, sources)} AND page_id = ANY(:page_ids) "
        f"ORDER BY page_id, seq"
    )
    params: dict[str, object] = {"page_ids": list(page_ids)}
    if space_id is not None:
        params["space_id"] = space_id
    if sources is not None:
        params["sources"] = list(sources)
    return {int(pid): str(txt) for pid, txt in session.execute(sql, params)}
