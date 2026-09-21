"""provider tagging + row-level security (ADR-0004)

Adds the source_type / source_id / tags columns to page_source and chunk, the source index and
CHECK constraint, and enables default-deny RLS on chunk keyed by source_id.

Idempotent by design: the 0001 baseline builds the *current* ORM metadata via create_all, so on a
fresh ``alembic upgrade head`` the columns/indexes already exist and the IF-NOT-EXISTS guards make
this a near-no-op that still (re)asserts the CHECK + RLS. On a database created before these
columns existed, it adds and backfills them.

The server defaults are intentionally KEPT (a documented deviation from the plan's "drop default"):
the ORM models carry the same server_default, so keeping them here holds the migration-built and
create_all-built databases to the same shape (schema.py's contract). Ingestion still stamps
source_id explicitly at its single activation seam, so a second source is a code change, not a
silent default.

Reader/writer *roles* are cluster-global infrastructure (docker init SQL / ops), not created here.

Revision ID: 0002_provider_tags_and_rls
Revises: 0001_core_schema
Create Date: 2026-08-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from schema import schema

revision: str = "0002_provider_tags_and_rls"
down_revision: str | None = "0001_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_TYPE_CHECK = "source_type IN ('confluence', 'zendesk', 'notion', 'upload')"


def upgrade() -> None:
    for tbl in ("page_source", "chunk"):
        op.execute(
            f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS "
            "source_type varchar(32) NOT NULL DEFAULT 'confluence'"
        )
        op.execute(
            f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS "
            "source_id varchar(128) NOT NULL DEFAULT 'confluence:default'"
        )
        op.execute(
            f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS tags text[] NOT NULL DEFAULT '{{}}'"
        )
        op.execute(f"ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS ck_{tbl}_source_type")
        op.execute(
            f"ALTER TABLE {tbl} ADD CONSTRAINT ck_{tbl}_source_type CHECK ({_SOURCE_TYPE_CHECK})"
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunk_active_source "
        "ON chunk (is_active, source_id) WHERE is_active"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_page_source_source_id ON page_source (source_id)")

    schema.apply_chunk_rls(op.get_bind())


def downgrade() -> None:
    schema.drop_chunk_rls(op.get_bind())
    op.execute("DROP INDEX IF EXISTS ix_chunk_active_source")
    op.execute("DROP INDEX IF EXISTS ix_page_source_source_id")
    for tbl in ("page_source", "chunk"):
        op.execute(f"ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS ck_{tbl}_source_type")
        for col in ("tags", "source_id", "source_type"):
            op.execute(f"ALTER TABLE {tbl} DROP COLUMN IF EXISTS {col}")
