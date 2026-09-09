"""PLAN 10.4: retrieval-time knowledge-scope filtering, behind the flag.

`_base_filters` (and the three query builders that use it) gain an optional `knowledge_scopes`
predicate. These are SQL-shape/binding-discipline tests with a spy session (no database needed) —
mirrors `test_search_repo_gucs.py`'s style: when the caller passes `None` (the default, i.e. the
flag-off path), the emitted SQL is byte-for-byte the pre-10.4 shape; when a list is passed, the
predicate appears and the values are bound, never interpolated into the SQL text.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.features.retrieval.infrastructure.search_repo import (
    dense_search,
    fetch_rerank_texts,
    keyword_search,
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


def test_keyword_search_omits_predicate_when_knowledge_scopes_is_none() -> None:
    s = _SpySession()
    keyword_search(s.as_session(), "q", None, 10)
    sql, params = s.calls[0]
    assert "tags &&" not in sql
    assert "knowledge_scopes" not in params


def test_keyword_search_adds_predicate_when_knowledge_scopes_given() -> None:
    s = _SpySession()
    keyword_search(
        s.as_session(), "q", None, 10, knowledge_scopes=["obi-general-test", "obi-mews-test"]
    )
    sql, params = s.calls[0]
    assert "tags && :knowledge_scopes" in sql
    assert params["knowledge_scopes"] == ["obi-general-test", "obi-mews-test"]


def test_dense_search_omits_predicate_when_knowledge_scopes_is_none() -> None:
    s = _SpySession()
    dense_search(s.as_session(), [0.1, 0.2], None, 10, dim=2)
    sql, params = s.calls[0]
    assert "tags &&" not in sql
    assert "knowledge_scopes" not in params


def test_dense_search_adds_predicate_when_knowledge_scopes_given() -> None:
    s = _SpySession()
    dense_search(s.as_session(), [0.1, 0.2], None, 10, dim=2, knowledge_scopes=["obi-general-test"])
    sql, params = s.calls[0]
    assert "tags && :knowledge_scopes" in sql
    assert params["knowledge_scopes"] == ["obi-general-test"]


def test_fetch_rerank_texts_adds_predicate_when_knowledge_scopes_given() -> None:
    s = _SpySession()
    fetch_rerank_texts(s.as_session(), [1, 2], None, knowledge_scopes=["obi-toast-test"])
    sql, params = s.calls[0]
    assert "tags && :knowledge_scopes" in sql
    assert params["knowledge_scopes"] == ["obi-toast-test"]


def test_fetch_rerank_texts_omits_predicate_when_knowledge_scopes_is_none() -> None:
    s = _SpySession()
    fetch_rerank_texts(s.as_session(), [1, 2], None)
    sql, params = s.calls[0]
    assert "tags &&" not in sql
    assert "knowledge_scopes" not in params


def test_malicious_knowledge_scope_value_never_reaches_sql_text() -> None:
    s = _SpySession()
    keyword_search(
        s.as_session(), "q", None, 10, knowledge_scopes=["general'; DROP TABLE chunk; --"]
    )
    sql, params = s.calls[0]
    assert "DROP TABLE" not in sql
    assert params["knowledge_scopes"] == ["general'; DROP TABLE chunk; --"]
