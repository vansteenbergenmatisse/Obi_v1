"""Token counter invariants — provider-agnostic (pass under tiktoken or the heuristic fallback)."""

from __future__ import annotations

from app.features.ingestion.domain.tokenization import TokenCounter

TC = TokenCounter()

LOREM = (
    "The onboarding guide explains how to request access to core systems when you join. "
    "It covers SSO enrollment, VPN setup, and the development environment bootstrap. "
) * 40  # long enough to force multiple windows


def test_empty_and_whitespace_count_zero() -> None:
    assert TC.count("") == 0
    assert TC.count("   \n\t ") == 0


def test_count_is_positive_and_monotonic() -> None:
    short = TC.count("hello world")
    longer = TC.count("hello world " * 20)
    assert short > 0
    assert longer > short


def test_split_windows_never_exceed_max() -> None:
    max_tokens = 50
    windows = TC.split(LOREM, max_tokens=max_tokens, overlap_tokens=10)
    assert len(windows) > 1
    assert all(w.strip() for w in windows)
    assert all(TC.count(w) <= max_tokens for w in windows)


def test_split_short_text_returns_single_window() -> None:
    text = "just a short paragraph"
    assert TC.split(text, max_tokens=100) == [text]


def test_split_empty_returns_empty_list() -> None:
    assert TC.split("", max_tokens=100) == []


def test_split_covers_all_words_when_no_overlap() -> None:
    windows = TC.split(LOREM, max_tokens=40, overlap_tokens=0)
    joined_words = " ".join(windows).split()
    assert joined_words == LOREM.split()


def test_split_rejects_overlap_ge_max() -> None:
    # overlap must be strictly less than max or windows can't advance
    try:
        TC.split(LOREM, max_tokens=20, overlap_tokens=20)
    except ValueError:
        return
    raise AssertionError("expected ValueError for overlap >= max_tokens")
