"""Rollback: restoring a retained superseded version is an atomic pointer swap."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.features.confluence_sync.application.sync_service import target_versions
from app.features.ingestion import (
    build_ingestion_services,
    classify,
    get_local_state,
    rollback_to,
)
from app.features.ingestion import (
    normalization as norm,
)
from app.platform.db.engine import session_scope
from app.platform.db.models import DocumentVersion, PageSource

from ._helpers import (
    active_child_chunks,
    active_version,
    active_versions_count,
    count_versions,
    index_page,
    read,
)

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest


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


def test_rollback_restores_page_source_hashes_and_pipeline_stamps(gateway, settings):
    """PLAN 4.6.5: a rollback must repoint PageSource's cached hashes/stamps at the target
    version, not leave them pinned to the version that was active before the rollback."""
    index_page(gateway, settings, 1001, version=1)
    index_page(gateway, settings, 1001, version=2)

    with read() as s:
        v1 = s.execute(
            select(DocumentVersion).where(
                DocumentVersion.page_id == 1001, DocumentVersion.cf_version == 1
            )
        ).scalar_one()
        v1_id = v1.id
        v1_fields = {
            "content_hash": v1.content_hash,
            "structure_hash": v1.structure_hash,
            "parser_version": v1.parser_version,
            "chunker_version": v1.chunker_version,
            "contextualization_version": v1.contextualization_version,
            "embedding_model": v1.embedding_model,
            "embedding_dim": v1.embedding_dim,
            "retrieval_schema_version": v1.retrieval_schema_version,
        }

    with session_scope() as s:
        assert rollback_to(s, page_id=1001, target_version_id=v1_id) is True

    with read() as s:
        ps = s.get(PageSource, 1001)
        for field, expected in v1_fields.items():
            assert getattr(ps, field) == expected, field


def test_rollback_then_unchanged_sync_reports_no_change(gateway, settings):
    """PLAN 4.6.5: after rollback, re-syncing the same (target) content must not be spuriously
    flagged as a change just because a stale cached hash from the superseded version lingers."""
    index_page(gateway, settings, 1001, version=1)
    index_page(gateway, settings, 1001, version=2)

    with read() as s:
        v1_id = s.execute(
            select(DocumentVersion.id).where(
                DocumentVersion.page_id == 1001, DocumentVersion.cf_version == 1
            )
        ).scalar_one()
    with session_scope() as s:
        assert rollback_to(s, page_id=1001, target_version_id=v1_id) is True

    gateway.set_version(1001, 1)  # source is still (again) at the rolled-back version
    decision = _classify_current(gateway, settings, page_id=1001)

    assert not decision.meaningful


def test_rollback_then_real_newer_revision_is_detected_not_masked(gateway, settings):
    """PLAN 4.6.5: after rollback, the source revision that was active *before* the rollback (a
    real newer revision from the rolled-back-to version's perspective) must still be detected as a
    change on the next sync — not silently masked because a stale cached hash from that same
    superseded version never got cleared off PageSource."""
    index_page(gateway, settings, 1001, version=1)
    index_page(gateway, settings, 1001, version=2)

    with read() as s:
        v1_id = s.execute(
            select(DocumentVersion.id).where(
                DocumentVersion.page_id == 1001, DocumentVersion.cf_version == 1
            )
        ).scalar_one()
    with session_scope() as s:
        assert rollback_to(s, page_id=1001, target_version_id=v1_id) is True

    # Confluence itself was never rolled back — it still serves v2, the version that was active
    # (and whose hash was cached on PageSource) immediately before this rollback.
    gateway.set_version(1001, 2)
    decision = _classify_current(gateway, settings, page_id=1001)

    assert decision.meaningful
    assert decision.content_hash is not None


def _classify_current(gateway, settings, *, page_id: int):
    """Mirror sync_service.handle_sync_page's classify() call, read-only (no writes)."""
    with read() as s:
        local = get_local_state(s, page_id)
    services = build_ingestion_services(settings)
    target = target_versions(settings, embedding_model=services.embedding_model)
    meta = gateway.get_page_meta(page_id)
    page = gateway.get_page(page_id)
    blocks = norm.normalize_body(page.body_storage) if page else []
    return classify(
        local=local,
        meta=meta,
        target=target,
        labels=gateway.get_labels(page_id),
        restrictions=gateway.get_restrictions(page_id),
        space_key=str(meta.space_id),
        attachments=gateway.get_attachments(page_id),
        blocks=blocks,
    )
