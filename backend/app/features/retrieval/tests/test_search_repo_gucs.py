"""Unit tests for the per-transaction pgvector-and-RLS GUC helpers (panel r2-gucs).

``SET LOCAL`` cannot bind parameters, so ``apply_hnsw_gucs`` validates its inputs instead of
binding them: valid values are emitted verbatim, and an out-of-whitelist ``iterative_scan`` —
including an injection attempt — degrades to ``relaxed_order`` rather than reaching the SQL
string. ``apply_source_scope`` and ``apply_knowledge_scope`` set the RLS scope GUCs via
``set_config`` with a **bound** parameter instead, because interpolating a caller-controlled
source or scope list would be an injection vector; these tests pin that the SQL text always
carries the ``:s`` placeholder (never the value) while the value travels in the bound params.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from app.features.retrieval.infrastructure.search_repo import (
    apply_hnsw_gucs,
    apply_knowledge_scope,
    apply_source_scope,
)


class _SpySession:
    """A stand-in for Session that records the SQL text and bound params passed to ``execute``."""

    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[Any] = []

    def execute(self, clause: Any, params: Any = None, *args: Any, **kwargs: Any) -> None:
        self.statements.append(str(clause))
        self.params.append(params)
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


def test_r2_gucs_source_scope_uses_bound_param_not_interpolated() -> None:
    """panel r2-gucs · substep p0-s0_5-reg-retrieval-stage-2
    Sources: SELECT set_config('app.allowed_sources', :s, true) — the value is bound, never
    interpolated into the SQL text."""
    s = _SpySession()
    apply_source_scope(s.as_session(), ["mews", "toast"])
    assert s.statements == ["SELECT set_config('app.allowed_sources', :s, true)"]
    assert s.params == [{"s": "mews,toast"}]
    assert "mews" not in s.statements[0]
    assert "toast" not in s.statements[0]


def test_r2_gucs_source_scope_empty_list_binds_empty_string() -> None:
    """panel r2-gucs · substep p0-s0_5-reg-retrieval-stage-2
    An empty allowed-sources list binds an empty string, not a wildcard — the RESTRICTIVE
    policy then matches nothing (default-deny / fail closed)."""
    s = _SpySession()
    apply_source_scope(s.as_session(), [])
    assert s.statements == ["SELECT set_config('app.allowed_sources', :s, true)"]
    assert s.params == [{"s": ""}]


def test_r2_gucs_knowledge_scope_uses_bound_param_not_interpolated() -> None:
    """panel r2-gucs · substep p0-s0_5-reg-retrieval-stage-2
    Scopes: SELECT set_config('app.allowed_knowledge_scopes', :k, true) — the value is bound,
    never interpolated into the SQL text."""
    s = _SpySession()
    apply_knowledge_scope(s.as_session(), ["obi-mews-test", "obi-toast-test"])
    assert s.statements == ["SELECT set_config('app.allowed_knowledge_scopes', :s, true)"]
    assert s.params == [{"s": "obi-mews-test,obi-toast-test"}]
    assert "obi-mews-test" not in s.statements[0]


def test_r2_gucs_knowledge_scope_none_binds_wildcard() -> None:
    """panel r2-gucs · substep p0-s0_5-reg-retrieval-stage-2
    ``allowed_scopes=None`` (the internal/eval opt-out) binds the '*' wildcard rather than
    leaving the GUC unset."""
    s = _SpySession()
    apply_knowledge_scope(s.as_session(), None)
    assert s.statements == ["SELECT set_config('app.allowed_knowledge_scopes', :s, true)"]
    assert s.params == [{"s": "*"}]


def test_r2_gucs_knowledge_scope_empty_list_binds_empty_string_not_wildcard() -> None:
    """panel r2-gucs · substep p0-s0_5-reg-retrieval-stage-2
    An empty (but not ``None``) allowed-scopes list binds an empty string, distinct from the
    ``'*'`` wildcard — the RESTRICTIVE policy then matches nothing (default-deny / fail closed)."""
    s = _SpySession()
    apply_knowledge_scope(s.as_session(), [])
    assert s.statements == ["SELECT set_config('app.allowed_knowledge_scopes', :s, true)"]
    assert s.params == [{"s": ""}]
