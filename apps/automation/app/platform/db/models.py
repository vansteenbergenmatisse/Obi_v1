"""Core ORM for the versioned Confluence knowledge store.

This is app-wide technical schema shared by the confluence_sync, ingestion, retrieval and
rag_agent features (they own the *logic*; this module owns the *tables*). See ADR-0002 and
the migration in alembic/versions/0001_core_schema.py for the authoritative DDL.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from app.platform.config import get_settings
from app.platform.db.base import Base
from app.platform.db.enums import (
    DocState,
    EventProcStatus,
    JobStatus,
    PageStatus,
    ReconStatus,
)

EMB_DIM = get_settings().embedding_dim

# Provider tagging (ADR-0004). source_type is a coarse connector label constrained by a CHECK
# (not a PG enum, to avoid ALTER TYPE friction as connectors grow). The set is seeded with the
# planned sources so adding one is data, not a migration; source_id (e.g. "confluence:default")
# is the per-source isolation key that RLS and the explicit source filter both key on.
SOURCE_TYPES = ("confluence", "zendesk", "notion", "upload")
_SOURCE_TYPE_CHECK = "source_type IN ('confluence', 'zendesk', 'notion', 'upload')"

# chunk.kind
KIND_PARENT = 0
KIND_CHILD = 1

# pgvector caps a `vector` HNSW index at 2000 dims. For higher-dimension models (e.g. OpenAI
# text-embedding-3-large at 3072) we index a half-precision cast — `halfvec` HNSW supports up to
# 4000 dims. Full-precision vectors stay in the column; only the index is half precision, which
# has negligible recall impact. See ADR-0002.
_HNSW_MAX_VECTOR_DIM = 2000
_HNSW_WITH = {"m": 16, "ef_construction": 200}
_HNSW_WHERE = "is_active AND kind = 1 AND embedding IS NOT NULL"


def _embedding_hnsw_index() -> Index:
    if EMB_DIM > _HNSW_MAX_VECTOR_DIM:
        return Index(
            "ix_chunk_embedding_hnsw",
            text(f"(embedding::halfvec({EMB_DIM})) halfvec_cosine_ops"),
            postgresql_using="hnsw",
            postgresql_with=_HNSW_WITH,
            postgresql_where=text(_HNSW_WHERE),
        )
    return Index(
        "ix_chunk_embedding_hnsw",
        "embedding",
        postgresql_using="hnsw",
        postgresql_with=_HNSW_WITH,
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=text(_HNSW_WHERE),
    )


def _pk() -> Mapped[int]:
    return mapped_column(BigInteger, primary_key=True, autoincrement=True)


def _ts_created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PageSource(Base):
    """One row per Confluence page: canonical registry + active-version pointer + hashes."""

    __tablename__ = "page_source"

    page_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Confluence page id
    space_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # provider tagging (ADR-0004): mirrors chunk so the registry records each page's source
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'confluence'")
    )
    source_id: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=text("'confluence:default'")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    current_cf_version: Mapped[int] = mapped_column(Integer, nullable=False)
    active_doc_version_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("document_version.id", deferrable=True, initially="DEFERRED"),
        nullable=True,
    )
    page_status: Mapped[PageStatus] = mapped_column(
        SAEnum(PageStatus, name="page_status", create_type=False), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # change-detection hashes (of the ACTIVE indexed state)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    structure_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    attachment_manifest_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    access_scope_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    labels_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # pipeline version stamps (of the ACTIVE indexed state)
    parser_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    chunker_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    contextualization_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_schema_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = _ts_created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("active_doc_version_id", name="uq_page_source_active_doc_version_id"),
        CheckConstraint(_SOURCE_TYPE_CHECK, name=conv("ck_page_source_source_type")),
        Index("ix_page_source_space_id", "space_id"),
        Index("ix_page_source_parent_id", "parent_id"),
        Index("ix_page_source_source_id", "source_id"),
        Index("ix_page_source_page_status", "page_status"),
        Index("ix_page_source_last_reconciled_at", "last_reconciled_at"),
    )


class PageRestriction(Base):
    """Persisted per-page principal read ACL (PLAN 4.3; ADR-0004 §page-level ACL / ADR-0005 §9).

    Presence of any row for a page means it is restricted to the listed principals; a page with
    no rows here is unrestricted — the same contract ``PrincipalPermissionPolicy.restrictions``
    already used when it was fixture-fed. Written by ``confluence_sync``'s ``handle_sync_page``
    whenever a page's restriction list changes; read by ``retrieval`` alongside RLS as the
    page-level security layer.
    """

    __tablename__ = "page_restriction"

    page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("page_source.page_id", ondelete="CASCADE"), primary_key=True
    )
    principal: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = _ts_created()


class Document(Base):
    """Logical, immutable identity of a page's indexed doc (one per page)."""

    __tablename__ = "document"

    id: Mapped[int] = _pk()
    # deferrable: page_source ⇄ document_version ⇄ document form an insert-order cycle on first
    # index (the registry row is written last, in the same txn). Checked at commit, not on insert.
    page_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("page_source.page_id", deferrable=True, initially="DEFERRED"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = _ts_created()


class DocumentVersion(Base):
    """Immutable staging/active snapshot of a page at a given Confluence version."""

    __tablename__ = "document_version"

    id: Mapped[int] = _pk()
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("document.id"), nullable=False)
    page_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # denormalized
    cf_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[DocState] = mapped_column(
        SAEnum(DocState, name="doc_state", create_type=False), nullable=False
    )

    content_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    structure_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    parser_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    chunker_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    contextualization_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_schema_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    built_by_job_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = _ts_created()
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "cf_version",
            "retrieval_schema_version",
            "embedding_model",
            name="uq_document_version_idem",
        ),
        Index("ix_document_version_document_id_state", "document_id", "state"),
        Index("ix_document_version_page_id_state", "page_id", "state"),
        # at most one active version per document
        Index(
            "ux_document_version_one_active",
            "document_id",
            unique=True,
            postgresql_where=text("state = 'active'"),
        ),
    )


