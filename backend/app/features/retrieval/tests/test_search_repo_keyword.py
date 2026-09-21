"""panel r2-keyword · substep p0-s0_5-reg-retrieval-stage-2

Pins the three checks the panel names for keyword search that
``test_search_repo_knowledge_scope.py`` does not cover (that file is scoped to the optional
PLAN-10.4 ``knowledge_scopes`` predicate only):

* the AND-to-OR ``tsquery`` rewrite (``plainto_tsquery`` with ``&`` replaced by ``|``) is present
  in the emitted SQL;
* the score expression is ``ts_rank(tsv, ...)`` and it drives ``ORDER BY score DESC``;
* the predicate is written against the ``tsv`` column, which is what ``ix_chunk_tsv_gin`` indexes.

SQL-shape/binding-discipline tests with a spy session (no database needed) — mirrors
``test_search_repo_gucs.py``'s and ``test_search_repo_knowledge_scope.py``'s ``_SpySession`` style.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.features.retrieval.infrastructure.search_repo import keyword_search


class _SpySession:
    """Records the SQL text and bound params passed to `execute`; returns no rows."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, clause: Any, params: dict[str, Any] | None = None) -> list[Any]:
        self.calls.append((str(clause), dict(params or {})))
        return []

    def as_session(self) -> Session:
        return cast(Session, self)


def test_r2_keyword_and_rewritten_to_or_in_query() -> None:
    """panel r2-keyword · substep p0-s0_5-reg-retrieval-stage-2
    The tsquery built from the question is plainto_tsquery with its implicit AND (&) rewritten
    to OR (|), so a multi-term question matches a chunk sharing any term, not all of them."""
    s = _SpySession()
    keyword_search(s.as_session(), "annual leave policy", None, 75)
    sql, params = s.calls[0]
    assert "replace(plainto_tsquery('english', :q)::text, '&', '|')::tsquery" in sql
    assert params["q"] == "annual leave policy"


def test_r2_keyword_rank_expression_is_ts_rank_on_tsv() -> None:
    """panel r2-keyword · substep p0-s0_5-reg-retrieval-stage-2
    The rank/score column is ts_rank(tsv, query), aliased as score, and ORDER BY sorts by that
    score descending (ties broken by page_id ascending) so the caller's LIMIT keeps the best
    matches."""
    s = _SpySession()
    keyword_search(s.as_session(), "q", None, 75)
    sql, _ = s.calls[0]
    assert (
        "ts_rank(tsv, replace(plainto_tsquery('english', :q)::text, '&', '|')::tsquery) AS score"
        in sql
    )
    assert "ORDER BY score DESC, page_id ASC" in sql


def test_r2_keyword_predicate_is_against_tsv_column() -> None:
    """panel r2-keyword · substep p0-s0_5-reg-retrieval-stage-2
    The WHERE clause matches the rewritten tsquery against the `tsv` column (not, say, a raw text
    column), which is what ix_chunk_tsv_gin indexes -- so the planner can use that index."""
    s = _SpySession()
    keyword_search(s.as_session(), "q", None, 75)
    sql, _ = s.calls[0]
    assert "tsv @@ replace(plainto_tsquery('english', :q)::text, '&', '|')::tsquery" in sql
    assert "FROM chunk" in sql


def test_r2_keyword_limit_is_bound_not_interpolated() -> None:
    """panel r2-keyword · substep p0-s0_5-reg-retrieval-stage-2
    The row cap (75 per the panel's Settings) is a bound parameter, never interpolated into the
    SQL text, so an arbitrary caller-supplied limit can't reach the query as raw SQL."""
    s = _SpySession()
    keyword_search(s.as_session(), "q", None, 75)
    sql, params = s.calls[0]
    assert "LIMIT :limit" in sql
    assert "LIMIT 75" not in sql
    assert params["limit"] == 75


def test_r2_keyword_applies_base_filter_clause_bound_not_interpolated() -> None:
    """panel r2-keyword · substep p0-s0_5-reg-retrieval-stage-2
    The panel's Filters row says "the same as dense": the mandatory pre-model filter — active,
    child kind, current page status, and the source list — is present in keyword search's
    emitted SQL too, and the source list is bound as a parameter, not interpolated into the
    query text."""
    s = _SpySession()
    keyword_search(s.as_session(), "q", None, 75, sources=["source-one", "source-two"])
    sql, params = s.calls[0]
    assert "is_active AND kind = 1 AND page_status = 'current'" in sql
    assert "source_id = ANY(:sources)" in sql
    assert "source-one" not in sql
    assert "source-two" not in sql
    assert params["sources"] == ["source-one", "source-two"]
