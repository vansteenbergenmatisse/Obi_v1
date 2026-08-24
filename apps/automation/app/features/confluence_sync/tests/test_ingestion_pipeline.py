"""Phase-3 pipeline over the DB: embeddings + tsv populated, keyword search works, atomic swaps."""

from __future__ import annotations

from sqlalchemy import text

from app.features.confluence_sync.application.sync_service import target_versions
from app.features.ingestion import build_ingestion_services, reusable_active_children
from app.platform.config import Settings, get_settings
from app.platform.db.enums import DocState
from app.platform.db.models import Chunk, DocumentVersion

from ._helpers import active_child_chunks, active_version, active_versions_count, index_page, read


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


def test_reuse_guard_disables_on_config_change(gateway, settings: Settings) -> None:
    index_page(gateway, settings, 1001, 1)
    with read() as s:
        svc = build_ingestion_services(settings)
        tgt = target_versions(settings, svc.embedding_model)
        # unchanged pipeline config -> prior children are reuse-eligible
        assert reusable_active_children(s, 1001, target=tgt, services=svc)
        # bump the retrieval schema version -> reuse disabled (full re-embed)
        bumped = settings.model_copy(
            update={"retrieval_schema_version": settings.retrieval_schema_version + 1}
        )
        svc_b = build_ingestion_services(bumped)
        tgt_b = target_versions(bumped, svc_b.embedding_model)
        assert reusable_active_children(s, 1001, target=tgt_b, services=svc_b) == []


def test_schema_bump_triggers_full_reembed_release(gateway, settings: Settings) -> None:
    from app.features.confluence_sync.application.sync_service import handle_sync_page
    from app.platform.db.engine import session_scope

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


def test_label_driven_knowledge_scope_tag_unions_with_source_scope(
    gateway, settings: Settings
) -> None:
    """PLAN 10.2: a page labeled `toast` (a recognized POS-provider knowledge scope — asserted as
    the platform, not this repo's own `Muse` codename, per ADR-0011's disclosed collision) is
    stamped with that tag on both page_source and every active chunk, unioned with the page's
    existing source_scope tag (`base`), not replacing it."""
    from app.features.confluence_sync.application.sync_service import handle_sync_page
    from app.platform.db.engine import session_scope
    from app.platform.db.models import PageSource

    # `toast` is recognized via the committed config/knowledge_scopes.json, not an env override —
    # deterministic regardless of the developer's local .env.
    gateway.set_labels(1001, ["toast"])
    gateway.set_version(1001, 1)
    with session_scope() as s:
        outcome = handle_sync_page(
            s, page_id=1001, gateway=gateway, settings=settings, tags=["base"]
        )
    assert outcome.action == "indexed"

    with read() as s:
        ps = s.get(PageSource, 1001)
        assert ps is not None
        assert set(ps.tags) == {"base", "toast"}
    children = active_child_chunks(1001)
    assert children and all(set(c.tags) == {"base", "toast"} for c in children)


def test_conflicting_provider_labels_contribute_no_tag_and_log_conflict(
    gateway, settings: Settings, monkeypatch
) -> None:
    """Two provider labels on the same page (`mews` + `toast`) is a conflict: zero label-derived
    tags land on the page (the existing `base` source_scope tag is untouched), and a
    `knowledge_scope_conflict` event is logged so an operator can fix the Confluence labels."""
    from app.features.confluence_sync.application import sync_service
    from app.platform.db.engine import session_scope
    from app.platform.db.models import PageSource

    captured: dict = {}
    monkeypatch.setattr(
        sync_service.log, "warning", lambda event, **kw: captured.update(event=event, **kw)
    )

    gateway.set_labels(1001, ["mews", "toast"])
    gateway.set_version(1001, 1)
    with session_scope() as s:
        outcome = sync_service.handle_sync_page(
            s, page_id=1001, gateway=gateway, settings=settings, tags=["base"]
        )
    assert outcome.action == "indexed"
    assert captured.get("event") == "knowledge_scope_conflict"
    assert set(captured.get("matched_labels", [])) == {"mews", "toast"}

    with read() as s:
        ps = s.get(PageSource, 1001)
        assert ps is not None
        assert set(ps.tags) == {"base"}
