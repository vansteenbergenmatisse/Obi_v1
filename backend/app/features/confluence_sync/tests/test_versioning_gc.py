"""Garbage collection: retain 0 — a rebuild deletes the just-superseded version and its chunks in
the same transaction, so only the active version ever survives (sync rule 6 / D1, no rollback)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from schema.enums import DocState
from schema.models import Chunk, DocumentVersion

from ._helpers import count_versions, index_page, read

pytestmark = pytest.mark.db  # substep 2.3.1 · panel i4-gc: real local Postgres via conftest


def test_i4_gc_keeps_zero_superseded_versions(gateway, settings):
    """panel i4-gc · substep 2.3.1 (D1)
    After a page has been rebuilt four times, no superseded version survives — only the active
    version (v4) remains. Retain 0: nothing is kept for rollback."""
    index_page(gateway, settings, 1002, version=1)
    index_page(gateway, settings, 1002, version=2)
    index_page(gateway, settings, 1002, version=3)
    index_page(gateway, settings, 1002, version=4)  # cascades on top of this feature's own
    # versions/page-1002-v{1..4}.json fixtures (added for this panel; the corpus base file for
    # 1002 stays at its existing version 5, so no other test's indexing is affected)

    with read() as s:
        rows = s.execute(
            select(DocumentVersion.cf_version, DocumentVersion.state).where(
                DocumentVersion.page_id == 1002
            )
        ).all()

    by_version = {cf_version: state for cf_version, state in rows}
    assert by_version == {4: DocState.active}  # only the active version survives — retain 0
    assert count_versions(1002) == 1


def test_i4_gc_deletes_the_superseded_version_and_cascades_chunks(gateway, settings):
    """panel i4-gc · substep 2.3.1 (D1)
    A single rebuild deletes the just-superseded version (v1) outright, and its chunk rows are gone
    too, proving the FK cascade — not merely orphaned or retired rows."""
    index_page(gateway, settings, 1002, version=1)

    with read() as s:
        v1_id = s.execute(
            select(DocumentVersion.id).where(
                DocumentVersion.page_id == 1002, DocumentVersion.cf_version == 1
            )
        ).scalar_one()

    index_page(gateway, settings, 1002, version=2)  # one rebuild -> v1 is superseded then GC'd

    with read() as s:
        assert s.get(DocumentVersion, v1_id) is None
        remaining_chunks = (
            s.execute(select(Chunk.id).where(Chunk.doc_version_id == v1_id)).scalars().all()
        )
        assert remaining_chunks == []
    assert count_versions(1002) == 1  # only the active v2 remains
