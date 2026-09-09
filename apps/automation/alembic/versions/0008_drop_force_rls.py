"""drop FORCE on chunk RLS so the writer needs no SUPERUSER (ADR-0013)

``chunk`` was under ``FORCE ROW LEVEL SECURITY``, where even the table owner is subject to the
default-deny policy — so on the local cluster the writer only escaped it by being a SUPERUSER.
Managed Postgres (Supabase Cloud on AWS; RDS/Aurora as the reversible fallback) grants no true
superuser, so under ``FORCE`` the owner/writer would be filtered to zero rows and ingestion +
reconciliation reads would break on cutover (Phase 6).

Fix: keep RLS ``ENABLE``d, drop ``FORCE``. A non-superuser *owner* is then exempt by ownership
alone, while the non-owner ``rag_reader`` role stays fully policy-bound — read-path isolation
(ADR-0004) is unchanged, because it never depended on ``FORCE``, only on the reader being a
non-owner. See ADR-0013.

Idempotent: ``NO FORCE`` is a no-op when FORCE is already absent, and the 0001 baseline builds the
current ORM metadata via create_all + ``schema.apply_chunk_rls`` (which as of ADR-0013 no longer
FORCEs), so a fresh ``alembic upgrade head`` re-asserts the intended state either way.

Revision ID: 0008_drop_force_rls
Revises: 0007_knowledge_scope
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_drop_force_rls"
down_revision: str | None = "0007_knowledge_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ENABLE is left in place (default-deny still applies to the non-owner reader); only FORCE goes.
    op.execute("ALTER TABLE chunk NO FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Restore the pre-ADR-0013 state. Reversible, but re-forcing RLS requires the writer to be a
    # SUPERUSER again (i.e. the local cluster, not managed Postgres) or ingestion reads will break.
    op.execute("ALTER TABLE chunk FORCE ROW LEVEL SECURITY")
