"""Garbage collection: only the two most recent superseded versions survive a rebuild."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.platform.db.enums import DocState
from app.platform.db.models import Chunk, DocumentVersion

from ._helpers import count_versions, index_page, read

pytestmark = pytest.mark.db  # substep 0.5.2 · panel i4-gc: real local Postgres via conftest


def test_i4_gc_keeps_the_two_most_recent_superseded_versions(gateway, settings):
    """panel i4-gc · substep 0.5.2
    After a page has been rebuilt four times, exactly the two most recently superseded
    versions (v2 and v3) plus the active version (v4) remain."""
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
    assert by_version == {
        2: DocState.superseded,
        3: DocState.superseded,
        4: DocState.active,
    }
    assert count_versions(1002) == 3  # v2, v3 retained (retain=2) + active v4


def test_i4_gc_deletes_older_versions_and_cascades_chunks(gateway, settings):
    """panel i4-gc · substep 0.5.2
    The version beyond the retention window (v1) is deleted outright, and its chunk rows
    are gone too, proving the FK cascade — not merely orphaned rows."""
    index_page(gateway, settings, 1002, version=1)

    with read() as s:
        v1_id = s.execute(
            select(DocumentVersion.id).where(
                DocumentVersion.page_id == 1002, DocumentVersion.cf_version == 1
            )
        ).scalar_one()

    index_page(gateway, settings, 1002, version=2)
    index_page(gateway, settings, 1002, version=3)
    index_page(gateway, settings, 1002, version=4)

    with read() as s:
        assert s.get(DocumentVersion, v1_id) is None
        remaining_chunks = (
            s.execute(select(Chunk.id).where(Chunk.doc_version_id == v1_id)).scalars().all()
        )
        assert remaining_chunks == []
