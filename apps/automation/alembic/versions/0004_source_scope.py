"""source_scope: configurable Confluence sync roots (PLAN 3.5.6)

Adds the ``source_scope`` table — the DB-backed replacement for the never-consumed
``CONFLUENCE_SPACES`` env var. A ``space``-type row reproduces today's whole-space sync
unchanged; a ``page``-type row narrows reconciliation to a root page + its live descendants.

Deliberately schema-only (no data seed): unlike the design note's original "one-time migration
seed" idea, this migration does not read ``CONFLUENCE_SPACES``/``Settings`` at migration time —
migrations 0001-0003 never couple DDL to mutable env state, and doing so here would make the
upgrade non-deterministic across environments (including the hermetic test DB) and break the
plain `alembic upgrade head` reproducibility every other migration in this repo relies on. Rows
are seeded instead via the one-off `scripts/seed_source_scope.py` (documented deviation from the
approved spec; ownership was already "one-off, no CRUD" either way).

Revision ID: 0004_source_scope
Revises: 0003_query_trace
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_source_scope"
down_revision: str | None = "0003_query_trace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_TYPE_CHECK = "source_type IN ('confluence', 'zendesk', 'notion', 'upload')"
_ROOT_TYPE_CHECK = "root_type IN ('space', 'page')"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS source_scope (
            id BIGSERIAL PRIMARY KEY,
            root_type varchar(16) NOT NULL,
            root_id varchar(128) NOT NULL,
            source_type varchar(32) NOT NULL DEFAULT 'confluence',
            tags text[] NOT NULL DEFAULT '{}',
            label varchar(256),
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_source_scope_root UNIQUE (root_type, root_id),
            CONSTRAINT ck_source_scope_root_type CHECK ("""
        + _ROOT_TYPE_CHECK
        + """),
            CONSTRAINT ck_source_scope_source_type CHECK ("""
        + _SOURCE_TYPE_CHECK
        + """)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_source_scope_active "
        "ON source_scope (is_active) WHERE is_active"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS source_scope")
