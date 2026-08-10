"""Job handlers that turn a queued event into an idempotent, version-aware index update."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, insert, update
from sqlalchemy.orm import Session

from app.features.ingestion import (
    ChangeClass,
    PageHashes,
    TargetVersions,
    build_ingestion_services,
    classify,
    deactivate_page,
    decide_body_fetch,
    get_local_state,
    map_page_status,
    stage_and_activate,
)
from app.features.ingestion import (
    normalization as norm,
)
from app.platform.clients import ConfluenceGateway
from app.platform.config import Settings
from app.platform.db.models import Chunk, PageRestriction, PageSource

_REBUILD_CLASSES = {
    ChangeClass.body_changed,
    ChangeClass.section_added,
    ChangeClass.section_updated,
    ChangeClass.section_removed,
    ChangeClass.section_moved,
    ChangeClass.index_config_change,
}


@dataclass
class SyncOutcome:
    action: str  # indexed | metadata_only | no_change | deactivated | gone
    classes: list[str]
    page_id: int | None


def target_versions(settings: Settings, embedding_model: str | None = None) -> TargetVersions:
    # embedding_model reflects the ACTUAL producer (may be "fake" offline), so a later switch to a
    # real provider registers as a config change and triggers a rebuild.
    return TargetVersions(
        parser_version=settings.parser_version,
        chunker_version=settings.chunker_version,
        contextualization_version=settings.contextualization_version,
        retrieval_schema_version=settings.retrieval_schema_version,
        embedding_model=embedding_model or settings.embedding_model,
    )


def handle_sync_page(
    session: Session,
    *,
    page_id: int,
    gateway: ConfluenceGateway,
    settings: Settings,
    tags: list[str] | None = None,
) -> SyncOutcome:
    meta = gateway.get_page_meta(page_id)
    if meta is None:
        # source no longer exists / inaccessible -> remove from live index
        from app.platform.db.enums import PageStatus

        deactivate_page(session, page_id=page_id, status=PageStatus.deleted)
        return SyncOutcome(action="gone", classes=["status_changed"], page_id=page_id)

    services = build_ingestion_services(settings)
    target = target_versions(settings, embedding_model=services.embedding_model)
    local = get_local_state(session, page_id)
    page_status = map_page_status(meta.status)
    space_key = str(meta.space_id)

    labels = gateway.get_labels(page_id)
    restrictions = gateway.get_restrictions(page_id)
    attachments = gateway.get_attachments(page_id)

    need_body = decide_body_fetch(local, meta, target)
    blocks: list[norm.Block] | None = None
    if need_body:
        page = gateway.get_page(page_id)
        blocks = norm.normalize_body(page.body_storage) if page else []

    decision = classify(
        local=local,
        meta=meta,
        target=target,
        labels=labels,
        restrictions=restrictions,
        space_key=space_key,
        attachments=attachments,
        blocks=blocks,
    )

    if decision.is_delete:
        deactivate_page(session, page_id=page_id, status=page_status)
        return SyncOutcome(action="deactivated", classes=["status_changed"], page_id=page_id)

    # PLAN 4.3: persist the real principal list, not just its hash (ADR-0004/0005 page-level ACL).
    # `restrictions` is fetched fresh above on every sync; only write when it actually changed (or
    # on first index) to avoid a redundant delete+insert on every reconcile tick. Deferred until
    # after `page_source` is guaranteed to exist (the FK target) — first index creates it below in
    # `stage_and_activate`, so this can't run before branching on `rebuild`.
    restrictions_changed = local is None or decision.access_scope_hash != local.access_scope_hash

    rebuild = local is None or bool(decision.classes & _REBUILD_CLASSES)
    if rebuild:
        if blocks is None:  # safety: rebuild requires the body
            page = gateway.get_page(page_id)
            blocks = norm.normalize_body(page.body_storage) if page else []
        hashes = PageHashes(
            content_hash=norm.content_hash(blocks),
            structure_hash=norm.structure_hash(blocks),
            labels_hash=decision.labels_hash,
            access_scope_hash=decision.access_scope_hash,
            attachment_manifest_hash=decision.attachment_manifest_hash,
        )
        stage_and_activate(
            session,
            meta=meta,
            blocks=blocks,
            hashes=hashes,
            target=target,
            page_status=page_status,
            services=services,
            tags=tags,
        )
        if restrictions_changed:
            _replace_restrictions(session, page_id=page_id, principals=restrictions)
        return SyncOutcome(
            action="indexed", classes=sorted(c.value for c in decision.classes), page_id=page_id
        )

    if decision.meaningful:
        _apply_metadata_only(session, meta, decision, page_status, tags=tags)
        if restrictions_changed:
            _replace_restrictions(session, page_id=page_id, principals=restrictions)
        return SyncOutcome(
            action="metadata_only",
            classes=sorted(c.value for c in decision.classes),
            page_id=page_id,
        )

    _touch_reconciled(session, page_id)
    return SyncOutcome(action="no_change", classes=["no_change"], page_id=page_id)


def _replace_restrictions(session: Session, *, page_id: int, principals: list[str]) -> None:
    """Full replace of a page's persisted ACL — mirrors ``restrictions`` being the current,
    complete list from Confluence, not a delta. An empty list correctly leaves zero rows
    (unrestricted)."""
    session.execute(delete(PageRestriction).where(PageRestriction.page_id == page_id))
    if principals:
        session.execute(
            insert(PageRestriction),
            [{"page_id": page_id, "principal": p} for p in dict.fromkeys(principals)],
        )


def handle_delete_page(session: Session, *, page_id: int, status: str) -> SyncOutcome:
    deactivate_page(session, page_id=page_id, status=map_page_status(status))
    return SyncOutcome(action="deactivated", classes=["status_changed"], page_id=page_id)


def _apply_metadata_only(session, meta, decision, page_status, *, tags=None) -> None:
    """Update registry + propagate retrieval-relevant metadata to chunks WITHOUT re-embedding."""
    ps = session.get(PageSource, meta.page_id)
    if ps is None:
        return
    now = datetime.now(UTC)
    ps.title = meta.title
    ps.parent_id = meta.parent_id
    ps.source_url = meta.source_url
    ps.page_status = page_status
    ps.source_modified_at = meta.version_created_at
    if decision.labels_hash is not None:
        ps.labels_hash = decision.labels_hash
    if decision.access_scope_hash is not None:
        ps.access_scope_hash = decision.access_scope_hash
    if decision.attachment_manifest_hash is not None:
        ps.attachment_manifest_hash = decision.attachment_manifest_hash
    if tags is not None:
        ps.tags = list(tags)
    ps.last_indexed_at = now
    ps.updated_at = now
    if ps.active_doc_version_id is not None:
        values: dict = {
            "title": meta.title,
            "source_url": meta.source_url,
            "page_status": page_status,
        }
        if decision.access_scope_hash is not None:
            values["access_scope"] = decision.access_scope_hash
        if tags is not None:
            values["tags"] = list(tags)
        session.execute(
            update(Chunk).where(Chunk.doc_version_id == ps.active_doc_version_id).values(**values)
        )
    session.flush()


def _touch_reconciled(session: Session, page_id: int) -> None:
    ps = session.get(PageSource, page_id)
    if ps is not None:
        ps.last_reconciled_at = datetime.now(UTC)
        session.flush()
