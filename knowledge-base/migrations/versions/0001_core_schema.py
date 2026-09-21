"""core schema: versioned Confluence knowledge store

Baseline snapshot built from the ORM metadata via the shared schema helper so the migrated
database and the create_all test database are identical. Subsequent migrations use normal
Alembic autogenerate diffs from this baseline.

Revision ID: 0001_core_schema
Revises:
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from schema import schema

revision: str = "0001_core_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    schema.create_all(op.get_bind())


def downgrade() -> None:
    schema.drop_all(op.get_bind())
