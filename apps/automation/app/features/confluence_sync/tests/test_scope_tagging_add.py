"""Regression test for panel tg-add ("Add a label"), substep 0.5.2.

An editor adds a Confluence label to an already-indexed page, alongside whatever labels it
already carried (Confluence sends label_added; the page version does not change). The worker
re-resolves the full current label set on every sync (`resolve_knowledge_scope_tags` in
`handle_sync_page`), so the newly-recognized tag must land on `page_source.tags` -- and because
`ChangeClass.labels_changed` alone is not in `_REBUILD_CLASSES` (`sync_service.py`), this must be
a metadata-only update: the active `document_version` is never rebuilt for a label-only change.

Not duplicated here: `test_knowledge_scope.py` covers `resolve_knowledge_scope_tags` in isolation
(pure function, no sync path); `test_scope_resolver.py` covers folder/space roots (unrelated);
`test_knowledge_scope_backfill.py` covers an already-tagged corpus's retrieval readiness, not this
add transition. `test_scope_tagging_first.py` covers the first-index case and
`test_scope_tagging_change.py` covers swapping one recognized label for another; this file is the
only one exercising an add-alongside-the-existing-label transition on an already-indexed page.

The panel's second acceptance line -- "the page appears in the new scope's results on the next
question" -- is proven here too, end to end through the real sync path (`test_tg_add_...
makes_page_appear_in_new_scope_on_next_question`). `test_retrieval_knowledge_scope.py` proves the
retrieval-side predicate alone by stamping `chunk.tags` directly via SQL and never runs a label
through the sync worker, so it does not cover the add-label -> chunk.tags propagation this panel
requires.
"""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once
from app.features.retrieval import HybridRetriever, PrincipalPermissionPolicy
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings
from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker
from app.platform.db.models import PageSource

from ._helpers import active_version, enqueue_sync, index_page, read

pytestmark = pytest.mark.db


def test_tg_add_label_only_change_updates_tags_without_rebuild(gateway, settings):
    """panel tg-add · substep 0.5.2
    Adding a new recognized label to an already-indexed page (no other content change) updates
    its knowledge-scope tags in place without re-embedding: active_doc_version_id is unchanged."""
    # page 1001 starts with only its fixture labels (onboarding/engineering/guide), none recognized.
    gateway.set_labels(1001, ["onboarding"])
    index_page(gateway, settings, 1001, version=1)

    with read() as s:
        page_source = s.get(PageSource, 1001)
        assert page_source is not None
        assert page_source.tags == []  # no recognized tag yet
    version_before_row = active_version(1001)
    assert version_before_row is not None
    version_before = version_before_row.id

    # ADD a new label alongside the existing one; same page content, no version bump.
    gateway.set_labels(1001, ["onboarding", "obi-mews-test"])
    enqueue_sync(1001, 1, key="sync:1001:label-add")
    result = run_once(gateway, settings, owner="test")

    assert result is not None
    outcome = result.outcome
    assert isinstance(outcome, SyncOutcome)
    assert outcome.action == "metadata_only"
    with read() as s:
        page_source = s.get(PageSource, 1001)
        assert page_source is not None
        assert "obi-mews-test" in page_source.tags  # new tag now present
    version_after_row = active_version(1001)
    assert version_after_row is not None
    assert version_after_row.id == version_before  # metadata-only: no rebuild


def _retriever(settings: Settings) -> HybridRetriever:
    return HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
        enable_knowledge_scope_filtering=True,
        trace_sessionmaker=get_sessionmaker(),
    )


def test_tg_add_label_only_change_makes_page_appear_in_new_scope_on_next_question(
    gateway, settings
):
    """panel tg-add · substep 0.5.2
    The page appears in the new scope's results on the next question: adding a recognized label
    to an already-indexed page, alongside its existing labels, makes it resolve under a retrieval
    query scoped to the new tag -- without any re-embed (metadata-only propagates chunk.tags too,
    per `_apply_metadata_only` in sync_service.py)."""
    gateway.set_labels(1001, ["onboarding"])
    index_page(gateway, settings, 1001, version=1)
    retr = _retriever(settings)

    # Before the add: no recognized scope tag on the page's chunks, so a query scoped to
    # obi-mews-test never resolves it (ADR-0011 Decision 1: no tag -> no participation).
    before = retr.retrieve("Onboarding Guide", "100", k=5, knowledge_scopes=["obi-mews-test"])
    assert "1001" not in before

    # ADD a new label alongside the existing one; same page content, no version bump.
    gateway.set_labels(1001, ["onboarding", "obi-mews-test"])
    enqueue_sync(1001, 1, key="sync:1001:label-add-retrieval")
    result = run_once(gateway, settings, owner="test")

    assert result is not None
    outcome = result.outcome
    assert isinstance(outcome, SyncOutcome)
    assert outcome.action == "metadata_only"
    after = retr.retrieve("Onboarding Guide", "100", k=5, knowledge_scopes=["obi-mews-test"])
    assert "1001" in after  # the page is now searchable in its new scope, on the next question
