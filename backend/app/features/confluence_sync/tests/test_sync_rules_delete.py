"""Sync rules 1, 1b and 7 — delete/trash/archive and the classified label remove a page's rows
outright (not soft-deactivate), and a delete followed by a restore rebuilds the page from scratch.

Substep 2.2.4 (the sync-rules §13 series, step 1). Panels: i2-gone, tg-purge, tg-classified.
Assertions are outcomes only — row counts and re-embed counts — never code paths."""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once

from ._helpers import (
    active_child_chunks,
    active_version,
    enqueue_delete,
    enqueue_sync,
    index_page,
    install_counting_embedder,
    page_row_counts,
    read,
    run_worker,
)

pytestmark = pytest.mark.db


def test_in2_delete_page_removes_rows(gateway, settings):
    """panel i2-gone · rule 1
    Delete/trash/archive a page: every row it owns — chunk, document_version, document,
    page_source, page_restriction — is gone, not merely inactive."""
    index_page(gateway, settings, 1001, version=3)
    assert active_child_chunks(1001)  # indexed with live chunks first

    enqueue_delete(1001, "trashed", key="del:1001")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "purged"
    assert page_row_counts(1001) == {
        "chunk": 0,
        "document_version": 0,
        "document": 0,
        "page_source": 0,
        "page_restriction": 0,
    }


def test_in2_delete_then_restore_full_rebuilds(gateway, settings, monkeypatch):
    """panel i2-gone · rule 1b
    Restoring a purged page re-indexes it from Confluence as a first index: a fresh version, every
    child re-embedded, and the page retrievable again."""
    index_page(gateway, settings, 1001, version=3)

    enqueue_delete(1001, "trashed", key="del:1001:restore")
    run_once(gateway, settings, owner="test")
    assert page_row_counts(1001)["page_source"] == 0  # purged: nothing to reactivate

    # Restore: with page_source gone, the next sync sees no local state -> first-index full build.
    counter = install_counting_embedder(monkeypatch, settings)
    enqueue_sync(1001, cf_version=3, key="restore:1001")
    run_worker(gateway, settings, owner="test")

    restored = active_child_chunks(1001)
    assert restored  # retrievable again
    assert active_version(1001) is not None  # a fresh active version exists
    assert counter.texts == len(restored)  # every child re-embedded, none reused


def test_in2_classified_label_removes_rows(gateway, settings):
    """panel tg-classified · rule 7
    Adding the reserved classified label removes every row of the page on the next sync, whatever
    other recognized tags it still carries."""
    index_page(gateway, settings, 1001, version=3)
    assert active_child_chunks(1001)

    # classified wins even alongside a valid recognized scope.
    gateway.set_labels(1001, ["obi-general-test", "classified"])
    enqueue_sync(1001, cf_version=3, key="classify:1001")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "purged"
    assert page_row_counts(1001) == {
        "chunk": 0,
        "document_version": 0,
        "document": 0,
        "page_source": 0,
        "page_restriction": 0,
    }
    with read() as s:
        from schema.models import PageSource

        assert s.get(PageSource, 1001) is None
