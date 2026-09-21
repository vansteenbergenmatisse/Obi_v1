"""Insert the chunks inactive: parent-first linking, the is_active default, and the uniqueness
constraint that keeps a rebuild from colliding with itself (design panel i4-chunks)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from schema.models import KIND_CHILD, KIND_PARENT, Chunk

from ._helpers import active_version, index_page, read

pytestmark = (
    pytest.mark.db
)  # substep 0.5.2: real local Postgres via this dir's session-scoped conftest


def test_i4_chunks_parents_persisted_before_children_are_linked(gateway, settings):
    """panel i4-chunks · substep 0.5.2
    Order: parents flushed first, then children mapped to (section, parent ordinal) — every child
    chunk's parent_chunk_id is a valid, non-null FK to an actually-persisted parent Chunk row in the
    same doc_version_id (page-1001's body has five h1/h2/h3 sections, so multiple parents exist)."""
    index_page(gateway, settings, 1001, version=1)
    version = active_version(1001)
    assert version is not None

    with read() as s:
        chunks = list(
            s.execute(select(Chunk).where(Chunk.doc_version_id == version.id)).scalars().all()
        )

    parent_ids = {c.id for c in chunks if c.kind == KIND_PARENT}
    children = [c for c in chunks if c.kind == KIND_CHILD]
    assert len(parent_ids) >= 2  # multi-section body: at least two parent chunks exist
    assert children
    assert all(c.parent_chunk_id is not None and c.parent_chunk_id in parent_ids for c in children)


def test_i4_chunks_default_inactive_until_the_swap(gateway, settings, session):
    """panel i4-chunks · substep 0.5.2
    Flags: is_active = false, is stamped active only by the swap — a chunk row inserted without an
    explicit is_active value reads back false, proving the database default (not application code)
    is what keeps a staged chunk out of search until _activate() flips it."""
    index_page(gateway, settings, 1001, version=1)
    version = active_version(1001)
    assert version is not None

    with read() as s:
        template = (
            s.execute(select(Chunk).where(Chunk.doc_version_id == version.id)).scalars().first()
        )
    assert template is not None

    throwaway = Chunk(
        doc_version_id=version.id,
        page_id=template.page_id,
        cf_version=template.cf_version,
        kind=KIND_PARENT,
        stable_key=b"throwaway-stable-key-i4-chunks",
        positional_key=b"throwaway-positional-key-i4-chunks",
        content_key=b"throwaway-content-key-i4-chunks",
        content_hash=b"throwaway-content-key-i4-chunks",
        seq=9998,
        heading_path=["Throwaway"],
        location={},
        display_content="throwaway",
        retrieval_content="throwaway",
        tokens=1,
        title="Throwaway",
        space_id=template.space_id,
        source_url=template.source_url,
        page_status=template.page_status,
        retrieval_schema_version=template.retrieval_schema_version,
        embedding_model=template.embedding_model,
        access_scope=template.access_scope,
        # is_active intentionally omitted: the column's server_default is what this test protects.
    )
    session.add(throwaway)
    session.flush()

    reloaded = session.execute(select(Chunk.is_active).where(Chunk.id == throwaway.id)).scalar_one()
    assert reloaded is False


def test_i4_chunks_uniqueness_on_doc_version_and_stable_key(gateway, settings, session):
    """panel i4-chunks · substep 0.5.2
    Uniqueness: (doc_version_id, stable_key) — inserting a second chunk row that repeats an
    existing chunk's (doc_version_id, stable_key) pair raises IntegrityError; the constraint fires
    at the database, not merely as an application-level check."""
    index_page(gateway, settings, 1001, version=1)
    version = active_version(1001)
    assert version is not None

    with read() as s:
        existing = (
            s.execute(select(Chunk).where(Chunk.doc_version_id == version.id)).scalars().first()
        )
    assert existing is not None

    duplicate = Chunk(
        doc_version_id=version.id,
        page_id=existing.page_id,
        cf_version=existing.cf_version,
        kind=existing.kind,
        stable_key=existing.stable_key,  # same (doc_version_id, stable_key) as `existing`
        positional_key=b"dup-positional-key-i4-chunks",
        content_key=b"dup-content-key-i4-chunks",
        content_hash=b"dup-content-key-i4-chunks",
        seq=9999,
        heading_path=["Duplicate"],
        location={},
        display_content="duplicate",
        retrieval_content="duplicate",
        tokens=1,
        title="Duplicate",
        space_id=existing.space_id,
        source_url=existing.source_url,
        page_status=existing.page_status,
        retrieval_schema_version=existing.retrieval_schema_version,
        embedding_model=existing.embedding_model,
        access_scope=existing.access_scope,
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
