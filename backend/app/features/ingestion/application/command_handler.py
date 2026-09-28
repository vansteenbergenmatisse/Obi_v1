"""Apply a decided :class:`SyncCommand` to the store — the ingestion layer's only entry point.

This is the "do the work" half that used to live in
``confluence_sync.application.sync_service.handle_sync_page``. It knows nothing
about webhooks, sweeps, ``source_scope``, or membership: the trigger layer already
decided (``upsert`` vs ``delete``) and computed the authoritative ``scopes``.
Ingestion just executes:

* ``upsert`` → fetch body · normalize · classify (rebuild vs metadata-only vs
  no-change, an ingestion-internal optimization) · chunk · contextualize · embed ·
  version · swap · write metadata + restrictions, stamping exactly ``cmd.scopes``.
* ``delete`` → hard-purge every row for the page (idempotent: a no-op on a page
  that was never indexed).

Imports its own feature's internals by full submodule path (never through the
``app.features.ingestion`` root — that would trip the self-facade guard) and the
cross-layer contract from ``app.shared``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, insert, update
from sqlalchemy.orm import Session

from app.features.ingestion.application.services import build_ingestion_services
from app.features.ingestion.application.versioning import (
    PageHashes,
    purge_page,
    stage_and_activate,
)
from app.features.ingestion.domain import normalization as norm
from app.features.ingestion.domain.attachment_extraction import (
    attachment_to_blocks,
    extract_attachment,
)
from app.features.ingestion.domain.change_detection import (
    ChangeClass,
    TargetVersions,
    classify,
    decide_body_fetch,
    map_page_status,
)
from app.features.ingestion.infrastructure.page_source_repo import get_local_state
from app.platform.clients import ConfluenceGateway
from app.platform.config import Settings
from app.platform.logging import get_logger
from app.shared.sync_command import SyncCommand, SyncOutcome
from schema.models import Chunk, PageRestriction, PageSource

log = get_logger("ingestion.command_handler")

# Change classes that force a full rebuild (every child re-embedded, no vector reused —
# sync rule 6). A title rename rebuilds so no stale title survives in a reused vector; it is
# safe against uq_document_version_idem because a Confluence title edit bumps cf_version.
# attachment_changed is deliberately excluded: attachment versions are independent of the
# page's cf_version, so a rebuild triggered by an attachment-only edit would attempt a second
# DocumentVersion row at the SAME cf_version and raise IntegrityError. An attachment change with
# no other page change waits for the next rebuild-triggering event.
_REBUILD_CLASSES = {
    ChangeClass.body_changed,
    ChangeClass.section_added,
    ChangeClass.section_updated,
    ChangeClass.section_removed,
    ChangeClass.section_moved,
    ChangeClass.title_changed,
    ChangeClass.index_config_change,
}


def target_versions(settings: Settings, embedding_model: str | None = None) -> TargetVersions:
    # embedding_model reflects the ACTUAL producer (may be "fake" offline), so a later switch to
    # a real provider registers as a config change and triggers a rebuild.
    return TargetVersions(
        parser_version=settings.parser_version,
        chunker_version=settings.chunker_version,
        contextualization_version=settings.contextualization_version,
        retrieval_schema_version=settings.retrieval_schema_version,
        embedding_model=embedding_model or settings.embedding_model,
    )


def apply_sync_command(
    session: Session,
    cmd: SyncCommand,
    gateway: ConfluenceGateway,
    settings: Settings,
) -> SyncOutcome:
    """Execute one decided command. Structurally satisfies ``confluence_sync``'s IngestionSink."""
    if cmd.action == "delete":
        # Hard purge (owner decision 2026-09-25): remove every row, idempotent on an
        # unindexed page. A later restore re-indexes from Confluence as a first index. The
        # outcome distinguishes a real removal ("purged") from a no-op on a page that was never
        # indexed ("skipped") — the outcome-based analogue of the pre-split skipped/unlabeled path.
        existed = purge_page(session, page_id=cmd.page_id)
        if existed:
            return SyncOutcome(action="purged", classes=["status_changed"], page_id=cmd.page_id)
        return SyncOutcome(action="skipped", classes=["skipped"], page_id=cmd.page_id)

    return _apply_upsert(session, cmd, gateway, settings)


