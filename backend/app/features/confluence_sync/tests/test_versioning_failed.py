"""A failed version never activates: the record persists, GC never reaps it (panel i4-failed)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.features.confluence_sync.application.sync_service import target_versions
from app.features.ingestion import (
    PageHashes,
    build_ingestion_services,
    map_page_status,
    stage_and_activate,
)
from schema.engine import get_sessionmaker
from schema.enums import DocState
from schema.models import DocumentVersion

from ._helpers import index_page, read

pytestmark = pytest.mark.db  # substep 0.5.2 · panel i4-failed: real local Postgres via conftest

_HASHES = PageHashes(
    content_hash=b"\x00" * 32,
    structure_hash=b"\x00" * 32,
    labels_hash=b"\x00" * 32,
    access_scope_hash=b"\x00" * 32,
    attachment_manifest_hash=b"\x00" * 32,
)


def _force_gate_failure(gateway, settings, *, page_id: int, cf_version: int) -> None:
    """Force `stage_and_activate`'s own gate to reject a rebuild (zero blocks -> zero child
    chunks) and commit the resulting failed-state row ourselves, on a page already indexed once.

    Reaching this same gate through the job queue instead loses the row entirely: `run_once`'s
    "transaction 2" wraps a whole sync in one commit-or-rollback session and rolls everything back
    on any handler exception (see `worker.py`'s own transaction-discipline docstring) — confirmed
    empirically (querying `document_version` after `index_page` reached this same gate via
    `run_once`/`drain` returns zero rows). Calling `stage_and_activate` (the function this panel is
    about) directly, with a session this test commits itself, isolates the versioning layer's own
    persistence contract from that separate, unrelated job-queue transaction boundary.

    Also confirmed empirically: doing this on a page's very *first* index hits a different wall —
    `Document.page_id`'s FK to `page_source.page_id` is DEFERRED to commit ("insert-order cycle on
    first index", models.py:186-190), and `page_source` is only ever created inside `_activate`,
    which a gate failure never reaches — so a first-index gate failure cannot even be committed
    (raises `IntegrityError` at commit). Forcing the gate on a *rebuild* of an already-indexed page
    avoids that: `document` and `page_source` already exist from the prior successful index, so
    only the new (failed) `document_version` row is inserted.
    """
    gateway.set_version(page_id, cf_version)
    meta = gateway.get_page_meta(page_id)
    assert meta is not None
    services = build_ingestion_services(settings)
    target = target_versions(settings, embedding_model=services.embedding_model)
    session = get_sessionmaker()()
    try:
        with pytest.raises(ValueError, match="no child chunks"):
            stage_and_activate(
                session,
                meta=meta,
                blocks=[],  # zero blocks -> build_chunks yields zero children -> the gate rejects
                hashes=_HASHES,
                target=target,
                page_status=map_page_status(meta.status),
                services=services,
            )
        session.commit()
    finally:
        session.close()


def test_i4_failed_version_persists_as_a_record(gateway, settings):
    """panel i4-failed · substep 0.5.2
    A failed build never goes live, but its DocumentVersion row (state=failed) is a persisted
    record in the database, not deleted."""
    index_page(gateway, settings, 1001, version=1)  # first index must succeed (see docstring)
    _force_gate_failure(gateway, settings, page_id=1001, cf_version=2)

    with read() as s:
        row = s.execute(
            select(DocumentVersion).where(
                DocumentVersion.page_id == 1001, DocumentVersion.cf_version == 2
            )
        ).scalar_one()
    assert row.state == DocState.failed


def test_i4_failed_never_garbage_collected_by_gc(gateway, settings):
    """panel i4-failed · substep 0.5.2
    Today's gap, disclosed on the panel itself: `_gc_superseded` only ever selects
    state=superseded rows, so a state=failed version row is never selected, marked or deleted by
    it — it survives a real GC pass (triggered by another successful rebuild of the same page)
    completely untouched."""
    index_page(gateway, settings, 1001, version=1)
    _force_gate_failure(gateway, settings, page_id=1001, cf_version=2)

    with read() as s:
        failed_id = s.execute(
            select(DocumentVersion.id).where(
                DocumentVersion.page_id == 1001, DocumentVersion.cf_version == 2
            )
        ).scalar_one()

    # A real successful rebuild (cf_version=3): supersedes v1 and calls `_gc_superseded` as its
    # last step. `_gc_superseded` cannot be imported directly here (not exported at the ingestion
    # feature root, and a deep cross-feature import would fail `make boundaries`), so it is
    # exercised the way the substep itself allows: indirectly, via a real rebuild.
    index_page(gateway, settings, 1001, version=3)

    with read() as s:
        still_there = s.get(DocumentVersion, failed_id)
    assert still_there is not None
    assert still_there.state == DocState.failed
