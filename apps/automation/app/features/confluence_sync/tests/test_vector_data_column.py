"""chunk.embedding: nullable, child-only, and colocated with tags/tsv on the same row
(design panel vd-column).

Dimension is never hardcoded here: ``vd-column``'s own ``today`` line discloses that the design
page's literal "3072" claim is unverifiable from source alone (the code default is Voyage
voyage-3-large at 1024 dims, and the real deployed dimension depends on an env override). These
tests only assert nullability, child-only population, and same-row colocation — never a specific
number of dimensions — reading whatever ``get_settings().embedding_dim`` resolves to in the test
environment when a dimension needs comparing at all.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.platform.config import get_settings
from app.platform.db.models import KIND_PARENT, Chunk

from ._helpers import active_child_chunks, active_version, index_page, read

pytestmark = (
    pytest.mark.db
)  # substep 0.5.3: real local Postgres via this dir's session-scoped conftest


def test_vd_column_embedding_is_nullable(gateway, settings, session):
    """panel vd-column · substep 0.5.3
    Type: vector(N), nullable — a Chunk row flushes and commits fine with embedding=None; the
    schema itself allows a null embedding, independent of whatever value application code sets."""
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
        stable_key=b"throwaway-stable-key-vd-column",
        positional_key=b"throwaway-positional-key-vd-column",
        content_key=b"throwaway-content-key-vd-column",
        content_hash=b"throwaway-content-key-vd-column",
        seq=9997,
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
        embedding=None,  # the schema-level claim under test: this must not raise
    )
    session.add(throwaway)
    session.flush()
    session.commit()

    reloaded = session.execute(select(Chunk.embedding).where(Chunk.id == throwaway.id)).scalar_one()
    assert reloaded is None


def test_vd_column_only_child_chunks_carry_an_embedding(gateway, settings):
    """panel vd-column · substep 0.5.3
    Who has one: child chunks only — after a real index, every parent chunk for the page has
    embedding IS NULL and every active child chunk has embedding IS NOT NULL."""
    index_page(gateway, settings, 1001, version=1)
    version = active_version(1001)
    assert version is not None

    with read() as s:
        parents = list(
            s.execute(
                select(Chunk).where(Chunk.doc_version_id == version.id, Chunk.kind == KIND_PARENT)
            )
            .scalars()
            .all()
        )
    assert parents, "expected at least one parent chunk"
    assert all(p.embedding is None for p in parents)

    children = active_child_chunks(1001)
    assert children, "expected at least one active child chunk"
    assert all(c.embedding is not None for c in children)


def test_vd_column_embedding_colocated_with_tags_and_tsv_on_same_row(gateway, settings):
    """panel vd-column · substep 0.5.3
    Same row: an active child Chunk row's embedding, text, tags, scope_state and tsv all live on
    the one row, not split across tables — a single row simultaneously carries all five,
    non-empty/non-null.

    "text" is the child's own ``retrieval_content``/``display_content`` columns (panel vd-text:
    "the verbatim child text, for citations"). "scope_state" has no separate column in the
    schema — it is the same tags/labels state materialized on ``chunk.tags``, per
    ``test_scope_tagging_retag.py``'s own disclosure for the identical claim; asserting
    ``row.tags`` proves both names at once, not two independent surfaces.

    Page 1001 carries no recognized label, so its chunks' ``tags`` are empty; page 3001
    (fixture label ``obi-general-test``) is used here instead, since a non-empty ``tags`` list is
    exactly the claim under test."""
    index_page(gateway, settings, 3001, version=1)
    children = active_child_chunks(3001)
    assert children, "expected at least one active child chunk"

    dim = get_settings().embedding_dim
    row = children[0]
    assert row.embedding is not None
    assert len(row.embedding) == dim
    assert row.retrieval_content
    assert row.display_content
    assert row.tags  # tags == scope_state, no separate column
    assert row.tsv
