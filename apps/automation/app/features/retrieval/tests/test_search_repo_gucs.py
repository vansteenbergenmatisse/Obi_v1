"""Unit tests for the per-transaction pgvector HNSW GUC helper.

``SET LOCAL`` cannot bind parameters, so the helper validates its inputs instead of binding
them. These tests pin that contract with a spy session (no database needed): valid values are
emitted verbatim, and an out-of-whitelist ``iterative_scan`` — including an injection attempt —
degrades to ``relaxed_order`` rather than reaching the SQL string.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.features.retrieval.infrastructure.search_repo import apply_hnsw_gucs


class _SpySession:
    """A stand-in for Session that records the SQL text passed to ``execute``."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, clause: Any, *args: Any, **kwargs: Any) -> None:
        self.statements.append(str(clause))
        return None

    def as_session(self) -> Session:
        return cast(Session, self)


def test_emits_both_gucs_with_valid_values() -> None:
    s = _SpySession()
    apply_hnsw_gucs(s.as_session(), ef_search=100, iterative_scan="relaxed_order")
    assert s.statements == [
        "SET LOCAL hnsw.ef_search = 100",
        "SET LOCAL hnsw.iterative_scan = 'relaxed_order'",
    ]


def test_ef_search_is_coerced_to_int() -> None:
    s = _SpySession()
    apply_hnsw_gucs(s.as_session(), ef_search=250, iterative_scan="strict_order")
    assert s.statements[0] == "SET LOCAL hnsw.ef_search = 250"
    assert s.statements[1] == "SET LOCAL hnsw.iterative_scan = 'strict_order'"


def test_unknown_scan_mode_falls_back_to_relaxed_order() -> None:
    s = _SpySession()
    apply_hnsw_gucs(s.as_session(), ef_search=100, iterative_scan="turbo")
    assert s.statements[1] == "SET LOCAL hnsw.iterative_scan = 'relaxed_order'"


def test_injection_attempt_never_reaches_sql() -> None:
    s = _SpySession()
    apply_hnsw_gucs(s.as_session(), ef_search=100, iterative_scan="off'; DROP TABLE chunk; --")
    # The malicious string is not in the whitelist, so it degrades — no DROP reaches the SQL.
    assert s.statements[1] == "SET LOCAL hnsw.iterative_scan = 'relaxed_order'"
    assert "DROP TABLE" not in s.statements[1]
