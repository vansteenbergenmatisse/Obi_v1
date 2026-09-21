"""query_trace: per-retrieval tracing scoreboard (PLAN 3.5.4)

Adds the query_trace table. Retrieval fills the retrieval columns via the writer engine (RLS
never blocks it); the Phase-4 answer runtime UPDATEs the same row with rewritten_query / answer /
citations / feedback (all nullable). Idempotent (CREATE TABLE IF NOT EXISTS) because the 0001
baseline builds current ORM metadata via create_all, so on a fresh upgrade the table already exists.

Revision ID: 0003_query_trace
Revises: 0002_provider_tags_and_rls
Create Date: 2026-08-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_query_trace"
down_revision: str | None = "0002_provider_tags_and_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS query_trace (
            id                  bigserial PRIMARY KEY,
            raw_query           text        NOT NULL,
            retrieved_page_ids  bigint[]    NOT NULL,
            allowed_sources     text[]      NOT NULL,
            embedding_model     varchar(128) NOT NULL,
            reranker_model      varchar(128) NOT NULL,
            latency_ms          integer     NOT NULL,
            retrieved_chunk_ids bigint[],
            rerank_scores       double precision[],
            rewritten_query     text,
            answer              text,
            citations           jsonb,
            feedback            smallint,
            created_at          timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_query_trace_created_at ON query_trace (created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS query_trace")
