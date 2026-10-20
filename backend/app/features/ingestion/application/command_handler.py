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
from app.features.ingestion.domain.applicability import (
    applies_to_payload,
    validate_applies_to,
)
from app.features.ingestion.domain.applies_to_parsing import extract_applies_to
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
    applicability: list | None = None
    applicability_known = False  # True only when the body was fetched this sync
    if need_body:
        blocks, applicability = _normalize_fetched_body(gateway, page_id, settings)
        applicability_known = True

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
            blocks, applicability = _normalize_fetched_body(gateway, page_id, settings)
            applicability_known = True
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
            labels=list(labels),
            applicability=applicability,
        )
        if restrictions_changed:
            _replace_restrictions(session, page_id=page_id, principals=restrictions)
        return SyncOutcome(
            action="indexed", classes=sorted(c.value for c in decision.classes), page_id=page_id
        )

    # §D.0 scope restamp: cmd.scopes is authoritative (recognized_labels ∩ authorized), but
    # classify() compares only page-side state — a recognized-set or source_scope allow-list
    # edit changes neither the page nor its labels_hash. Comparing the stamped tags here is
    # what lets the complete sweep restamp (gap A: a scope added to the tag map; gap B: a
    # narrowed allow-list whose stale tags would keep satisfying the RLS overlap forever).
    scopes_drifted = local is not None and set(local.tags) != set(final_tags)

    # mi-applies (8.2.2): the Applies-to table is lifted out of the body before hashing,
    # so a table-only edit changes no content hash — comparing the freshly parsed payload
    # against the stamped one is what routes a metadata edit (changed OR removed record)
    # to the same restamp path, invalidating stale eligibility with no re-embed. Only
    # compared when the body was fetched this sync; the record cannot change without one.
    applicability_drifted = (
        local is not None and applicability_known and applicability != local.applicability
    )

    if decision.meaningful or scopes_drifted or applicability_drifted:
        _apply_metadata_only(
            session,
            meta,
            decision,
            page_status,
            tags=final_tags,
            labels=list(labels),
            applicability=applicability if applicability_known else _KEEP,
        )
        if restrictions_changed:
            _replace_restrictions(session, page_id=page_id, principals=restrictions)
        if decision.meaningful:
            classes = sorted(c.value for c in decision.classes)
        else:
            classes = (["applicability_restamped"] if applicability_drifted else []) + (
                ["scopes_restamped"] if scopes_drifted else []
            )
        return SyncOutcome(action="metadata_only", classes=classes, page_id=page_id)

    _touch_reconciled(session, page_id)
    return SyncOutcome(action="no_change", classes=["no_change"], page_id=page_id)


def _normalize_fetched_body(
    gateway: ConfluenceGateway, page_id: int, settings: Settings
) -> tuple[list[norm.Block], list | None]:
    """Fetch + split the body: normalized blocks (Applies-to tables lifted out) and the
    validated applicability payload (mi-applies, 8.2.2).

    The tables are removed BEFORE normalization so they are metadata, never chunk
    content, and a table-only edit changes no content hash. An authored-but-invalid
    table raises ``ApplicabilityValidationError`` out of the sync — loud by named
    reason, never a silent fall-back to label-only (the job fails; the previously
    indexed state survives untouched)."""
    page = gateway.get_page(page_id)
    if page is None:
        return [], None
    extraction = extract_applies_to(page.body_storage)
    blocks = norm.normalize_body(extraction.body_storage)
    if not extraction.rules:
        return blocks, None  # no record: the documented label-only default
    record = validate_applies_to(
        extraction.rules,
        settings.product_catalog,
        settings.platform_registry.platform_keys(),
    )
    return blocks, applies_to_payload(record)


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


# Sentinel for _apply_metadata_only: the body was not fetched this sync, so the stamped
# applicability is kept as-is (None is a real value: "the record was removed").
_KEEP = object()


def _apply_metadata_only(
    session, meta, decision, page_status, *, tags=None, labels=None, applicability=_KEEP
) -> None:
    """Update registry + propagate retrieval-relevant metadata to chunks WITHOUT re-embedding."""
    ps = session.get(PageSource, meta.page_id)
    if ps is None:
        return
    now = datetime.now(UTC)
    if meta.version_number > ps.current_cf_version:
        # The revision is fully consumed here (the body was fetched and its content
        # proved unchanged — only metadata moved), so advance the high-water mark or
        # every later sweep re-flags the same version as drift forever.
        ps.current_cf_version = meta.version_number
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
    if labels is not None:
        ps.labels = list(labels)  # raw labels restamp (ADR-directed-source-target-routing-labels D3, mi-labels): no re-embed
    if applicability is not _KEEP:
        ps.applicability = applicability  # mi-applies 8.2.2: restamp (None = removed)
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
        if labels is not None:
            values["labels"] = list(labels)
        if applicability is not _KEEP:
            values["applicability"] = applicability
        session.execute(
            update(Chunk).where(Chunk.doc_version_id == ps.active_doc_version_id).values(**values)
        )
    session.flush()


def _touch_reconciled(session: Session, page_id: int) -> None:
    ps = session.get(PageSource, page_id)
    if ps is not None:
        ps.last_reconciled_at = datetime.now(UTC)
        session.flush()
