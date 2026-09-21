"""Regression test for panel tg-retag ("Tags updated without a re-embed"), substep 0.5.2.

A label-only re-sync (Confluence sends a label change with no other page edit, no version bump)
must touch exactly the panel's named surfaces -- `page_source.tags`, chunk `tags`, `labels_hash`,
`last_indexed_at` (the panel's "scope_state" is this same tags/labels state, materialized on
`page_source.tags` and `chunk.tags`; there is no separate `scope_state` column in the schema) --
and must leave every other surface untouched: no re-embed (`Chunk.embedding` byte-identical), no
new `document_version` row, no pointer swap (`active_doc_version_id` unchanged), and the body
hashes (`content_hash`/`structure_hash`) unchanged, confirming the body was never touched either.

Not duplicated here: `test_knowledge_scope.py` covers `resolve_knowledge_scope_tags` in isolation
(pure function, no sync path); `test_scope_resolver.py` covers folder/space roots (unrelated);
`test_knowledge_scope_backfill.py` covers an already-tagged corpus's retrieval readiness, not this
transition. `test_scope_tagging_change.py` (panel tg-change) and `test_scope_tagging_add.py`
(panel tg-add) already prove the "no rebuild" outcome via the `active_doc_version_id` proxy; this
file is the fuller, more precise version for tg-retag -- it enumerates every touched and untouched
surface the panel names, not just that one proxy.
"""

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


def test_tg_retag_metadata_only_touches_tags_and_scope_state_not_version_or_embeddings(
    gateway, settings
):
    """panel tg-retag · substep 0.5.2
    On a label-only change, only page_source.tags, chunk.tags, scope_state (the same tags/labels
    state), labels_hash and last_indexed_at change; embeddings, document_version and
    active_doc_version_id stay untouched -- no re-embed, no new version, no pointer swap."""
    # Page 3002 ("Mews PMS Sync Setup") carries the fixture label "obi-mews-test".
    index_page(gateway, settings, 3002, version=1)

    with read() as s:
        ps_before = s.get(PageSource, 3002)
        assert ps_before is not None
        tags_before = list(ps_before.tags)
        labels_hash_before = ps_before.labels_hash
        last_indexed_at_before = ps_before.last_indexed_at
        active_doc_version_id_before = ps_before.active_doc_version_id
        content_hash_before = ps_before.content_hash
        structure_hash_before = ps_before.structure_hash

    assert tags_before == ["obi-mews-test"]
    assert active_doc_version_id_before is not None

    version_before = active_version(3002)
    assert version_before is not None and version_before.id == active_doc_version_id_before
    versions_count_before = count_versions(3002)

    chunks_before = active_child_chunks(3002)
    assert chunks_before, "expected active chunks after first index"
    embeddings_before = {
        c.id: (list(c.embedding) if c.embedding is not None else None) for c in chunks_before
    }
    chunk_ids_before = {c.id for c in chunks_before}
    assert all(chunk.tags == ["obi-mews-test"] for chunk in chunks_before)

    # Label-only change: same body, same version, only the recognized label swaps.
    gateway.set_labels(3002, ["obi-toast-test"])
    enqueue_sync(3002, 1, key="sync:3002:retag")
    result = run_once(gateway, settings, owner="test")

    assert result is not None
    outcome = result.outcome
    assert isinstance(outcome, SyncOutcome)
    assert outcome.action == "metadata_only"

    with read() as s:
        ps_after = s.get(PageSource, 3002)
        assert ps_after is not None
        tags_after = list(ps_after.tags)
        labels_hash_after = ps_after.labels_hash
        last_indexed_at_after = ps_after.last_indexed_at
        active_doc_version_id_after = ps_after.active_doc_version_id
        content_hash_after = ps_after.content_hash
        structure_hash_after = ps_after.structure_hash

    # --- touched surfaces (panel: page_source.tags, chunk.tags, scope_state, labels_hash,
    # last_indexed_at) ---
    assert tags_after == ["obi-toast-test"]  # page_source.tags changed to the new resolved value
    assert tags_after != tags_before
    assert labels_hash_after != labels_hash_before  # labels_hash changed
    assert last_indexed_at_after is not None
    assert last_indexed_at_before is not None
    assert last_indexed_at_after > last_indexed_at_before  # last_indexed_at advanced

    chunks_after = active_child_chunks(3002)
    assert chunks_after
    assert {c.id for c in chunks_after} == chunk_ids_before  # same chunk rows, no rebuild
    # scope_state (the tags/labels state materialized on the chunks) reflects the change
    assert all(chunk.tags == ["obi-toast-test"] for chunk in chunks_after)

    # --- untouched surfaces (panel: embeddings, document_version, active_doc_version_id) ---
    assert active_doc_version_id_after == active_doc_version_id_before  # no pointer swap
    assert count_versions(3002) == versions_count_before  # no new document_version row inserted
    embeddings_after = {
        c.id: (list(c.embedding) if c.embedding is not None else None) for c in chunks_after
    }
    assert embeddings_after == embeddings_before  # every active chunk's embedding is byte-identical
    assert content_hash_after == content_hash_before  # body hash unchanged -> body never touched
    assert structure_hash_after == structure_hash_before
