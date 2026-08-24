"""knowledge_scope: curated_knowledge_entry table + tags GIN index + query_trace column (PLAN 10.3)

Adds the storage this phase's retrieval-time filtering (PLAN 10.4) and always-present curated
layer (PLAN 10.6) read from: ``curated_knowledge_entry`` (hand-authored knowledge, tagged like
``chunk``/``page_source`` and always eligible when its ``tags`` is empty), a partial GIN index on
``chunk.tags`` for the ``tags && ARRAY[...]`` membership predicate 10.4 adds, and
``query_trace.allowed_knowledge_scopes`` (audit trail, mirrors the existing ``allowed_sources``
column). Idempotent (``IF NOT EXISTS`` throughout) for the same reason as every migration in this
chain since 0003: the 0001 baseline builds current ORM metadata via ``create_all``, so a fresh
``upgrade head`` already has this shape by the time this migration runs.

Revision ID: 0007_knowledge_scope
Revises: 0006_dedupe_source_type_check
Create Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007_knowledge_scope"
down_revision: str | None = "0006_dedupe_source_type_check"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS curated_knowledge_entry (
            id          bigserial PRIMARY KEY,
            tags        text[]      NOT NULL DEFAULT '{}',
            title       text        NOT NULL,
            body        text        NOT NULL,
            is_active   boolean     NOT NULL DEFAULT true,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunk_tags_gin ON chunk USING gin (tags) WHERE is_active"
    )
    op.execute("ALTER TABLE query_trace ADD COLUMN IF NOT EXISTS allowed_knowledge_scopes text[]")


def downgrade() -> None:
    op.execute("ALTER TABLE query_trace DROP COLUMN IF EXISTS allowed_knowledge_scopes")
    op.execute("DROP INDEX IF EXISTS ix_chunk_tags_gin")
    op.execute("DROP TABLE IF EXISTS curated_knowledge_entry")
