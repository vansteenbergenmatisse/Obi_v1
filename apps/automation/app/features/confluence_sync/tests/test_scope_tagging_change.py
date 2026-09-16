"""Regression test for panel tg-change ("Change a label"), substep 0.5.2.

An editor swaps one recognized label for another on an already-indexed page (Confluence sends
label_deleted then label_added, no body change). The worker reads the current label set fresh
on every sync (`resolve_knowledge_scope_tags` in `handle_sync_page`), so the page's tags must
converge to exactly the new tag with the old one gone -- never both at once -- and this is a
metadata-only change: no rebuild (the active document_version does not change).

Not duplicated here: `test_knowledge_scope.py` covers `resolve_knowledge_scope_tags` in isolation;
`test_scope_resolver.py` covers folder/space roots; `test_knowledge_scope_backfill.py` covers an
already-tagged corpus. This file is the only one exercising the real sync path for a label swap.
"""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once
from app.platform.db.models import PageSource

from ._helpers import active_version, enqueue_sync, index_page, read

pytestmark = pytest.mark.db


def test_tg_change_label_swap_leaves_no_stale_double_tag(gateway, settings):
    """panel tg-change · substep 0.5.2
    A label swap (mews -> toast) converges to exactly the new tag, with the old tag gone and
    no rebuild (same active document_version)."""
    gateway.set_labels(1001, ["obi-mews-test"])
    index_page(gateway, settings, 1001, version=1)

    with read() as s:
        page_source = s.get(PageSource, 1001)
        assert page_source is not None
        assert page_source.tags == ["obi-mews-test"]
    version_before_row = active_version(1001)
    assert version_before_row is not None
    version_before = version_before_row.id

    gateway.set_labels(1001, ["obi-toast-test"])  # label swap; same page content, no version bump
    enqueue_sync(1001, 1, key="sync:1001:label-swap")
    result = run_once(gateway, settings, owner="test")

    assert result is not None
    outcome = result.outcome
    assert isinstance(outcome, SyncOutcome)
    assert outcome.action == "metadata_only"
    with read() as s:
        page_source = s.get(PageSource, 1001)
        assert page_source is not None
        assert page_source.tags == ["obi-toast-test"]  # old tag gone, no double-tag
    version_after_row = active_version(1001)
    assert version_after_row is not None
    assert version_after_row.id == version_before  # metadata-only: no rebuild
