"""Immutable versioning with atomic activation and rollback.

A page's indexed content is built into a *staging* ``document_version`` (with its chunks
``is_active=False``), validated, then activated in the caller's single transaction via a pointer
swap. Obsolete chunks are deleted only after activation; N superseded versions are retained for
instant rollback (ADR-0002).

Phase 3 builds real token-aware parent/child chunks with contextual ``retrieval_content`` and
embeddings, reusing embeddings for unchanged chunks (incremental diff) and populating the dense
(``embedding``) and keyword (``tsv``) columns the retrieval layer searches.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, literal_column, select, update
from sqlalchemy.orm import Session

from app.features.ingestion.application.contextualizer import ContextItem
from app.features.ingestion.application.services import IngestionServices
from app.features.ingestion.domain import normalization as norm
from app.features.ingestion.domain.change_detection import TargetVersions
from app.features.ingestion.domain.chunk_diff import diff_chunks
from app.features.ingestion.domain.chunking import PlannedChunk, plan_chunks
from app.features.ingestion.infrastructure.page_source_repo import ensure_document
from app.platform.clients.confluence_client import ConfluencePageMeta
from app.platform.db.enums import DocState, PageStatus
from app.platform.db.models import KIND_CHILD, KIND_PARENT, Chunk, DocumentVersion, PageSource

DEFAULT_RETAIN_SUPERSEDED = 2


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
    old_children: list[Chunk],
) -> list[Chunk]:
    """Token-aware parent/child chunks with contextual retrieval_content, embeddings and tsv.

    Children whose content is unchanged (diff vs ``old_children``) reuse their prior embedding and
    retrieval_content; only new/edited children are contextualized and embedded.
    """
    plan = plan_chunks(
        page_id=meta.page_id, blocks=blocks, config=services.config, counter=services.counter
    )
    child_plans: list[PlannedChunk] = [c for pp in plan for c in pp.children]
    retrieval, embeddings = _resolve_children(meta, blocks, child_plans, old_children, services)

    common = dict(
        doc_version_id=doc_version_id,
        page_id=meta.page_id,
        cf_version=meta.version_number,
        title=meta.title,
        space_id=meta.space_id,
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
    old_children: list[Chunk],
    services: IngestionServices,
) -> tuple[list[str], list[list[float] | None]]:
    """Reuse embeddings for unchanged children; contextualize + embed only new/edited ones."""
    n = len(child_plans)
    retrieval: list[str] = [""] * n
    embeddings: list[list[float] | None] = [None] * n

    # Chunk exposes the key attrs as SQLAlchemy Mapped[bytes]; structurally a HasKeys at runtime.
    diff = diff_chunks(old_children, child_plans)  # pyright: ignore[reportArgumentType]
    for match in diff.reuse:
        old = old_children[match.old_index]
        retrieval[match.new_index] = old.retrieval_content
        embeddings[match.new_index] = old.embedding

    reembed = diff.reembed_indexes
    if reembed:
        items = [
            ContextItem(
                title=meta.title,
                heading_path=child_plans[i].heading_path,
                text=child_plans[i].text,
            )
            for i in reembed
        ]
        doc_text = "\n".join(b.text for b in blocks if b.text)
        rcontents = services.contextualizer.contextualize(document_text=doc_text, items=items)
        vectors = services.embedder.embed(rcontents)
        for j, i in enumerate(reembed):
            retrieval[i] = rcontents[j]
            embeddings[i] = vectors[j]
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
) -> DocumentVersion:
    """Stage a new version, validate, and atomically activate it. Single transaction."""
    doc = ensure_document(session, meta.page_id)
    # Reuse prior embeddings only when the embedding pipeline is unchanged; a model/dim/schema
    # change routes through the full re-embed release gate (all children rebuilt under the new
    # config, then swapped atomically — the prior version stays retained for rollback).
    old_children = reusable_active_children(
        session, meta.page_id, target=target, services=services
    )

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
        old_children=old_children,
    )
    # link parent<-child and prev/next among children in reading order
    _link_chunks(session, chunks)

    # validate staging before touching the live set
    children = [c for c in chunks if c.kind == KIND_CHILD]
    if not children:
        new_version.state = DocState.failed
        session.flush()
        raise ValueError(f"staging produced no child chunks for page {meta.page_id}")

    _activate(session, meta=meta, hashes=hashes, target=target, page_status=page_status,
              new_version=new_version, embedding_dim=services.embedding_dim)
    _gc_superseded(session, document_id=doc.id, retain=retain_superseded)
    return new_version


def reusable_active_children(
    session: Session, page_id: int, *, target: TargetVersions, services: IngestionServices
) -> list[Chunk]:
    """Active child chunks eligible for embedding reuse — empty when the pipeline config changed.

    An embedding-model, embedding-dim, contextualization-version or retrieval-schema change makes
    prior vectors incomparable (or the wrong width), so reuse is disabled and every child is
    re-embedded under the new configuration (the full re-embed release gate).
    """
    ps = session.get(PageSource, page_id)
    if ps is None or ps.active_doc_version_id is None:
        return []
    active = session.get(DocumentVersion, ps.active_doc_version_id)
    if active is None or not _pipeline_config_matches(active, target, services):
        return []
    return list(
        session.execute(
            select(Chunk).where(
                Chunk.doc_version_id == ps.active_doc_version_id,
                Chunk.kind == KIND_CHILD,
            )
        ).scalars()
    )


def _pipeline_config_matches(
    active: DocumentVersion, target: TargetVersions, services: IngestionServices
) -> bool:
    return (
        active.embedding_model == services.embedding_model
        and active.embedding_dim == services.embedding_dim
        and active.contextualization_version == target.contextualization_version
        and active.retrieval_schema_version == target.retrieval_schema_version
    )


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
    superseded = session.execute(
        select(DocumentVersion.id)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.state == DocState.superseded,
        )
        .order_by(DocumentVersion.superseded_at.desc())
    ).scalars().all()
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


def rollback_to(session: Session, *, page_id: int, target_version_id: int) -> bool:
    """Roll back to a retained superseded version (atomic pointer swap)."""
    ps = session.get(PageSource, page_id)
    target = session.get(DocumentVersion, target_version_id)
    if ps is None or target is None or target.page_id != page_id:
        return False
    now = _now()
    current_id = ps.active_doc_version_id
    if current_id is not None and current_id != target_version_id:
        session.execute(
            update(DocumentVersion)
            .where(DocumentVersion.id == current_id)
            .values(state=DocState.superseded, superseded_at=now)
        )
        session.execute(
            update(Chunk).where(Chunk.doc_version_id == current_id).values(is_active=False)
        )
    target.state = DocState.active
    target.activated_at = now
    target.superseded_at = None
    session.execute(
        update(Chunk).where(Chunk.doc_version_id == target_version_id).values(is_active=True)
    )
    ps.active_doc_version_id = target_version_id
    ps.current_cf_version = target.cf_version
    ps.updated_at = now
    session.flush()
    return True