def _apply_upsert(
    session: Session,
    cmd: SyncCommand,
    gateway: ConfluenceGateway,
    settings: Settings,
) -> SyncOutcome:
    page_id = cmd.page_id
    meta = gateway.get_page_meta(page_id)
    if meta is None:
        # Raced with a delete between decide and apply — purge and report gone.
        purge_page(session, page_id=page_id)
        return SyncOutcome(action="gone", classes=["status_changed"], page_id=page_id)

    services = build_ingestion_services(settings)
    target = target_versions(settings, embedding_model=services.embedding_model)
    local = get_local_state(session, page_id)
    page_status = map_page_status(meta.status)
    space_key = str(meta.space_id)

    labels = gateway.get_labels(page_id)
    restrictions = gateway.get_restrictions(page_id)
    attachments = gateway.get_attachments(page_id)
    # scopes are authoritative — computed by the trigger's decide_command as
    # (recognized_labels ∩ authorized). Ingestion stamps exactly these; it never re-derives
    # membership from labels or source_scope.
    final_tags = list(cmd.scopes)

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
        # Status flipped to trashed/archived/deleted between decide and apply — purge.
        purge_page(session, page_id=page_id)
        return SyncOutcome(action="purged", classes=["status_changed"], page_id=page_id)

    restrictions_changed = local is None or decision.access_scope_hash != local.access_scope_hash

    rebuild = local is None or bool(decision.classes & _REBUILD_CLASSES)
    if rebuild:
        if blocks is None:  # safety: a rebuild requires the body
            page = gateway.get_page(page_id)
            blocks = norm.normalize_body(page.body_storage) if page else []
        # classify() always sets these three metadata hashes (they need no body), so they are
        # never None on the rebuild path — assert the invariant to satisfy the type checker.
        assert decision.labels_hash is not None
        assert decision.access_scope_hash is not None
        assert decision.attachment_manifest_hash is not None
        hashes = PageHashes(
            content_hash=norm.content_hash(blocks),
            structure_hash=norm.structure_hash(blocks),
            labels_hash=decision.labels_hash,
            access_scope_hash=decision.access_scope_hash,
            attachment_manifest_hash=decision.attachment_manifest_hash,
        )
        attachment_blocks = _attachment_blocks(gateway, page_id, attachments, settings)
        stage_and_activate(
            session,
            meta=meta,
            blocks=blocks + attachment_blocks,
            hashes=hashes,
            target=target,
            page_status=page_status,
            services=services,
            tags=final_tags,
        )
        if restrictions_changed:
            _replace_restrictions(session, page_id=page_id, principals=restrictions)
        return SyncOutcome(
            action="indexed", classes=sorted(c.value for c in decision.classes), page_id=page_id
        )

    if decision.meaningful:
        _apply_metadata_only(session, meta, decision, page_status, tags=final_tags)
        if restrictions_changed:
            _replace_restrictions(session, page_id=page_id, principals=restrictions)
        return SyncOutcome(
            action="metadata_only",
            classes=sorted(c.value for c in decision.classes),
            page_id=page_id,
        )

    _touch_reconciled(session, page_id)
    return SyncOutcome(action="no_change", classes=["no_change"], page_id=page_id)


def _attachment_blocks(
    gateway: ConfluenceGateway, page_id: int, attachments: list[dict], settings: Settings
) -> list[norm.Block]:
    """Download + extract every attachment's text as blocks. Fails soft per attachment.

    Deterministic order (by attachment id) keeps section identity stable across syncs. Bounded
    by ``confluence_attachment_max_per_page`` (a safety ceiling). Oversized-by-metadata or
    unfetchable attachments are skipped and logged, never raised.
    """
    blocks: list[norm.Block] = []
    ordered = sorted(attachments, key=lambda a: str(a.get("id") or ""))
    max_per_page = settings.confluence_attachment_max_per_page
    if len(ordered) > max_per_page:
        log.warning(
            "confluence_attachment_count_capped",
            page_id=page_id,
            found=len(ordered),
            max_per_page=max_per_page,
        )
        ordered = ordered[:max_per_page]
    for att in ordered:
        title = att.get("title") or ""
        download_link = att.get("downloadLink")
        file_size = att.get("fileSize")
        if not download_link or not title:
            continue
        max_bytes = settings.confluence_attachment_max_bytes
        if isinstance(file_size, int) and file_size > max_bytes:
            log.warning(
                "confluence_attachment_skipped_oversized_metadata",
                page_id=page_id,
                title=title,
                file_size=file_size,
                max_bytes=max_bytes,
            )
            continue
        data = gateway.download_attachment(download_link, max_bytes=max_bytes)
        if data is None:
            log.warning("confluence_attachment_skipped_unfetchable", page_id=page_id, title=title)
            continue
        result = extract_attachment(filename=title, media_type=att.get("mediaType"), data=data)
        blocks.extend(attachment_to_blocks(title=title, text=result.text))
    return blocks


def _replace_restrictions(session: Session, *, page_id: int, principals: list[str]) -> None:
    """Full replace of a page's persisted ACL — ``principals`` is the complete current list."""
    session.execute(delete(PageRestriction).where(PageRestriction.page_id == page_id))
    if principals:
        session.execute(
            insert(PageRestriction),
            [{"page_id": page_id, "principal": p} for p in dict.fromkeys(principals)],
        )


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
