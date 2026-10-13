"""Phase-3 pipeline over the DB: embeddings + tsv populated, keyword search works, atomic swaps."""

from __future__ import annotations

import pytest
from sqlalchemy import func, literal_column, select, text

from app.platform.config import Settings, get_settings
from schema.enums import DocState
from schema.models import KIND_PARENT, Chunk, DocumentVersion

from ._helpers import active_child_chunks, active_version, active_versions_count, index_page, read

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest


def test_children_have_embeddings_and_tsv(gateway, settings: Settings) -> None:
    index_page(gateway, settings, 1001, 1)
    children = active_child_chunks(1001)
    assert children, "expected at least one active child chunk"
    dim = get_settings().embedding_dim
    for c in children:
        assert c.embedding is not None
        assert len(c.embedding) == dim
        assert c.retrieval_content
        assert c.tsv  # keyword vector populated


def test_keyword_tsv_is_queryable(gateway, settings: Settings) -> None:
    index_page(gateway, settings, 1001, 1)
    with read() as s:
        hits = s.execute(
            text(
                "SELECT count(*) FROM chunk "
                "WHERE is_active AND kind = 1 AND page_id = 1001 "
                "AND tsv @@ plainto_tsquery('english', 'access')"
            )
        ).scalar_one()
    assert hits > 0  # 'access' appears in the onboarding page and is keyword-searchable


def test_i3_tsv_column_is_children_only(gateway, settings: Settings) -> None:
    """panel i3-tsv · substep 0.5.2
    Column: chunk.tsv, children only — after a real index, every parent chunk for the page has
    tsv IS NULL and every active child chunk has tsv IS NOT NULL."""
    index_page(gateway, settings, 1001, 1)
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
    assert all(p.tsv is None for p in parents)

    children = active_child_chunks(1001)
    assert children, "expected at least one active child chunk"
    assert all(c.tsv is not None for c in children)


def test_i3_tsv_built_from_title_heading_path_and_text(gateway, settings: Settings) -> None:
    """panel i3-tsv · substep 0.5.2
    Built from: to_tsvector('english', title + heading path + text) — a child's stored tsv is
    byte-for-byte the tsvector Postgres computes fresh from that same row's own title,
    heading_path (joined with ' > ') and display_content, proving the construction formula
    rather than merely that some word in the body is findable."""
    index_page(gateway, settings, 1001, 1)
    children = active_child_chunks(1001)
    assert children, "expected at least one active child chunk"

    with read() as s:
        for c in children:
            expected = s.execute(
                select(
                    func.to_tsvector(
                        literal_column("'english'"),
                        c.title + " " + " > ".join(c.heading_path) + " " + c.display_content,
                    )
                )
            ).scalar_one()
            assert c.tsv == expected


def test_i3_tsv_gin_index_scoped_to_active_children(gateway, settings: Settings) -> None:
    """panel i3-tsv · substep 0.5.2
    Index: ix_chunk_tsv_gin, active children — the index exists on chunk.tsv using the gin
    access method, restricted by a partial predicate to active child rows only."""
    index_page(gateway, settings, 1001, 1)  # forces the schema to exist even on a cold test db
    with read() as s:
        indexdef = s.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_chunk_tsv_gin'")
        ).scalar_one_or_none()
    assert indexdef is not None, "expected the ix_chunk_tsv_gin index to exist on chunk"
    lowered = indexdef.lower()
    assert "using gin" in lowered
    assert "tsv" in lowered
    assert "is_active" in lowered  # scoped to active rows
    assert "kind" in lowered  # scoped to children (kind = 1) only


def test_vd_keyword_column_built_from_title_heading_path_and_text_english(
    gateway, settings: Settings
) -> None:
    """panel vd-keyword · substep 0.5.3
    Column: tsv = to_tsvector('english', title || heading path || text) — a child's stored tsv is
    byte-for-byte the tsvector Postgres computes fresh, with the 'english' text-search
    configuration, from that same row's own title, heading_path (joined with ' > ') and
    display_content — the exact construction formula the vector-database panel names, not merely
    that some word in the body is findable (that weaker claim is `test_keyword_tsv_is_queryable`,
    above)."""
    index_page(gateway, settings, 1001, 1)
    children = active_child_chunks(1001)
    assert children, "expected at least one active child chunk"

    with read() as s:
        for c in children:
            expected = s.execute(
                select(
                    func.to_tsvector(
                        literal_column("'english'"),
                        c.title + " " + " > ".join(c.heading_path) + " " + c.display_content,
                    )
                )
            ).scalar_one()
            assert c.tsv == expected


def test_vd_keyword_gin_index_exists_over_tsv(gateway, settings: Settings) -> None:
    """panel vd-keyword · substep 0.5.3
    Index: ix_chunk_tsv_gin — the index named in the panel exists on chunk.tsv using Postgres's
    gin access method, which is what lets the keyword query's `tsv @@ ...` predicate be answered
    from the index rather than a sequential scan."""
    index_page(gateway, settings, 1001, 1)  # forces the schema to exist even on a cold test db
    with read() as s:
        indexdef = s.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_chunk_tsv_gin'")
        ).scalar_one_or_none()
    assert indexdef is not None, "expected the ix_chunk_tsv_gin index to exist on chunk"
    lowered = indexdef.lower()
    assert "using gin" in lowered
    assert "tsv" in lowered


