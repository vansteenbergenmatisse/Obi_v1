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
"""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once
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
