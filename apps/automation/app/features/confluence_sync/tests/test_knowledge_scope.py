"""Pure unit tests for label -> knowledge-scope tag resolution (PLAN 10.2) — no DB, no gateway."""

from __future__ import annotations

from app.features.confluence_sync.domain.knowledge_scope import resolve_knowledge_scope_tags

RECOGNIZED = frozenset(
    {"obi-general-test", "obi-mews-test", "obi-operacloud-test", "obi-toast-test"}
)


def test_recognized_label_becomes_a_tag():
    result = resolve_knowledge_scope_tags(["obi-mews-test"], RECOGNIZED)
    assert result.tags == ("obi-mews-test",)
    assert result.conflict is False
    assert result.matched_labels == ("obi-mews-test",)


def test_unrecognized_label_is_ignored():
    result = resolve_knowledge_scope_tags(["some-other-label"], RECOGNIZED)
    assert result.tags == ()
    assert result.conflict is False
    assert result.matched_labels == ()


def test_general_plus_one_provider_label_yields_both_tags_no_conflict():
    result = resolve_knowledge_scope_tags(["obi-general-test", "obi-mews-test"], RECOGNIZED)
    assert result.tags == ("obi-general-test", "obi-mews-test")
    assert result.conflict is False
    assert result.matched_labels == ("obi-general-test", "obi-mews-test")


def test_two_provider_labels_conflict_mews_and_opera_cloud():
    result = resolve_knowledge_scope_tags(["obi-mews-test", "obi-operacloud-test"], RECOGNIZED)
    assert result.tags == ()
    assert result.conflict is True
    assert result.matched_labels == ("obi-mews-test", "obi-operacloud-test")


def test_two_provider_labels_conflict_mews_and_toast():
    # dedicated case: `obi-toast-test` echoes this repo's own codename (ADR-0006/ADR-0011) — must
    # still resolve as a normal provider-label conflict, not be treated specially/ignored.
    result = resolve_knowledge_scope_tags(["obi-mews-test", "obi-toast-test"], RECOGNIZED)
    assert result.tags == ()
    assert result.conflict is True
    assert result.matched_labels == ("obi-mews-test", "obi-toast-test")


def test_empty_labels_yield_empty_result():
    result = resolve_knowledge_scope_tags([], RECOGNIZED)
    assert result.tags == ()
    assert result.conflict is False
    assert result.matched_labels == ()


def test_labels_are_trimmed_and_lowercased_before_matching():
    result = resolve_knowledge_scope_tags([" Obi-Mews-Test ", "OBI-TOAST-TEST"], RECOGNIZED)
    assert result.tags == ()
    assert result.conflict is True
    assert result.matched_labels == ("obi-mews-test", "obi-toast-test")
