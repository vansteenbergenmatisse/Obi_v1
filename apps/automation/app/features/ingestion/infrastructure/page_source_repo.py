"""Read/write access to the page_source registry + document identity."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.ingestion.domain.change_detection import LocalState
from app.platform.db.models import Document, PageSource


def get_page_source(session: Session, page_id: int) -> PageSource | None:
    return session.get(PageSource, page_id)


def get_local_state(session: Session, page_id: int) -> LocalState | None:
    ps = session.get(PageSource, page_id)
    if ps is None:
        return None
    return LocalState(
        current_cf_version=ps.current_cf_version,
        page_status=ps.page_status,
        title=ps.title,
        parent_id=ps.parent_id,
        content_hash=ps.content_hash,
        structure_hash=ps.structure_hash,
        attachment_manifest_hash=ps.attachment_manifest_hash,
        access_scope_hash=ps.access_scope_hash,
        labels_hash=ps.labels_hash,
        parser_version=ps.parser_version,
        chunker_version=ps.chunker_version,
        contextualization_version=ps.contextualization_version,
        contextualization_and_schema=ps.retrieval_schema_version,
        embedding_model=ps.embedding_model,
    )


def ensure_document(session: Session, page_id: int) -> Document:
    doc = session.execute(
        select(Document).where(Document.page_id == page_id)
    ).scalar_one_or_none()
    if doc is None:
        doc = Document(page_id=page_id)
        session.add(doc)
        session.flush()
    return doc
