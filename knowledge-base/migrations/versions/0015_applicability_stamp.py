"""applicability lands on the chunks (panel mi-applies, substep 8.2.2 / plan.md §D.3)

Adds a nullable JSONB ``applicability`` column to ``chunk`` and ``page_source``: the
validated "Applies to" record sync stamps during a build or over the §D.0 metadata-only
restamp route (a JSON list of rules, OR between them). NULL means the page authored no
record and keeps the documented label-only behavior (§D.11) — never a wildcard.

Applicability never grants access: it only narrows relevance on top of labels, RLS and
page permissions, so NO policy changes ride this migration — the scope/source RLS
policies on both tables are untouched in both directions, and the downgrade simply
drops the two columns (clean, data-lossy for the stamp only; a later re-upgrade is
restamped by the next sync of each page).

Revision ID: 0015_applicability_stamp
Revises: 0014_chunk_scope_fail_closed
Create Date: 2026-10-05
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015_applicability_stamp"
down_revision: str | None = "0014_chunk_scope_fail_closed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("page_source", "chunk")


def upgrade() -> None:
    # Idempotent (IF NOT EXISTS) for the same reason as every migration in this chain:
    # the 0001 baseline builds the *current* ORM metadata via schema.create_all, so a
    # fresh upgrade already has these columns — 0015 is the explicit-DDL record of the
    # change for a mid-chain deploy.
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS applicability jsonb")


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS applicability")
