"""One switch, flipped atomically: old version off, new version on, the registry pointer moved
with it (design panel i4-swap)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.features.confluence_sync.application.sync_service import handle_sync_page
from app.platform.config import Settings
from schema.engine import session_scope
from schema.enums import DocState
from schema.models import Chunk, DocumentVersion, PageSource

from ._helpers import active_child_chunks, active_version, index_page, read

pytestmark = (
    pytest.mark.db
)  # substep 0.5.2: real local Postgres via this dir's session-scoped conftest


def test_i4_swap_old_version_superseded_and_its_chunks_inactive(
    gateway, settings: Settings
) -> None:
    """panel i4-swap · substep 0.5.2
    Old version: the swap flips the previously active DocumentVersion row to state=superseded
    (with superseded_at stamped) and flips every one of its chunks to is_active=false — the
    now-stale build is fully retired, not merely unlinked."""
    index_page(gateway, settings, 1001, version=1)
    v1 = active_version(1001)
    assert v1 is not None
    assert active_child_chunks(1001)  # v1's children are live before the reindex

    index_page(gateway, settings, 1001, version=3)  # v3 adds a Troubleshooting section

    with read() as s:
        old = s.get(DocumentVersion, v1.id)
        assert old is not None
        assert old.state == DocState.superseded
        assert old.superseded_at is not None

        old_chunks = s.execute(select(Chunk).where(Chunk.doc_version_id == v1.id)).scalars().all()
    assert old_chunks  # the old version's chunk rows still exist, just retired
    assert all(c.is_active is False for c in old_chunks)


def test_i4_swap_new_version_active_and_its_chunks_active(gateway, settings: Settings) -> None:
    """panel i4-swap · substep 0.5.2
    New version: the swap flips the freshly staged DocumentVersion row to state=active (with
    activated_at stamped) and flips every one of its chunks to is_active=true — exactly the rows
    a reader sees once the rebuild lands."""
    index_page(gateway, settings, 1001, version=1)
    index_page(gateway, settings, 1001, version=3)

    new = active_version(1001)
    assert new is not None
    assert new.state == DocState.active
    assert new.activated_at is not None

    with read() as s:
        new_chunks = s.execute(select(Chunk).where(Chunk.doc_version_id == new.id)).scalars().all()
    assert new_chunks
    assert all(c.is_active is True for c in new_chunks)


def test_i4_swap_pointer_moves_identity_hashes_stamps_and_tags_to_the_new_version(
    gateway, settings: Settings
) -> None:
    """panel i4-swap · substep 0.5.2
    Pointer: page_source.active_doc_version_id is repointed to the new version's id, and every
    field the design panel names moves with it in the same swap — title, url, hashes, the
    pipeline stamps, tags and current_cf_version — not left stale from the superseded build."""
    gateway.set_version(1001, 1)
    with session_scope() as s:
        outcome_v1 = handle_sync_page(
            s, page_id=1001, gateway=gateway, settings=settings, tags=["base"]
        )
    assert outcome_v1.action == "indexed"
    v1 = active_version(1001)
    assert v1 is not None

    with read() as s:
        ps_before = s.get(PageSource, 1001)
        assert ps_before is not None
        assert ps_before.active_doc_version_id == v1.id
        assert ps_before.current_cf_version == 1
        assert set(ps_before.tags) == {"base"}
        content_hash_before = ps_before.content_hash
        title_before, url_before = ps_before.title, ps_before.source_url
        last_indexed_before = ps_before.last_indexed_at
        assert last_indexed_before is not None

    gateway.set_version(1001, 3)  # v3 adds a Troubleshooting section: a different body hash
    with session_scope() as s:
        outcome_v3 = handle_sync_page(
            s, page_id=1001, gateway=gateway, settings=settings, tags=["base", "obi-general-test"]
        )
    assert outcome_v3.action == "indexed"
    v3 = active_version(1001)
    assert v3 is not None
    assert v3.id != v1.id

    with read() as s:
        ps_after = s.get(PageSource, 1001)
        assert ps_after is not None

        # pointer: repointed to the new version, not the old one
        assert ps_after.active_doc_version_id == v3.id

        # identity carried by the pointer: stamped from THIS build's meta, not left over from the
        # prior one (title/url happen to be unchanged across these two fixture revisions)
        assert ps_after.title == title_before
        assert ps_after.source_url == url_before

        # hashes: recomputed from the new build's content, not the superseded build's
        assert ps_after.content_hash != content_hash_before

        # pipeline stamps: the pointer's version stamps match the new version's own row
        assert ps_after.parser_version == v3.parser_version
        assert ps_after.chunker_version == v3.chunker_version
        assert ps_after.contextualization_version == v3.contextualization_version
        assert ps_after.embedding_model == v3.embedding_model
        assert ps_after.embedding_dim == v3.embedding_dim
        assert ps_after.retrieval_schema_version == v3.retrieval_schema_version
        assert ps_after.last_indexed_at is not None
        assert ps_after.last_indexed_at >= last_indexed_before

        # tags: exactly what this build passed, not a stale union from the previous swap
        assert set(ps_after.tags) == {"base", "obi-general-test"}

        # current_cf_version: the new Confluence revision number, not the old one
        assert ps_after.current_cf_version == 3
