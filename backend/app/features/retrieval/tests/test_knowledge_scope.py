"""Resolving a request-shaped scope value into the allowed-scopes set (ADR-0021).

ADR-0021 retired the knowledge-scope axis, so in production the recognized set is EMPTY and this
resolver always returns ``[]`` (no base scope is injected). The function is kept as the single
place that normalises/degrades an incoming request-shaped value; the generic interpret-logic is
still exercised below with a non-empty sample recognized set.
"""

from __future__ import annotations

from app.features.retrieval.domain.knowledge_scope import resolve_allowed_scopes

# Neutral sample scopes — the resolver is generic over whatever recognized set it is handed.
_SAMPLE = frozenset({"scope-a", "scope-b"})


def test_empty_recognized_set_always_returns_empty() -> None:
    """ADR-0021 production reality: with the retired axis there are no recognized scopes, so any
    request resolves to the empty allow-list (no base scope)."""
    assert resolve_allowed_scopes(None, frozenset(), None) == []
    assert resolve_allowed_scopes("scope-a", frozenset(), "scope-b") == []


def test_no_request_or_default_returns_empty() -> None:
    assert resolve_allowed_scopes(None, _SAMPLE, None) == []


def test_recognized_requested_scope_is_returned_without_a_base() -> None:
    assert resolve_allowed_scopes("scope-a", _SAMPLE, None) == ["scope-a"]


def test_requested_scope_matching_is_case_insensitive() -> None:
    assert resolve_allowed_scopes("SCOPE-A", _SAMPLE, None) == ["scope-a"]


def test_unrecognized_requested_scope_degrades_to_default() -> None:
    assert resolve_allowed_scopes("unknown-platform", _SAMPLE, "scope-b") == ["scope-b"]


def test_unrecognized_requested_scope_with_no_default_is_empty() -> None:
    assert resolve_allowed_scopes("unknown-platform", _SAMPLE, None) == []


def test_no_requested_scope_falls_back_to_default() -> None:
    assert resolve_allowed_scopes(None, _SAMPLE, "scope-b") == ["scope-b"]


def test_unrecognized_default_is_ignored() -> None:
    assert resolve_allowed_scopes(None, _SAMPLE, "not-a-real-scope") == []


def test_result_is_sorted() -> None:
    # A recognized requested scope is returned as a one-element sorted list.
    assert resolve_allowed_scopes("scope-b", _SAMPLE, None) == ["scope-b"]
