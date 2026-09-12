"""query_trace.subject_hash — hashed edge-token subject for audit (Phase 11.1c / ADR-0014)

The Obi embed binds each request to a verified platform JWT (``X-Obi-Token``). For audit we record
*who* asked as ``sha256(sub)`` — never the raw subject and never the token itself. Nullable: the
tokenless internal/eval path and every pre-11.1c row carry no subject.

Revision ID: 0011_query_trace_subject_hash
Revises: 0010_customer_scope_rls
Create Date: 2026-09-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011_query_trace_subject_hash"
down_revision: str | None = "0010_customer_scope_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent (IF NOT EXISTS) for the same reason as every migration in this chain: the 0001
    # baseline builds the *current* ORM metadata via schema.create_all, so a fresh upgrade already
    # has this column — 0011 is the explicit-DDL record of the change for a mid-chain deploy.
    op.execute("ALTER TABLE query_trace ADD COLUMN IF NOT EXISTS subject_hash text")


def downgrade() -> None:
    op.execute("ALTER TABLE query_trace DROP COLUMN IF EXISTS subject_hash")
