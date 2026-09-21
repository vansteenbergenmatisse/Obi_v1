"""First-index knowledge-scope tagging: the tag is already resolved on the very first sync."""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once
from schema.models import PageSource

from ._helpers import (
    active_child_chunks,
    active_version,
    count_versions,
    enqueue_sync,
    index_page,
    read,
)

pytestmark = pytest.mark.db


def test_tg_first_page_indexed_with_tags_already_resolved(gateway, settings):
    """panel tg-first · substep 0.5.2
    A first build creates document, version, chunks, and activates them with the label tags:
    a brand-new page (never seen before) carrying a Confluence label that maps to a known
    knowledge-scope tag must already carry that resolved tag on `page_source.tags` and on its
    active chunks after the one and only sync — not indexed bare and tagged in a later pass.
    """
    # page 3002 ("Mews PMS Sync Setup") is fresh to this test module and carries the Confluence
    # label "obi-mews-test", which config/knowledge_scopes.json recognizes as a knowledge-scope tag.
    index_page(gateway, settings, 3002, version=1)

    with read() as s:
        page_source = s.get(PageSource, 3002)
        assert page_source is not None
        assert "obi-mews-test" in page_source.tags

    chunks = active_child_chunks(3002)
    assert chunks and all("obi-mews-test" in c.tags for c in chunks)


def test_tg_first_later_label_after_first_build_is_metadata_only(gateway, settings):
    """panel tg-first · substep p0-s0_5-reg-knowledge-scopes
    A later label on an indexed page is a metadata-only update: once a first build has already
    indexed and tagged the page, a subsequent label change on that same page (no other content
    change, no version bump) creates no new document_version row and leaves the active version
    pointer unchanged."""
    # page 3004 ("Toast POS Menu Sync") is fresh to this test module and carries the fixture
    # label "obi-toast-test" on its very first sync.
    index_page(gateway, settings, 3004, version=1)

    with read() as s:
        page_source = s.get(PageSource, 3004)
        assert page_source is not None
        assert "obi-toast-test" in page_source.tags

    version_before = active_version(3004)
    assert version_before is not None
    versions_count_before = count_versions(3004)

    # A LATER label change on the already-indexed page: same body, same Confluence version.
    gateway.set_labels(3004, ["obi-general-test"])
    enqueue_sync(3004, 1, key="sync:3004:later-label")
    result = run_once(gateway, settings, owner="test")

    assert result is not None
    outcome = result.outcome
    assert isinstance(outcome, SyncOutcome)
    assert outcome.action == "metadata_only"

    with read() as s:
        page_source_after = s.get(PageSource, 3004)
        assert page_source_after is not None
        assert "obi-general-test" in page_source_after.tags

    version_after = active_version(3004)
    assert version_after is not None
    assert version_after.id == version_before.id  # active version pointer unchanged
    assert count_versions(3004) == versions_count_before  # no new document_version row
