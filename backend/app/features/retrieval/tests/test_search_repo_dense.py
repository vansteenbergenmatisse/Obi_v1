"""panel r2-dense · substep p0-s0_5-reg-retrieval-stage-2

Pins the checks in the ``r2-dense`` panel that ``test_search_repo_knowledge_scope.py`` does not
cover: that ``dense_search`` orders by the cosine ``<=>`` operator, that it casts to ``halfvec`` at
the same dimension threshold the HNSW index is built at (so the planner can use
``ix_chunk_embedding_hnsw``, see ``knowledge-base/schema/models.py::_embedding_hnsw_index`` /
``_HNSW_MAX_VECTOR_DIM``), and that its mandatory pre-model filter clause — active, child kind,
current page status, source list — is present and bound rather than interpolated. Spy-session
unit tests, no database, mirroring ``test_search_repo_gucs.py`` /
``test_search_repo_knowledge_scope.py``.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.features.retrieval.infrastructure.search_repo import (
    _HALFVEC_MIN_DIM,
    dense_search,
)


class _SpySession:
    """Records the SQL text and bound params passed to `execute`; returns no rows."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, clause: Any, params: dict[str, Any] | None = None) -> list[Any]:
        self.calls.append((str(clause), dict(params or {})))
        return []

    def as_session(self) -> Session:
        return cast(Session, self)


def test_r2_dense_uses_cosine_operator() -> None:
    """panel r2-dense · substep p0-s0_5-reg-retrieval-stage-2
    Dense search orders candidates by the pgvector cosine distance operator ``<=>``."""
    s = _SpySession()
    dense_search(s.as_session(), [0.1, 0.2], None, 10, dim=2, sources=["src-a"])
    sql, _ = s.calls[0]
    assert "<=>" in sql
    assert "ORDER BY dist ASC, page_id ASC" in sql


def test_r2_dense_casts_to_halfvec_at_index_dim_threshold() -> None:
    """panel r2-dense · substep p0-s0_5-reg-retrieval-stage-2
    At >=2001 dims (matching the halfvec index built when dim > 2000, see
    models.py::_HNSW_MAX_VECTOR_DIM), both sides of the ``<=>`` comparison are cast to
    ``halfvec(dim)`` so the query can use ``ix_chunk_embedding_hnsw``."""
    assert _HALFVEC_MIN_DIM == 2001
    s = _SpySession()
    dense_search(s.as_session(), [0.1] * 3072, None, 10, dim=3072, sources=["src-a"])
    sql, _ = s.calls[0]
    assert "embedding::halfvec(3072)" in sql
    assert "CAST(:qvec AS halfvec(3072))" in sql


def test_r2_dense_does_not_cast_to_halfvec_below_index_dim_threshold() -> None:
    """panel r2-dense · substep p0-s0_5-reg-retrieval-stage-2
    Below the 2001-dim threshold the plain ``vector`` type is used (matches the non-halfvec
    branch of ``_embedding_hnsw_index``); no halfvec cast is emitted."""
    s = _SpySession()
    dense_search(s.as_session(), [0.1, 0.2], None, 10, dim=2, sources=["src-a"])
    sql, _ = s.calls[0]
    assert "halfvec" not in sql
    assert "CAST(:qvec AS vector)" in sql


def test_r2_dense_applies_base_filter_clause_bound_not_interpolated() -> None:
    """panel r2-dense · substep p0-s0_5-reg-retrieval-stage-2
    The mandatory pre-model filter — active, child kind, current page status, and the source
    list — is present in the emitted SQL, and the source list is bound as a parameter, not
    interpolated into the query text."""
    s = _SpySession()
    dense_search(s.as_session(), [0.1, 0.2], None, 10, dim=2, sources=["source-one", "source-two"])
    sql, params = s.calls[0]
    assert "is_active AND kind = 1 AND page_status = 'current'" in sql
    assert "source_id = ANY(:sources)" in sql
    assert "source-one" not in sql
    assert "source-two" not in sql
    assert params["sources"] == ["source-one", "source-two"]


def test_r2_dense_requires_non_null_embedding() -> None:
    """panel r2-dense · substep p0-s0_5-reg-retrieval-stage-2
    Dense search never matches a chunk with no embedding: ``embedding IS NOT NULL`` is part
    of the WHERE clause alongside the base filters."""
    s = _SpySession()
    dense_search(s.as_session(), [0.1, 0.2], None, 10, dim=2, sources=["src-a"])
    sql, _ = s.calls[0]
    assert "embedding IS NOT NULL" in sql


def test_vd_question_compared_to_child_vectors_by_cosine_distance() -> None:
    """panel vd-question · substep p0-s0_5-reg-the-vector-database
    The question vector is compared with the child vectors by cosine distance: dense_search
    orders candidates by the pgvector ``<=>`` operator -- cosine, given the index built with
    ``vector_cosine_ops``/``halfvec_cosine_ops`` (models.py's ``_embedding_hnsw_index``) -- and
    the comparison is restricted to child-kind chunks (``kind = 1``), never a page's parent
    chunk or any other row shape."""
    s = _SpySession()
    dense_search(s.as_session(), [0.1] * 3072, None, 75, dim=3072, sources=["src-a"])
    sql, _ = s.calls[0]
    assert "<=>" in sql
    assert "kind = 1" in sql


def test_r2_dense_limit_is_bound_not_interpolated() -> None:
    """panel r2-dense · substep p0-s0_5-reg-retrieval-stage-2
    The row cap (candidate_k = 75 per the panel's Settings) is a bound parameter, never
    interpolated into the SQL text, so an arbitrary caller-supplied limit can't reach the query
    as raw SQL."""
    s = _SpySession()
    dense_search(s.as_session(), [0.1, 0.2], None, 75, dim=2, sources=["src-a"])
    sql, params = s.calls[0]
    assert "LIMIT :limit" in sql
    assert "LIMIT 75" not in sql
    assert params["limit"] == 75
