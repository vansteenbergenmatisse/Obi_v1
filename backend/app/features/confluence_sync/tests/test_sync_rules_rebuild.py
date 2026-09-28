"""Sync rule 6 — an edit rebuilds the whole page and re-embeds every child, reusing no vector, and
the just-superseded version's rows are deleted in the same transaction (retain 0, no rollback).

Substep 2.3.1 (the sync-rules §13 series, step 5). Decisions D1 (retain 0) and D2 (attachments
deferred, strict xfail). Panels: i3-embed, i2-rebuild, i4-gc.
Assertions are outcomes only — re-embed counts and row counts — never code paths."""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.worker import run_once

from ._helpers import (
    active_child_chunks,
    active_version,
    child_chunks_for_version,
    count_versions,
    enqueue_sync,
    index_page,
    install_counting_embedder,
    read,
    run_worker,
)

pytestmark = pytest.mark.db


def test_in3_body_edit_reembeds_every_chunk_no_reuse(gateway, settings, monkeypatch):
    """panel i3-embed · rule 6
    A body edit rebuilds the page and embeds every child afresh — the embedder is called once per
    child, no vector carried over from the old version."""
    index_page(gateway, settings, 1001, version=1)
    assert active_child_chunks(1001)

    counter = install_counting_embedder(monkeypatch, settings)
    gateway.set_version(1001, 3)  # v3 adds a Troubleshooting section: a real body edit
    enqueue_sync(1001, cf_version=3, key="edit:1001:body")
    run_worker(gateway, settings, owner="test")

    after = active_child_chunks(1001)
    assert after  # rebuilt and retrievable
    assert counter.texts == len(after)  # every child re-embedded, none reused


def test_in3_title_change_reembeds_every_chunk(gateway, settings, monkeypatch):
    """panel i2-rebuild · rule 6
    A rename (title changed, body unchanged) triggers a full rebuild that re-embeds every child, so
    no stale title can hide in an old vector."""
    index_page(gateway, settings, 1001, version=1)
    assert active_child_chunks(1001)

    # A title-only edit: a new title and a bumped revision (Confluence bumps version on a rename),
    # the body left unchanged. Substituted on the same gateway instance the real worker drives, so
    # sync_service/classify/stage_and_activate run unmodified.
    real_get_page_meta = gateway.get_page_meta

    def _renamed_meta(page_id: int):
        meta = real_get_page_meta(page_id)
        if meta is None:
            return None
        return meta.model_copy(update={"title": "Renamed Guide", "version_number": 2})

    monkeypatch.setattr(gateway, "get_page_meta", _renamed_meta)

    counter = install_counting_embedder(monkeypatch, settings)
    enqueue_sync(1001, cf_version=2, key="edit:1001:title")
    run_worker(gateway, settings, owner="test")

    after = active_child_chunks(1001)
    assert after
    assert all(c.title == "Renamed Guide" for c in after)  # rebuilt under the new title
    assert counter.texts == len(after)  # a rename re-embeds every child, none reused


def test_in3_rebuild_deletes_old_version_rows_immediately(gateway, settings):
    """panel i4-gc · rule 6 (D1)
    A rebuild deletes the just-superseded version and its chunks in the same transaction — retain 0,
    no rollback window: after one edit only the new active version's rows remain."""
    index_page(gateway, settings, 1001, version=1)
    v1 = active_version(1001)
    assert v1 is not None
    v1_id = v1.id
    assert child_chunks_for_version(v1_id)  # the old version had chunk rows

    gateway.set_version(1001, 3)  # a body edit -> a rebuild
    enqueue_sync(1001, cf_version=3, key="edit:1001:gc")
    run_once(gateway, settings, owner="test")

    # the superseded version and its chunks are gone outright, not merely inactive
    assert child_chunks_for_version(v1_id) == []
    with read() as s:
        from schema.models import DocumentVersion

        assert s.get(DocumentVersion, v1_id) is None
    assert count_versions(1001) == 1  # only the new active version survives


@pytest.mark.xfail(reason="needs 2.4.1", strict=True)
def test_in3_attachment_edit_reembeds_page(gateway, settings, monkeypatch):
    """panel i2-rebuild · rule 6 (D2)
    An attachment-only edit (manifest changed; body, title and cf_version unchanged) must rebuild
    the page and re-embed every child. Blocked by version identity — a new version cannot stage at
    the same cf_version until substep 2.4.1 adds the fingerprint dimension to the version-identity
    constraint. Strict xfail until 2.4.1 flips it green (and this marker is removed)."""
    index_page(gateway, settings, 1001, version=1)
    v1 = active_version(1001)
    assert v1 is not None

    # An attachment-only change: bump one attachment's manifest version (id/version/fileSize/
    # mediaType feed hash_attachment_manifest), leaving body, title and cf_version untouched.
    real_get_attachments = gateway.get_attachments

    def _edited_attachments(page_id: int):
        atts = [dict(a) for a in real_get_attachments(page_id)]
        if atts:
            atts[0]["version"] = (atts[0].get("version") or 1) + 1
        return atts

    monkeypatch.setattr(gateway, "get_attachments", _edited_attachments)

    counter = install_counting_embedder(monkeypatch, settings)
    enqueue_sync(1001, cf_version=1, key="edit:1001:attach")  # SAME cf_version — attachment-only
    run_worker(gateway, settings, owner="test")

    after = active_child_chunks(1001)
    v2 = active_version(1001)
    assert v2 is not None and v2.id != v1.id  # a new version staged + activated for the edit
    assert counter.texts == len(after)  # every child re-embedded