class Chunk(Base):
    """Parent (section) and child chunks. Hot-path filter columns are denormalized here."""

    __tablename__ = "chunk"

    id: Mapped[int] = _pk()
    doc_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("document_version.id", ondelete="CASCADE"), nullable=False
    )
    page_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cf_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0 parent, 1 child

    # stable identity + diff keys
    stable_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    positional_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    parent_chunk_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("chunk.id", ondelete="CASCADE"), nullable=True
    )
    prev_chunk_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    next_chunk_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    space_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # provider tagging + the RLS isolation key (ADR-0004)
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'confluence'")
    )
    source_id: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=text("'confluence:default'")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    display_content: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMB_DIM), nullable=True)
    tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    # denormalized hot-path filters (kept in sync at activation)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    page_status: Mapped[PageStatus] = mapped_column(
        SAEnum(PageStatus, name="page_status", create_type=False), nullable=False
    )
    retrieval_schema_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    access_scope: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    created_at: Mapped[datetime] = _ts_created()

    __table_args__ = (
        UniqueConstraint("doc_version_id", "stable_key", name="uq_chunk_doc_version_stable"),
        Index("ix_chunk_doc_version_id", "doc_version_id"),
        Index("ix_chunk_parent_chunk_id", "parent_chunk_id"),
        Index("ix_chunk_page_id_stable_key", "page_id", "stable_key"),
        Index("ix_chunk_doc_version_id_seq", "doc_version_id", "seq"),
        # dense: partial HNSW over active children with an embedding (dimension-aware, see above)
        _embedding_hnsw_index(),
        # keyword: partial GIN over active children
        Index(
            "ix_chunk_tsv_gin",
            "tsv",
            postgresql_using="gin",
            postgresql_where=text("is_active AND kind = 1"),
        ),
        Index(
            "ix_chunk_active_space",
            "is_active",
            "space_id",
            postgresql_where=text("is_active"),
        ),
        # source-scoped hot path: lets the planner use the source key alongside the RLS predicate
        Index(
            "ix_chunk_active_source",
            "is_active",
            "source_id",
            postgresql_where=text("is_active"),
        ),
        CheckConstraint(_SOURCE_TYPE_CHECK, name=conv("ck_chunk_source_type")),
    )


class EventLedger(Base):
    """Raw webhook / reconciliation events. Dedup by payload_hash and delivery_id."""

    __tablename__ = "event_ledger"

    id: Mapped[int] = _pk()
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    page_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cf_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    space_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_status: Mapped[PageStatus | None] = mapped_column(
        SAEnum(PageStatus, name="page_status", create_type=False), nullable=True
    )
    payload_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    delivery_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    origin: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0 webhook 1 recon 2 manual
    proc_status: Mapped[EventProcStatus] = mapped_column(
        SAEnum(EventProcStatus, name="event_proc_status", create_type=False),
        nullable=False,
        server_default=text("'received'"),
    )
    self_generated: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    dead_letter_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    received_at: Mapped[datetime] = _ts_created()
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("payload_hash", name="uq_event_ledger_payload_hash"),
        Index(
            "ux_event_ledger_delivery_id",
            "delivery_id",
            unique=True,
            postgresql_where=text("delivery_id IS NOT NULL"),
        ),
        Index("ix_event_ledger_page_id_cf_version", "page_id", "cf_version"),
        Index(
            "ix_event_ledger_proc_status",
            "proc_status",
            postgresql_where=text("proc_status IN ('received','queued','dead_letter')"),
        ),
    )


