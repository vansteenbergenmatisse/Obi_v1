"""Shared helpers for confluence_sync DB tests (not collected: filename is not test_*)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.features.confluence_sync.application.worker import drain, run_once
from app.platform.clients import ConfluenceGateway
from app.platform.config import Settings
from app.platform.jobs import enqueue_job
from schema.engine import get_sessionmaker, session_scope
from schema.enums import DocState
from schema.models import KIND_CHILD, Chunk, DocumentVersion, PageRestriction, PageSource


def enqueue_sync(page_id: int, cf_version: int | None, key: str) -> int | None:
    with session_scope() as s:
        return enqueue_job(
            s,
            job_type="sync_page",
            idempotency_key=key,
            payload={"event_type": "test"},
            page_id=page_id,
            cf_version=cf_version,
        )


def enqueue_delete(page_id: int, status: str, key: str) -> int | None:
    with session_scope() as s:
        return enqueue_job(
            s,
            job_type="delete_page",
            idempotency_key=key,
            payload={"status": status},
            page_id=page_id,
        )


def index_page(gateway: ConfluenceGateway, settings: Settings, page_id: int, version: int) -> None:
    """Seed a page into the index at a given version by running the real sync path."""
    gateway.set_version(page_id, version)
    enqueue_sync(page_id, version, key=f"seed:{page_id}:{version}")
    run_once(gateway, settings, owner="seed")


def run_worker(gateway: ConfluenceGateway, settings: Settings, owner: str = "test") -> list:
    return drain(gateway, settings, owner=owner, max_jobs=50)


def read():
    """A fresh read-only session (identity map isolated from writers)."""
    return get_sessionmaker()()


def active_version(page_id: int) -> DocumentVersion | None:
    with read() as s:
        ps = s.get(PageSource, page_id)
        if ps is None or ps.active_doc_version_id is None:
            return None
        return s.get(DocumentVersion, ps.active_doc_version_id)


def active_versions_count(page_id: int) -> int:
    with read() as s:
        doc_ids = (
            s.execute(
                select(DocumentVersion.id).where(
                    DocumentVersion.page_id == page_id, DocumentVersion.state == DocState.active
                )
            )
            .scalars()
            .all()
        )
        return len(doc_ids)


def active_child_chunks(page_id: int) -> list[Chunk]:
    with read() as s:
        return list(
            s.execute(
                select(Chunk).where(
                    Chunk.page_id == page_id,
                    Chunk.is_active.is_(True),
                    Chunk.kind == KIND_CHILD,
                )
            )
            .scalars()
            .all()
        )


def child_chunks_for_version(doc_version_id: int) -> list[Chunk]:
    """Every child chunk row for one document_version, regardless of is_active (panel vd-swap:
    a superseded version's rows persist, inactive, until i4-gc's retention window reaps them)."""
    with read() as s:
        return list(
            s.execute(
                select(Chunk).where(
                    Chunk.doc_version_id == doc_version_id, Chunk.kind == KIND_CHILD
                )
            )
            .scalars()
            .all()
        )


def restricted_principals(page_id: int) -> set[str]:
    """The persisted ACL for a page (PLAN 4.3); empty means unrestricted."""
    with read() as s:
        rows = (
            s.execute(select(PageRestriction.principal).where(PageRestriction.page_id == page_id))
            .scalars()
            .all()
        )
        return set(rows)


def count_versions(page_id: int) -> int:
    with read() as s:
        return s.execute(
            select(func.count(DocumentVersion.id)).where(DocumentVersion.page_id == page_id)
        ).scalar_one()