def test_version_upgrade_is_atomic_and_updates_content(gateway, settings: Settings) -> None:
    index_page(gateway, settings, 1001, 1)
    v1_children = {c.stable_key for c in active_child_chunks(1001)}

    index_page(gateway, settings, 1001, 3)  # v3 adds a Troubleshooting section
    assert active_versions_count(1001) == 1  # readers never see two active versions

    v3_children = active_child_chunks(1001)
    text_blob = " ".join(c.display_content for c in v3_children).lower()
    assert "troubleshooting" in text_blob or "sso" in text_blob
    # the section set changed between versions
    assert {c.stable_key for c in v3_children} != v1_children


def test_only_one_document_version_active_after_reindex(gateway, settings: Settings) -> None:
    index_page(gateway, settings, 1001, 1)
    index_page(gateway, settings, 1001, 3)
    with read() as s:
        active = (
            s.query(DocumentVersion)
            .filter(DocumentVersion.page_id == 1001, DocumentVersion.state == DocState.active)
            .count()
        )
        # every active chunk points at that one active version
        active_dv_ids = {
            c.doc_version_id
            for c in s.query(Chunk).filter(Chunk.page_id == 1001, Chunk.is_active.is_(True)).all()
        }
    assert active == 1
    assert len(active_dv_ids) == 1


def test_schema_bump_triggers_full_reembed_release(gateway, settings: Settings) -> None:
    from app.features.confluence_sync.application.sync_service import handle_sync_page
    from schema.engine import session_scope

    index_page(gateway, settings, 1001, 1)
    v1 = active_version(1001)
    assert v1 is not None

    # bump the index schema and re-run the same Confluence version through the sync path
    bumped = settings.model_copy(
        update={"retrieval_schema_version": settings.retrieval_schema_version + 1}
    )
    gateway.set_version(1001, 1)
    with session_scope() as s:
        outcome = handle_sync_page(s, page_id=1001, gateway=gateway, settings=bumped)
    assert outcome.action == "indexed"  # config change forced a rebuild

    v2 = active_version(1001)
    assert v2 is not None
    assert v2.id != v1.id  # a fresh index version was built and swapped in atomically
    assert v2.retrieval_schema_version == bumped.retrieval_schema_version
    assert active_versions_count(1001) == 1
    children = active_child_chunks(1001)
    assert children and all(c.embedding is not None for c in children)


def test_label_driven_knowledge_scope_stamped_on_page_and_chunks(
    gateway, settings: Settings
) -> None:
    """PLAN 10.2 / trigger split: a page labeled `toast-general` (a recognized POS-provider
    knowledge scope — the platform, not this repo's `Muse` codename, per ADR-0011's disclosed
    collision) is stamped with exactly that scope on page_source and every active chunk.

    Post trigger/ingestion split the stamped scopes are authoritative — `recognized_labels ∩
    authorized`. With no source_scope row the space is unrestricted, so the label itself is the
    scope. The pre-split additive `base` source_scope tag is retired: source_scope.tags are a
    recognized-scope allow-list (intersected), not arbitrary additive stamps."""
    from app.features.confluence_sync.application.sync_service import handle_sync_page
    from schema.engine import session_scope
    from schema.models import PageSource

    # `toast-general` is recognized via the committed config/knowledge_scopes.json, not an env
    # override — deterministic regardless of the developer's local .env.
    gateway.set_labels(1001, ["toast-general"])
    gateway.set_version(1001, 1)
    with session_scope() as s:
        outcome = handle_sync_page(s, page_id=1001, gateway=gateway, settings=settings)
    assert outcome.action == "indexed"

    with read() as s:
        ps = s.get(PageSource, 1001)
        assert ps is not None
        assert set(ps.tags) == {"toast-general"}
    children = active_child_chunks(1001)
    assert children and all(set(c.tags) == {"toast-general"} for c in children)


def test_two_provider_labels_share_all_scopes_no_conflict_log(
    gateway, settings: Settings, monkeypatch
) -> None:
    """Two provider labels on the same page (`mews` + `toast`) is legitimate sharing (D4, §13 step
    3), not a conflict: both label-derived scopes land on the page and no
    `knowledge_scope_conflict` event is logged. (Unrestricted space → scopes are the labels.)"""
    from app.features.confluence_sync.application import sync_service
    from schema.engine import session_scope
    from schema.models import PageSource

    captured: dict = {}
    monkeypatch.setattr(
        sync_service.log, "warning", lambda event, **kw: captured.update(event=event, **kw)
    )

    gateway.set_labels(1001, ["mews-general", "toast-general"])
    gateway.set_version(1001, 1)
    with session_scope() as s:
        outcome = sync_service.handle_sync_page(s, page_id=1001, gateway=gateway, settings=settings)
    assert outcome.action == "indexed"
    assert captured.get("event") != "knowledge_scope_conflict"  # conflict concept retired (D4)

    with read() as s:
        ps = s.get(PageSource, 1001)
        assert ps is not None
        assert set(ps.tags) == {"mews-general", "toast-general"}
