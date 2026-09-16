"""Document identity: one permanent row per page, stable across every rebuild."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.platform.db.models import Document

from ._helpers import index_page, read

pytestmark = (
    pytest.mark.db
)  # substep 0.5.2: real local Postgres via this dir's session-scoped conftest


def test_i4_document_one_row_per_page_across_rebuilds(gateway, settings):
    """panel i4-document · substep 0.5.2
    One per page: document.page_id is unique — exactly one Document row exists for the page,
    with the same id, after each of three rebuilds (versions 1, 2, 3)."""
    ids: list[int] = []
    for version in (1, 2, 3):
        index_page(gateway, settings, 1001, version=version)
        with read() as s:
            rows = s.execute(select(Document).where(Document.page_id == 1001)).scalars().all()
        assert len(rows) == 1
        ids.append(rows[0].id)

    assert len(set(ids)) == 1


def test_i4_document_id_is_stable_across_rebuilds(gateway, settings):
    """panel i4-document · substep 0.5.2
    Purpose: a stable id across every rebuild — the Document.id found after the first index is
    the exact same id found after two further rebuilds, not a new row per version."""
    index_page(gateway, settings, 1001, version=1)
    with read() as s:
        doc_id_after_v1 = s.execute(
            select(Document.id).where(Document.page_id == 1001)
        ).scalar_one()

    index_page(gateway, settings, 1001, version=2)
    index_page(gateway, settings, 1001, version=3)

    with read() as s:
        doc_id_after_v3 = s.execute(
            select(Document.id).where(Document.page_id == 1001)
        ).scalar_one()

    assert doc_id_after_v1 == doc_id_after_v3