class Job(Base):
    """Crash-safe, idempotent background job queue (claimed via FOR UPDATE SKIP LOCKED)."""

    __tablename__ = "job"

    id: Mapped[int] = _pk()
    job_type: Mapped[str] = mapped_column(String(48), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    page_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cf_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("100"))
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status", create_type=False),
        nullable=False,
        server_default=text("'pending'"),
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_event_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("event_ledger.id"), nullable=True
    )
    created_at: Mapped[datetime] = _ts_created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_job_idempotency_key"),
        Index(
            "ix_job_claim",
            "status",
            "available_at",
            "priority",
            postgresql_where=text("status IN ('pending','failed')"),
        ),
        Index(
            "ix_job_lease",
            "status",
            "lease_expires_at",
            postgresql_where=text("status IN ('leased','running')"),
        ),
        Index("ix_job_page_id", "page_id"),
    )


class ReconciliationRun(Base):
    """Report for one reconciliation sweep (lightweight or complete)."""

    __tablename__ = "reconciliation_run"

    id: Mapped[int] = _pk()
    scope: Mapped[str] = mapped_column(String(64), nullable=False)  # 'all' | 'space:KEY'
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # 'lightweight' | 'complete'
    status: Mapped[ReconStatus] = mapped_column(
        SAEnum(ReconStatus, name="recon_status", create_type=False),
        nullable=False,
        server_default=text("'running'"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pages_scanned: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    drift_detected: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    jobs_enqueued: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    orphans_deleted: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    errors: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (Index("ix_reconciliation_run_started_at", "started_at"),)


_ROOT_TYPE_CHECK = "root_type IN ('space', 'page')"


class SourceScope(Base):
    """A configured Confluence sync root: a whole space, or a page-subtree narrower than one.

    Replaces the old, never-consumed ``CONFLUENCE_SPACES`` env var (PLAN 3.5.6 / ADR-0004
    follow-on). ``space`` roots reproduce today's whole-space behavior unchanged; ``page`` roots
    narrow reconciliation to a root page + its live descendants (resolved by
    ``confluence_sync.domain.scope_resolver``). ``tags`` propagate to ``page_source``/``chunk``
    for bot scoping. One-off ownership: rows are inserted directly (script), no CRUD API yet.
    """

    __tablename__ = "source_scope"

    id: Mapped[int] = _pk()
    root_type: Mapped[str] = mapped_column(String(16), nullable=False)
    root_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'confluence'")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = _ts_created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("root_type", "root_id", name="uq_source_scope_root"),
        CheckConstraint(_ROOT_TYPE_CHECK, name=conv("ck_source_scope_root_type")),
        CheckConstraint(_SOURCE_TYPE_CHECK, name=conv("ck_source_scope_source_type")),
        Index("ix_source_scope_active", "is_active", postgresql_where=text("is_active")),
    )


class QueryTrace(Base):
    """One row per retrieval request: the tracing scoreboard (PLAN 3.5.4).

    Written via the WRITER engine so RLS never blocks the insert. Retrieval fills the retrieval
    columns at insert time, including retrieved_chunk_ids and rerank_scores (populated since
    Phase 4.2, once reranking runs inside the retrieval pipeline). The Phase-4 answer runtime
    UPDATEs the same row afterward with rewritten_query / answer / citations / feedback (all
    nullable here, since the original 3.5.4 migration predates all of Phase 4).
    """

    __tablename__ = "query_trace"

    id: Mapped[int] = _pk()
    raw_query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_page_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=False)
    allowed_sources: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    reranker_model: Mapped[str] = mapped_column(String(128), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    # populated at insert time by both retrieve() and retrieve_with_context() (retriever.py's
    # shared _trace helper); nullable only because the 3.5.4 migration predates reranking
    retrieved_chunk_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger), nullable=True)
    rerank_scores: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)
    # populated by the Phase-4 answer runtime's later UPDATE (answer_service.py + feedback PATCH)
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    feedback: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)  # +1 / -1

    created_at: Mapped[datetime] = _ts_created()

    __table_args__ = (Index("ix_query_trace_created_at", "created_at"),)


__all__ = [
    "PageSource",
    "Document",
    "DocumentVersion",
    "Chunk",
    "EventLedger",
    "Job",
    "ReconciliationRun",
    "SourceScope",
    "QueryTrace",
    "KIND_PARENT",
    "KIND_CHILD",
    "EMB_DIM",
]
