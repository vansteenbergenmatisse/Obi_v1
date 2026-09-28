"""Sync rule 8 — a change to one page never touches another page's rows. Editing and then deleting
page A leaves page B byte-identical: same child chunk ids, embeddings, tags and active version id.

Substep 2.2.4 (the sync-rules §13 series, step 6). Panel: vd-swap. Assertions are outcomes only —
the row identity of the untouched neighbour — never code paths."""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.worker import run_once

from ._helpers import (
    active_child_chunks,
    active_version,
    enqueue_delete,
    enqueue_sync,
    index_page,
    page_row_counts,
    run_worker,
)

pytestmark = pytest.mark.db

_PAGE_A = 1001  # the page that churns (edited, then deleted)
_PAGE_B = 1002  # the neighbour that must not move

_ZERO_ROWS = {
    "chunk": 0,
    "document_version": 0,
    "document": 0,
    "page_source": 0,
    "page_restriction": 0,
}


def _snapshot(page_id: int):
    """An order-independent fingerprint of a page's live child chunks plus its active version id —
    the bytes rule 8 forbids a neighbour's change from moving: chunk identity (stable_key), tags,
    and the embedding vector itself."""
    version = active_version(page_id)
    chunks = active_child_chunks(page_id)
    return (
        version.id if version is not None else None,
        {
            (
                chunk.stable_key,
                tuple(chunk.tags),
                tuple(chunk.embedding) if chunk.embedding is not None else None,
            )
            for chunk in chunks
        },
    )


def test_in2_change_never_touches_other_pages_rows(gateway, settings):
    """panel vd-swap · rule 8
    Editing and then deleting page A leaves page B untouched: B's child chunk ids, embeddings, tags
    and active version id are byte-identical before and after A's churn."""
    index_page(gateway, settings, _PAGE_A, version=1)
    index_page(gateway, settings, _PAGE_B, version=1)
    before = _snapshot(_PAGE_B)
    assert before[0] is not None and before[1]  # B indexed with a version and live chunks

    # Churn A: a body edit (rebuild, retain 0) followed by a delete (full purge).
    gateway.set_version(_PAGE_A, 3)
    enqueue_sync(_PAGE_A, cf_version=3, key="edit:A:1001")
    run_worker(gateway, settings, owner="test")
    enqueue_delete(_PAGE_A, "trashed", key="del:A:1001")
    run_once(gateway, settings, owner="test")
    assert page_row_counts(_PAGE_A) == _ZERO_ROWS  # A fully gone

    assert _snapshot(_PAGE_B) == before  # B unmoved: same version id, chunk ids, tags, embeddings
