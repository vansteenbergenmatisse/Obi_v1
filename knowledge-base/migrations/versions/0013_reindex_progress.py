"""add reindex progress columns to reconciliation_run (PLAN 2.0.3)

The full re-index job (substep 2.0.3) models a stamp-triggered rebuild of every tagged page as a
``reconciliation_run`` with ``kind='reindex'``. The proof requires a *visible, queryable* progress
counter that survives a restart, so progress lives in explicit columns, not in the ``report`` JSONB:

* ``total_pages`` — tagged pages the run must rebuild.
* ``pages_done``  — how many it has enqueued so far (the counter "the job row shows progress").
* ``cursor``      — the last tagged ``page_id`` enqueued; a crashed reindex resumes from the next
  page instead of from zero.

Reversible: ``downgrade`` drops the three columns. Idempotent (``ADD COLUMN IF NOT EXISTS`` /
``DROP COLUMN IF EXISTS``) for the same reason as the rest of this chain — a fresh database already
carries the columns via ``schema.create_all`` on the 0001 baseline; 0013 is the explicit record for
a mid-chain deploy.

Revision ID: 0013_reindex_progress
Revises: 0012_widen_document_version_idem
Create Date: 2026-09-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_reindex_progress"
down_revision: str | None = "0012_widen_document_version_idem"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "reconciliation_run"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS total_pages integer NOT NULL DEFAULT 0"
    )
    op.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS pages_done integer NOT NULL DEFAULT 0"
    )
    op.execute(f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS cursor bigint")


def downgrade() -> None:
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS cursor")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS pages_done")
    op.execute(f"ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS total_pages")
