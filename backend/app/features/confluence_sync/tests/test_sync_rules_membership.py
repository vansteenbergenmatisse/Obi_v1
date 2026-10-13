"""Sync rule 2 + label-gated membership (substep 2.2.4, §13 step 2). A page belongs in the index
only while it carries at least one recognized knowledge-scope label. Removing the last recognized
label removes every row (rule 2, same outcome as delete/classified); a first-seen page with no
recognized label is never ingested (never-bend rule 5). Unrelated Confluence labels and folder
roots (source_scope) no longer keep a page in.

Panels: tg-remove, ks-index. Assertions are outcomes only — row counts and the sync action —
never code paths."""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once

from ._helpers import (
    active_child_chunks,
    active_version,
    enqueue_sync,
    index_page,
    install_counting_embedder,
    page_row_counts,
    read,
)

pytestmark = pytest.mark.db

_ZERO_ROWS = {
    "chunk": 0,
    "document_version": 0,
    "document": 0,
    "page_source": 0,
    "page_restriction": 0,
}

# Fixture pages with a single recognized knowledge-scope label (knowledge_scopes.json).
_MEWS_PAGE = 3002  # mews-general
# Fixture page carrying no label at all (page-3007-unlabeled.json).
_UNLABELED_PAGE = 3007


def test_tags_remove_last_recognized_label_removes_rows(gateway, settings):
    """panel tg-remove · rule 2
    An indexed page whose last recognized knowledge-scope label is removed has every row it owns
    deleted — not merely deactivated — exactly like a delete or the classified label."""
    index_page(gateway, settings, _MEWS_PAGE, version=1)
    assert active_child_chunks(_MEWS_PAGE)  # indexed with live chunks first

    gateway.set_labels(_MEWS_PAGE, [])  # editor strips the last recognized label
    enqueue_sync(_MEWS_PAGE, cf_version=1, key="unlabel:3002")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "purged"
    assert page_row_counts(_MEWS_PAGE) == _ZERO_ROWS


def test_tags_unrelated_labels_alone_do_not_keep_page(gateway, settings):
    """panel tg-remove · rule 2
    Replacing every recognized label with unrelated Confluence labels (folder-root leftovers,
    housekeeping tags) removes the page: unrelated labels never keep a page in the index."""
    index_page(gateway, settings, _MEWS_PAGE, version=1)
    assert active_child_chunks(_MEWS_PAGE)

    gateway.set_labels(_MEWS_PAGE, ["onboarding", "engineering", "guide"])
    enqueue_sync(_MEWS_PAGE, cf_version=1, key="only-unrelated:3002")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "purged"
    assert page_row_counts(_MEWS_PAGE) == _ZERO_ROWS


def test_in2_untagged_page_never_indexed(gateway, settings):
    """panel ks-index · rule 5 / membership
    A first-seen page that carries no recognized knowledge-scope label is never ingested: no
    version, no chunk, no page_source row. Folder roots (source_scope) do not make it a member."""
    # Seed straight through the worker (not index_page, which would inject a base label): the page
    # must be judged on its own unlabeled state.
    gateway.set_version(_UNLABELED_PAGE, 1)
    enqueue_sync(_UNLABELED_PAGE, cf_version=1, key="firstseen:3007")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "skipped"
    assert page_row_counts(_UNLABELED_PAGE) == _ZERO_ROWS
    with read() as s:
        from schema.models import PageSource

        assert s.get(PageSource, _UNLABELED_PAGE) is None


def test_in2_first_relevant_tag_full_build(gateway, settings, monkeypatch):
    """panel ks-index · rule 5
    A first-seen page that gains its first recognized knowledge-scope label is fully built: a
    version is created and every child chunk is embedded from scratch (embed count == child count),
    none reused. The positive half of label-gated membership — the first relevant tag is what puts
    an untagged page into the index."""
    # Premise: while unlabeled, a first-seen page builds nothing (the negative half, rule 5).
    gateway.set_version(_UNLABELED_PAGE, 1)
    enqueue_sync(_UNLABELED_PAGE, cf_version=1, key="firstseen-unlabeled:3007")
    run_once(gateway, settings, owner="test")
    assert page_row_counts(_UNLABELED_PAGE) == _ZERO_ROWS  # untagged -> nothing built

    # The editor applies the first recognized label: now it must build in full.
    counter = install_counting_embedder(monkeypatch, settings)
    gateway.set_labels(_UNLABELED_PAGE, ["mews-general"])
    enqueue_sync(_UNLABELED_PAGE, cf_version=1, key="firsttag:3007")
    run_once(gateway, settings, owner="test")

    built = active_child_chunks(_UNLABELED_PAGE)
    assert active_version(_UNLABELED_PAGE) is not None  # a fresh active version exists
    assert built  # retrievable in its scope
    assert counter.texts == len(built)  # every child embedded on first build, none reused


def test_tags_recognized_label_present_keeps_page(gateway, settings):
    """panel tg-remove · rule 2 (guard)
    While at least one recognized label remains, adding or dropping unrelated labels never purges
    the page — membership is decided by recognized-label presence, not by any label change."""
    index_page(gateway, settings, _MEWS_PAGE, version=1)
    assert active_child_chunks(_MEWS_PAGE)

    gateway.set_labels(_MEWS_PAGE, ["mews-general", "onboarding", "housekeeping"])
    enqueue_sync(_MEWS_PAGE, cf_version=1, key="keep:3002")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action != "purged"
    assert active_child_chunks(_MEWS_PAGE)  # still retrievable
    assert page_row_counts(_MEWS_PAGE)["page_source"] == 1
