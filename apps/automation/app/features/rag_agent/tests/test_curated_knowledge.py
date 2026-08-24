"""PLAN 10.6: the always-present curated knowledge layer's pure adapter, plus SQL-shape/
binding-discipline tests for its one query (no database needed — mirrors
`retrieval/tests/test_search_repo_knowledge_scope.py`'s spy-session style). Scope-filtering
behavior against real Postgres is proven separately in `confluence_sync/tests/
test_curated_knowledge_repo.py`, matching PLAN 10.4's own split between binding-shape tests here
and real-DB isolation tests there.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.features.rag_agent.domain.curated_knowledge import CuratedEntry, curated_entry_to_hit
from app.features.rag_agent.infrastructure.curated_knowledge_repo import fetch_curated_entries


def test_curated_entry_to_hit_uses_a_namespaced_page_id_and_negative_chunk_id() -> None:
    entry = CuratedEntry(id=3, tags=("mews",), title="Password reset", body="...")
    hit = curated_entry_to_hit(entry)
    assert hit.page_id == "curated:3"
    assert hit.chunk_id == -3
    assert hit.title == "Password reset"
    assert hit.url == ""


def test_curated_entry_to_hit_ids_never_collide_between_distinct_entries() -> None:
    a = curated_entry_to_hit(CuratedEntry(id=1, tags=(), title="A", body="a"))
    b = curated_entry_to_hit(CuratedEntry(id=2, tags=(), title="B", body="b"))
    assert a.chunk_id != b.chunk_id
    assert a.page_id != b.page_id


class _SpySession:
    """Records the SQL text and bound params passed to `execute`; returns no rows."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, clause: Any, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((str(clause), dict(params or {})))

        class _Result:
            def all(self) -> list[Any]:
                return []

        return _Result()

    def as_session(self) -> Session:
        return cast(Session, self)


def test_fetch_curated_entries_binds_scopes_as_a_parameter_never_interpolated() -> None:
    s = _SpySession()
    fetch_curated_entries(s.as_session(), ["general", "mews"], limit=5)
    sql, params = s.calls[0]
    assert "tags && :allowed_scopes" in sql
    assert params["allowed_scopes"] == ["general", "mews"]
    assert params["limit"] == 5


def test_fetch_curated_entries_binds_a_malicious_scope_value_never_reaches_raw_sql() -> None:
    s = _SpySession()
    payload = "general'; DROP TABLE curated_knowledge_entry; --"
    fetch_curated_entries(s.as_session(), [payload], limit=5)
    sql, params = s.calls[0]
    assert payload not in sql
    assert params["allowed_scopes"] == [payload]


def test_fetch_curated_entries_includes_the_empty_tags_always_included_clause() -> None:
    s = _SpySession()
    fetch_curated_entries(s.as_session(), ["general"], limit=5)
    sql, _ = s.calls[0]
    assert "tags = '{}'" in sql
    assert "is_active" in sql
    assert "ORDER BY id" in sql
    assert "LIMIT :limit" in sql
