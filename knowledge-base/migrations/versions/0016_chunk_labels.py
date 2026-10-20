"""raw routing labels land on chunks (panel mi-labels, substep 9.1.2 / Option A Stage 3,
ADR-directed-source-target-routing-labels)

Adds the directed-connection routing axis (ADR-directed-source-target-routing-labels D1): a ``labels
text[] NOT NULL DEFAULT '{}'``
column on ``chunk`` and ``page_source`` holding the *raw* Confluence labels a page was published
with (the unresolved ``get_labels`` output), kept strictly distinct from the resolved
knowledge-scope ``tags``. A partial GIN ``ix_chunk_labels_gin ... WHERE is_active`` backs the
``labels && ARRAY[...]`` overlap the 9.4.1 hard filter will run, mirroring 0007's tags GIN.

Also adds (D1) the RESTRICTIVE ``chunk_labels_read`` RLS policy keyed on a new
``app.allowed_labels`` GUC, mirroring ``chunk_scope_read`` in shape. It is a deliberate **no-op
until the GUC is set** (the
retrieval code that sets it is substep 9.4.1 / Stage 6): unset/empty GUC and the ``'*'`` sentinel
opt out, a real list overlaps. This is sound because labels are the routing/relevance axis, not the
access boundary — source isolation (lock 1) and customer-scope isolation (lock 2) remain the
fail-closed fence and are untouched. So the policy only ever *subtracts* visibility once 9.4.1 sets
the GUC; today it changes nothing.

Idempotent (``IF NOT EXISTS`` / ``DROP ... IF EXISTS``) for the same reason as every migration in
this chain: the 0001 baseline builds the current ORM metadata via ``create_all`` (now including the
column + GIN index), so a fresh ``upgrade head`` already has this shape when 0016 runs; the RLS
policy is the one thing ``create_all`` does not express, so it is created here and in the test
harness (``schema.apply_chunk_labels_rls``).

The downgrade drops the policy, the GIN index and BOTH columns cleanly (reversible — never-bend
rule 11). It is safe on any host, including Supabase: the policy is a no-op (an unset GUC opts out),
so removing it loosens no isolation — source + scope RLS (locks 1-2) are never touched here.

Revision ID: 0016_chunk_labels
Revises: 0015_applicability_stamp
Create Date: 2026-10-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0016_chunk_labels"
down_revision: str | None = "0015_applicability_stamp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("page_source", "chunk")
_LABELS_GUC = "app.allowed_labels"
_CHUNK_LABELS_POLICY = "chunk_labels_read"
_LABELS_INDEX = "ix_chunk_labels_gin"

# RESTRICTIVE routing-label policy; a no-op until app.allowed_labels is set (9.4.1). Inline (not via
# schema.apply_chunk_labels_rls) so this migration is a self-contained, reversible snapshot.
_POLICY_LABELS = (
    f"CREATE POLICY {_CHUNK_LABELS_POLICY} ON chunk AS RESTRICTIVE FOR SELECT "
    f"USING (coalesce(current_setting('{_LABELS_GUC}', true), '') = '' "
    f"OR current_setting('{_LABELS_GUC}', true) = '*' "
    f"OR labels && string_to_array(current_setting('{_LABELS_GUC}', true), ','))"
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS labels text[] NOT NULL DEFAULT '{{}}'"
        )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {_LABELS_INDEX} ON chunk USING gin (labels) WHERE is_active"
    )
    bind = op.get_bind()
    bind.execute(text("ALTER TABLE chunk ENABLE ROW LEVEL SECURITY"))
    bind.execute(text(f"DROP POLICY IF EXISTS {_CHUNK_LABELS_POLICY} ON chunk"))
    bind.execute(text(_POLICY_LABELS))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(text(f"DROP POLICY IF EXISTS {_CHUNK_LABELS_POLICY} ON chunk"))
    op.execute(f"DROP INDEX IF EXISTS {_LABELS_INDEX}")
    for table in reversed(_TABLES):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS labels")
