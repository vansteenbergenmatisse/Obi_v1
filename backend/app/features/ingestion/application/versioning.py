"""Immutable versioning with atomic activation.

A page's indexed content is built into a *staging* ``document_version`` (with its chunks
``is_active=False``), validated, then activated in the caller's single transaction via a pointer
swap. The just-superseded version and its chunks are deleted in that same transaction — nothing is
retained (sync rule 6 / D1: retain 0, no rollback window).

Phase 3 builds real token-aware parent/child chunks with contextual ``retrieval_content`` and
embeddings; every child is contextualised and embedded afresh on every rebuild (sync rule 6 — no
vector is reused from an old version), populating the dense (``embedding``) and keyword (``tsv``)
columns the retrieval layer searches.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, literal_column, select, update
from sqlalchemy.orm import Session

from app.features.ingestion.application.contextualizer import ContextItem
from app.features.ingestion.application.services import IngestionServices
from app.features.ingestion.domain import normalization as norm
from app.features.ingestion.domain.change_detection import TargetVersions
from app.features.ingestion.domain.chunking import PlannedChunk, plan_chunks
from app.features.ingestion.infrastructure.page_source_repo import ensure_document
from app.platform.clients import ConfluencePageMeta
from schema.enums import DocState, PageStatus
from schema.models import (
    KIND_CHILD,
    KIND_PARENT,
    Chunk,
    Document,
    DocumentVersion,
    PageSource,
)

# Sync rule 6 / D1: retain 0 superseded versions — the just-superseded version and its chunks are
# deleted in the same transaction as the swap. No rollback window (rollback is retired); recovery is
# a fresh re-index from Confluence, the source of truth.
DEFAULT_RETAIN_SUPERSEDED = 0

# Source-tag activation seam (ADR-source-id-row-security-with-reader-writer-roles). Confluence is
# the only source today, so these are
# constants; a second source turns them into a parameter threaded from the sync caller.
_SOURCE_TYPE = "confluence"
_SOURCE_ID = "confluence:default"


def _tsv(*parts: str):
    """SQL expr: to_tsvector('english', <joined parts>) — config a literal, text a bind param."""
    source = " ".join(p for p in parts if p)
    return func.to_tsvector(literal_column("'english'"), source)


@dataclass
class PageHashes:
    content_hash: bytes
    structure_hash: bytes
    labels_hash: bytes
    access_scope_hash: bytes
    attachment_manifest_hash: bytes


def _now() -> datetime:
    return datetime.now(UTC)


def build_chunks(
    *,
    meta: ConfluencePageMeta,
    blocks: list[norm.Block],
    doc_version_id: int,
    page_status: PageStatus,
    access_scope_hash: bytes,
    target: TargetVersions,
    services: IngestionServices,
    tags: list[str] | None = None,
    labels: list[str] | None = None,
    applicability: list | None = None,
) -> list[Chunk]:
    """Token-aware parent/child chunks with contextual retrieval_content, embeddings and tsv.

    Every child is contextualized and embedded afresh (sync rule 6 — no vector is reused from an
    old version).
    """
    plan = plan_chunks(
        page_id=meta.page_id, blocks=blocks, config=services.config, counter=services.counter
    )
    child_plans: list[PlannedChunk] = [c for pp in plan for c in pp.children]
    retrieval, embeddings = _resolve_children(meta, blocks, child_plans, services)

    common = dict(
        doc_version_id=doc_version_id,
        page_id=meta.page_id,
        cf_version=meta.version_number,
        title=meta.title,
        space_id=meta.space_id,
        # single source-tag activation seam (ADR-source-id-row-security-with-reader-writer-roles): a
        # constant while Confluence is the only
        # source; becomes a parameter threaded from the caller when a second source lands.
        # tags (PLAN 3.5.6): threaded from the covering source_scope root(s), [] when none.
        source_type=_SOURCE_TYPE,
        source_id=_SOURCE_ID,
        tags=list(tags) if tags is not None else [],
        # raw Confluence labels (ADR-directed-source-target-routing-labels D1, mi-labels); the
        # routing axis, distinct from tags.
        labels=list(labels) if labels is not None else [],
        # validated "Applies to" payload (mi-applies, 8.2.2); None = label-only default.
        applicability=applicability,
        source_url=meta.source_url,
        page_status=page_status,
        retrieval_schema_version=target.retrieval_schema_version,
        embedding_model=services.embedding_model,
        access_scope=access_scope_hash,
        is_active=False,
    )

    chunks: list[Chunk] = []
    seq = 0
    ci = 0
    for pp in plan:
        p = pp.parent
        chunks.append(
            Chunk(
                kind=KIND_PARENT,
                stable_key=p.stable_key,
                positional_key=p.positional_key,
                content_key=p.content_key,
                content_hash=p.content_key,
                seq=seq,
                heading_path=list(p.heading_path),
                location=p.location,
                display_content=p.text,
                retrieval_content=p.text,  # parents are not embedded
                tokens=p.tokens,
                embedding=None,
                **common,
            )
        )
        seq += 1
        for c in pp.children:
            chunks.append(
                Chunk(
                    kind=KIND_CHILD,
                    stable_key=c.stable_key,
                    positional_key=c.positional_key,
                    content_key=c.content_key,
                    content_hash=c.content_key,
                    seq=seq,
                    heading_path=list(c.heading_path),
                    location=c.location,
                    display_content=c.text,
                    retrieval_content=retrieval[ci],
                    tokens=c.tokens,
                    embedding=embeddings[ci],
                    tsv=_tsv(meta.title, " > ".join(c.heading_path), c.text),
                    **common,
                )
            )
            seq += 1
            ci += 1
    return chunks


def _resolve_children(
    meta: ConfluencePageMeta,
    blocks: list[norm.Block],
    child_plans: list[PlannedChunk],
    services: IngestionServices,
) -> tuple[list[str], list[list[float] | None]]:
    """Contextualize and embed every child afresh (sync rule 6 — no vector reused from an old
    version; a rebuild embeds the whole page, so no stale title can hide in a reused vector)."""
    if not child_plans:
        return [], []
    items = [
        ContextItem(
            title=meta.title,
            heading_path=c.heading_path,
            text=c.text,
        )
        for c in child_plans
    ]
    doc_text = "\n".join(b.text for b in blocks if b.text)
    retrieval = services.contextualizer.contextualize(document_text=doc_text, items=items)
    embeddings: list[list[float] | None] = list(services.embedder.embed(retrieval))
    return retrieval, embeddings


def stage_and_activate(
    session: Session,
    *,
    meta: ConfluencePageMeta,
    blocks: list[norm.Block],
    hashes: PageHashes,
    target: TargetVersions,
    page_status: PageStatus,
    services: IngestionServices,
    retain_superseded: int = DEFAULT_RETAIN_SUPERSEDED,
    tags: list[str] | None = None,
    labels: list[str] | None = None,
    applicability: list | None = None,
) -> DocumentVersion:
    """Stage a new version, validate, and atomically activate it. Single transaction."""
    doc = ensure_document(session, meta.page_id)
    new_version = DocumentVersion(
        document_id=doc.id,
        page_id=meta.page_id,
        cf_version=meta.version_number,
        state=DocState.staging,
        content_hash=hashes.content_hash,
        structure_hash=hashes.structure_hash,
        parser_version=target.parser_version,
        chunker_version=target.chunker_version,
        contextualization_version=target.contextualization_version,
        embedding_model=services.embedding_model,
        embedding_dim=services.embedding_dim,
        retrieval_schema_version=target.retrieval_schema_version,
    )
    session.add(new_version)
    session.flush()  # get new_version.id

    chunks = build_chunks(
        meta=meta,
        blocks=blocks,
        doc_version_id=new_version.id,
        page_status=page_status,
        access_scope_hash=hashes.access_scope_hash,
        target=target,
        services=services,
        tags=tags,
        labels=labels,
        applicability=applicability,
    )
    # link parent<-child and prev/next among children in reading order
    _link_chunks(session, chunks)

    # validate staging before touching the live set
    children = [c for c in chunks if c.kind == KIND_CHILD]
    if not children:
        new_version.state = DocState.failed
        session.flush()
        raise ValueError(f"staging produced no child chunks for page {meta.page_id}")

    _activate(
        session,
        meta=meta,
        hashes=hashes,
        target=target,
        page_status=page_status,
        new_version=new_version,
        embedding_dim=services.embedding_dim,
        tags=tags,
        labels=labels,
        applicability=applicability,
    )
    _gc_superseded(session, document_id=doc.id, retain=retain_superseded)
    return new_version


def _link_chunks(session: Session, chunks: list[Chunk]) -> None:
    parents = [c for c in chunks if c.kind == KIND_PARENT]
    children = [c for c in chunks if c.kind == KIND_CHILD]
    session.add_all(parents)
    session.flush()
    # map (section, parent_ordinal) -> parent id (a section may span multiple parents)
    parent_by_key = {
        (p.location.get("section"), p.location.get("parent_ordinal")): p.id for p in parents
    }
    for ch in children:
        key = (ch.location.get("section"), ch.location.get("parent_ordinal"))
        ch.parent_chunk_id = parent_by_key.get(key)
    session.add_all(children)
    session.flush()
    for i, ch in enumerate(children):
        ch.prev_chunk_id = children[i - 1].id if i > 0 else None
        ch.next_chunk_id = children[i + 1].id if i < len(children) - 1 else None
    session.flush()


def _activate(
    session: Session,
    *,
    meta: ConfluencePageMeta,
    hashes: PageHashes,
    target: TargetVersions,
    page_status: PageStatus,
    new_version: DocumentVersion,
    embedding_dim: int,
    tags: list[str] | None = None,
    labels: list[str] | None = None,
    applicability: list | None = None,
) -> None:
    now = _now()
    ps = session.get(PageSource, meta.page_id)
    old_version_id = ps.active_doc_version_id if ps else None

    # supersede the previously active version + deactivate its chunks
    if old_version_id is not None:
        session.execute(
            update(DocumentVersion)
            .where(DocumentVersion.id == old_version_id)
            .values(state=DocState.superseded, superseded_at=now)
        )
        session.execute(
            update(Chunk).where(Chunk.doc_version_id == old_version_id).values(is_active=False)
        )

    # activate the new version + its chunks
    new_version.state = DocState.active
    new_version.activated_at = now
    session.execute(
        update(Chunk).where(Chunk.doc_version_id == new_version.id).values(is_active=True)
    )

    # upsert the registry (must point active pointer AFTER new_version exists)
    if ps is None:
        ps = PageSource(page_id=meta.page_id)
        session.add(ps)
    ps.space_id = meta.space_id
    # source-tag seam (ADR-source-id-row-security-with-reader-writer-roles), mirrors the chunk stamp
    # above
    ps.source_type = _SOURCE_TYPE
    ps.source_id = _SOURCE_ID
    ps.tags = list(tags) if tags is not None else []
    # raw labels (ADR-directed-source-target-routing-labels D1, mi-labels)
    ps.labels = list(labels) if labels is not None else []
    ps.applicability = applicability  # mi-applies 8.2.2: None = no record = label-only
    ps.parent_id = meta.parent_id
    ps.current_cf_version = meta.version_number
    ps.active_doc_version_id = new_version.id
    ps.page_status = page_status
    ps.title = meta.title
    ps.source_url = meta.source_url
    ps.source_modified_at = meta.version_created_at
    ps.content_hash = hashes.content_hash
    ps.structure_hash = hashes.structure_hash
    ps.attachment_manifest_hash = hashes.attachment_manifest_hash
    ps.access_scope_hash = hashes.access_scope_hash
    ps.labels_hash = hashes.labels_hash
    ps.parser_version = target.parser_version
    ps.chunker_version = target.chunker_version
    ps.contextualization_version = target.contextualization_version
    ps.embedding_model = target.embedding_model
    ps.embedding_dim = embedding_dim
    ps.retrieval_schema_version = target.retrieval_schema_version
    ps.last_indexed_at = now
    ps.updated_at = now
    session.flush()


def _gc_superseded(session: Session, *, document_id: int, retain: int) -> None:
    """Delete obsolete versions beyond the retained rollback window (chunks cascade)."""
    superseded = (
        session.execute(
            select(DocumentVersion.id)
            .where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.state == DocState.superseded,
            )
            .order_by(DocumentVersion.superseded_at.desc())
        )
        .scalars()
        .all()
    )
    for vid in superseded[retain:]:
        session.execute(
            update(DocumentVersion).where(DocumentVersion.id == vid).values(state=DocState.failed)
        )
        obj = session.get(DocumentVersion, vid)
        if obj is not None:
            session.delete(obj)  # chunks cascade via FK ondelete
    session.flush()


def deactivate_page(session: Session, *, page_id: int, status: PageStatus) -> bool:
    """Handle trash/delete/archive: mark status and remove chunks from the live index."""
    ps = session.get(PageSource, page_id)
    if ps is None:
        return False
    ps.page_status = status
    ps.updated_at = _now()
    if ps.active_doc_version_id is not None:
        session.execute(
            update(Chunk)
            .where(Chunk.doc_version_id == ps.active_doc_version_id)
            .values(is_active=False, page_status=status)
        )
    session.flush()
    return True


def purge_page(session: Session, *, page_id: int) -> bool:
    """Remove a page from the store entirely (sync rules 1/2/7): every version, its document,
    every chunk, the page_source and its restriction rows. Unlike ``deactivate_page`` (which only
    flips ``is_active``), nothing survives on disk — so a database dump or a bug that ignores
    ``is_active`` cannot leak the content. A later restore/re-tag re-indexes from Confluence as a
    first index (``get_local_state`` returns ``None``), the source of truth.

    Ordered inside the caller's single transaction to respect the RESTRICT foreign keys
    (``document.page_id`` and ``document_version.document_id`` carry no cascade): release the
    deferred active-version pointer, delete the versions (chunks cascade), delete the document,
    then delete the page_source (page_restriction cascades). Returns whether a page row existed.
    """
    ps = session.get(PageSource, page_id)
    if ps is None:
        return False
    # Release the deferred FK pointer first so the version rows it references can be deleted.
    ps.active_doc_version_id = None
    session.flush()
    # Chunks cascade from document_version; page_restriction cascades from page_source.
    session.execute(delete(DocumentVersion).where(DocumentVersion.page_id == page_id))
    session.execute(delete(Document).where(Document.page_id == page_id))
    session.execute(delete(PageSource).where(PageSource.page_id == page_id))
    session.flush()
    return True
