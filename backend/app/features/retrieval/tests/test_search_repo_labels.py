"""Option A Stage 6 / substep 9.4.1 (panel mi-hardfilter): the directed-connection label filter.

SQL-shape/binding-discipline tests with a spy session (no database) — mirrors
``test_search_repo_knowledge_scope.py``: when ``session_labels`` is ``None`` the emitted SQL is
byte-for-byte the pre-9.4.1 shape; when a list is passed the ``labels && :session_labels`` overlap
predicate appears right after the ``tags`` overlap and the values are BOUND, never interpolated
(never-bend rule 10). ``apply_allowed_labels`` sets the ``app.allowed_labels`` GUC via a bound
``set_config`` (same injection-safety discipline as ``apply_knowledge_scope``).
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.features.retrieval.infrastructure.search_repo import (
    apply_allowed_labels,
    dense_search,
    fetch_rerank_texts,
    keyword_search,
)


class _SpySession:
    """Records the SQL text and bound params passed to ``execute``; returns no rows."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, clause: Any, params: dict[str, Any] | None = None) -> list[Any]:
        self.calls.append((str(clause), dict(params or {})))
        return []

    def as_session(self) -> Session:
        return cast(Session, self)


def test_tags_keyword_search_omits_label_predicate_when_session_labels_is_none() -> None:
    """panel mi-hardfilter · substep 9.4.1
    A legacy/slot chat carries no session labels: the label overlap never enters the SQL."""
    s = _SpySession()
    keyword_search(s.as_session(), "q", None, 10)
    sql, params = s.calls[0]
    assert "labels &&" not in sql
    assert "session_labels" not in params


def test_tags_keyword_search_adds_label_predicate_when_session_labels_given() -> None:
    """panel mi-hardfilter · substep 9.4.1
    A directed chat's session labels become a bound ``labels && :session_labels`` overlap."""
    s = _SpySession()
    keyword_search(s.as_session(), "q", None, 10, session_labels=["obi-general", "toast-to-pms"])
    sql, params = s.calls[0]
    assert "labels && :session_labels" in sql
    assert params["session_labels"] == ["obi-general", "toast-to-pms"]


def test_tags_dense_search_adds_label_predicate_when_session_labels_given() -> None:
    """panel mi-hardfilter · substep 9.4.1
    The dense candidate path carries the same bound label overlap before top-k."""
    s = _SpySession()
    dense_search(s.as_session(), [0.1, 0.2], None, 10, dim=2, session_labels=["toast-to-pms"])
    sql, params = s.calls[0]
    assert "labels && :session_labels" in sql
    assert params["session_labels"] == ["toast-to-pms"]


def test_tags_fetch_rerank_texts_adds_label_predicate_when_session_labels_given() -> None:
    """panel mi-hardfilter · substep 9.4.1
    The rerank-text fetch applies the SAME label overlap, so an excluded page never reranks in."""
    s = _SpySession()
    fetch_rerank_texts(s.as_session(), [1, 2], None, session_labels=["obi-general"])
    sql, params = s.calls[0]
    assert "labels && :session_labels" in sql
    assert params["session_labels"] == ["obi-general"]


def test_tags_fetch_rerank_texts_omits_label_predicate_when_session_labels_is_none() -> None:
    """panel mi-hardfilter · substep 9.4.1
    No session labels: the rerank-text SQL stays byte-for-byte the pre-9.4.1 shape."""
    s = _SpySession()
    fetch_rerank_texts(s.as_session(), [1, 2], None)
    sql, params = s.calls[0]
    assert "labels &&" not in sql
    assert "session_labels" not in params


def test_sec_malicious_label_value_never_reaches_sql_text() -> None:
    """panel mi-hardfilter · substep 9.4.1
    A hostile session-label string rides as a bound value, never interpolated into the SQL text."""
    s = _SpySession()
    keyword_search(s.as_session(), "q", None, 10, session_labels=["general'; DROP TABLE chunk; --"])
    sql, params = s.calls[0]
    assert "DROP TABLE" not in sql
    assert params["session_labels"] == ["general'; DROP TABLE chunk; --"]


def test_sec_apply_allowed_labels_uses_bound_param_not_interpolated() -> None:
    """panel mi-hardfilter · substep 9.4.1
    Labels GUC: set_config('app.allowed_labels', :s, true) — value bound, never interpolated."""
    s = _SpySession()
    apply_allowed_labels(s.as_session(), ["obi-general", "toast-to-pms"])
    sql, params = s.calls[0]
    assert sql == "SELECT set_config('app.allowed_labels', :s, true)"
    assert params == {"s": "obi-general,toast-to-pms"}
    assert "toast-to-pms" not in sql


def test_sec_apply_allowed_labels_none_opts_out_with_wildcard() -> None:
    """panel mi-hardfilter · substep 9.4.1
    ``None`` (legacy / parent-expansion path) binds the '*' opt-out sentinel, not a real filter."""
    s = _SpySession()
    apply_allowed_labels(s.as_session(), None)
    sql, params = s.calls[0]
    assert sql == "SELECT set_config('app.allowed_labels', :s, true)"
    assert params == {"s": "*"}
