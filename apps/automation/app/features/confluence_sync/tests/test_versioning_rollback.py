"""Rollback: restoring a retained superseded version is an atomic pointer swap."""

from __future__ import annotations

from sqlalchemy import select

from app.features.ingestion.application.versioning import rollback_to
from app.platform.db.engine import session_scope
from app.platform.db.models import DocumentVersion

from ._helpers import (
    active_child_chunks,
    active_version,
    active_versions_count,
    count_versions,
    index_page,
    read,
)


def test_rollback_restores_prior_version(gateway, settings):
    index_page(gateway, settings, 1001, version=1)
    index_page(gateway, settings, 1001, version=2)
    index_page(gateway, settings, 1001, version=3)

    assert active_version(1001).cf_version == 3
    assert count_versions(1001) == 3  # v1, v2 retained (retain=2) + active v3

    with read() as s:
        v2_id = s.execute(
            select(DocumentVersion.id).where(
                DocumentVersion.page_id == 1001, DocumentVersion.cf_version == 2
            )
        ).scalar_one()

    with session_scope() as s:
        assert rollback_to(s, page_id=1001, target_version_id=v2_id) is True

    assert active_version(1001).cf_version == 2
    assert active_versions_count(1001) == 1  # exactly one active after swap
    assert {c.doc_version_id for c in active_child_chunks(1001)} == {v2_id}
