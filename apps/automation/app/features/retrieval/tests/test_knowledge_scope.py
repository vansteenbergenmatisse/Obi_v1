"""PLAN 10.4: resolving a request-shaped scope value into the allowed-scopes set used to filter
retrieval. Pure and co-located with `permission.classify_scope`, which already plays this
"interpret an incoming request-shaped value" role for `principal` (PLAN 4.6.6).
"""

from __future__ import annotations

from app.features.retrieval.domain.knowledge_scope import resolve_allowed_scopes

_RECOGNIZED = frozenset({"general", "mews", "opera-cloud", "toast"})


def test_no_request_or_default_returns_general_only() -> None:
    assert resolve_allowed_scopes(None, _RECOGNIZED, None) == ["general"]


def test_recognized_requested_scope_is_added_to_general() -> None:
    assert resolve_allowed_scopes("mews", _RECOGNIZED, None) == ["general", "mews"]


def test_requested_scope_matching_is_case_insensitive() -> None:
    assert resolve_allowed_scopes("MEWS", _RECOGNIZED, None) == ["general", "mews"]


def test_unrecognized_requested_scope_degrades_to_default() -> None:
    assert resolve_allowed_scopes("unknown-platform", _RECOGNIZED, "toast") == ["general", "toast"]


def test_unrecognized_requested_scope_with_no_default_degrades_to_general_only() -> None:
    assert resolve_allowed_scopes("unknown-platform", _RECOGNIZED, None) == ["general"]


def test_no_requested_scope_falls_back_to_default() -> None:
    assert resolve_allowed_scopes(None, _RECOGNIZED, "opera-cloud") == ["general", "opera-cloud"]


def test_unrecognized_default_is_ignored() -> None:
    assert resolve_allowed_scopes(None, _RECOGNIZED, "not-a-real-scope") == ["general"]


def test_result_is_sorted() -> None:
    assert resolve_allowed_scopes("toast", _RECOGNIZED, None) == ["general", "toast"]
