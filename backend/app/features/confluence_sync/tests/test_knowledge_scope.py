"""Pure unit tests for label -> knowledge-scope tag resolution (PLAN 10.2) — no DB, no gateway.

Post-D4 (substep 2.2.4, §13 step 3): there is no conflict concept. Two or more recognized provider
labels on one page is legitimate sharing — the page resolves to *all* matched recognized tags, and
is later made visible in each of those scopes by plain overlap. `matched_labels` and `tags` are the
same recognized set here (the resolver no longer zeroes anything)."""

from __future__ import annotations

import pytest

from app.features.confluence_sync.domain.knowledge_scope import resolve_knowledge_scope_tags

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

RECOGNIZED = frozenset(
    {"obi-general-test", "obi-mews-test", "obi-operacloud-test", "obi-toast-test"}
)


def test_recognized_label_becomes_a_tag():
    result = resolve_knowledge_scope_tags(["obi-mews-test"], RECOGNIZED)
    assert result.tags == ("obi-mews-test",)
    assert result.matched_labels == ("obi-mews-test",)


def test_unrecognized_label_is_ignored():
    result = resolve_knowledge_scope_tags(["some-other-label"], RECOGNIZED)
    assert result.tags == ()
    assert result.matched_labels == ()


def test_general_plus_one_provider_label_yields_both_tags():
    result = resolve_knowledge_scope_tags(["obi-general-test", "obi-mews-test"], RECOGNIZED)
    assert result.tags == ("obi-general-test", "obi-mews-test")
    assert result.matched_labels == ("obi-general-test", "obi-mews-test")


def test_two_provider_labels_share_both_scopes_mews_and_opera_cloud():
    # Post-D4: two provider labels is sharing, not a conflict — the page resolves to both tags.
    result = resolve_knowledge_scope_tags(["obi-mews-test", "obi-operacloud-test"], RECOGNIZED)
    assert result.tags == ("obi-mews-test", "obi-operacloud-test")
    assert result.matched_labels == ("obi-mews-test", "obi-operacloud-test")


def test_two_provider_labels_share_both_scopes_mews_and_toast():
    # dedicated case: `obi-toast-test` echoes this repo's own codename (ADR-0006/ADR-0011) — must
    # resolve as a normal shared provider scope, not be treated specially/ignored.
    result = resolve_knowledge_scope_tags(["obi-mews-test", "obi-toast-test"], RECOGNIZED)
    assert result.tags == ("obi-mews-test", "obi-toast-test")
    assert result.matched_labels == ("obi-mews-test", "obi-toast-test")


def test_empty_labels_yield_empty_result():
    result = resolve_knowledge_scope_tags([], RECOGNIZED)
    assert result.tags == ()
    assert result.matched_labels == ()


def test_labels_are_trimmed_and_lowercased_before_matching():
    result = resolve_knowledge_scope_tags([" Obi-Mews-Test ", "OBI-TOAST-TEST"], RECOGNIZED)
    assert result.tags == ("obi-mews-test", "obi-toast-test")
    assert result.matched_labels == ("obi-mews-test", "obi-toast-test")
