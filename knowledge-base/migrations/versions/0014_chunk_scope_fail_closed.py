"""chunk scope RLS: fail-closed floor removal (sync-rules step 4 / D3)

The ``chunk_scope_read`` RESTRICTIVE policy added in 0010 carried an ``OR cardinality(tags) = 0``
floor: an empty-tags chunk was global (visible under any scope). That floor is an active cross-scope
leak — dropping a page's last knowledge-scope tag left its active chunks with ``tags = []`` and thus
readable by *every* scope (mews, toast, operacloud, general).

Decision D3: drop the floor. The policy becomes pure ``tags``-overlap. An empty-tags chunk overlaps
nothing and is visible to **no** scope; "public" is the explicit ``general`` tag, never empty tags.
Rules 1/2/5/7 (sync-rules steps 1-3) already guarantee every active chunk carries >=1 recognised
tag, so this is defence-in-depth: fail-closed if that invariant ever regresses.

The ``'*'`` sentinel opt-out (internal/eval + already-authorized parent expansion) is kept, and an
unset GUC still fails closed (``string_to_array(NULL, ',')`` -> NULL -> overlap denies). Only
``chunk`` changes; ``curated_knowledge_entry_scope_read`` (operator-authored, intentionally global)
keeps its floor and is untouched.

DDL is inline (not via ``schema.apply_chunk_scope_rls``) so this migration is a self-contained,
reversible snapshot: ``downgrade`` restores the exact pre-0014 with-floor policy even though the
schema helper now emits the floor-less form.

Revision ID: 0014_chunk_scope_fail_closed
Revises: 0013_reindex_progress
Create Date: 2026-09-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

revision: str = "0014_chunk_scope_fail_closed"
down_revision: str | None = "0013_reindex_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCOPE_GUC = "app.allowed_knowledge_scopes"
_CHUNK_SCOPE_POLICY = "chunk_scope_read"

# fail-closed: pure tags-overlap, no cardinality(tags)=0 floor
_POLICY_FAIL_CLOSED = (
    f"CREATE POLICY {_CHUNK_SCOPE_POLICY} ON chunk AS RESTRICTIVE FOR SELECT "
    f"USING (current_setting('{_SCOPE_GUC}', true) = '*' "
    f"OR tags && string_to_array(current_setting('{_SCOPE_GUC}', true), ','))"
)

# pre-0014: the with-floor policy (empty tags = global) — restored on downgrade
_POLICY_WITH_FLOOR = (
    f"CREATE POLICY {_CHUNK_SCOPE_POLICY} ON chunk AS RESTRICTIVE FOR SELECT "
    f"USING (current_setting('{_SCOPE_GUC}', true) = '*' "
    f"OR cardinality(tags) = 0 "
    f"OR tags && string_to_array(current_setting('{_SCOPE_GUC}', true), ','))"
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("ALTER TABLE chunk ENABLE ROW LEVEL SECURITY"))
    bind.execute(text(f"DROP POLICY IF EXISTS {_CHUNK_SCOPE_POLICY} ON chunk"))
    bind.execute(text(_POLICY_FAIL_CLOSED))


_DOWNGRADE_ON_SUPABASE_BLOCKED = (
    "Blocked: never downgrade 0014 on Supabase. It restores the empty-tags-means-public floor, "
    "reopening the cross-scope leak the fail-closed policy exists to prevent. Fix forward instead."
)


def _refuse_supabase_downgrade(bind: Connection) -> None:
    """Hard stop: refuse to downgrade 0014 against a Supabase host (root CLAUDE.md rule #1).

    0014's downgrade re-creates the pre-0014 policy with ``OR cardinality(tags) = 0`` — the
    empty-tags-means-public floor — so any active chunk that regresses to empty tags becomes
    readable by every scope. Mirrors 0009's tested guard (open decision X1 from the 4.2 coverage
    audit, accepted 2026-10-05): it reads the host off the live bind, so it protects any caller
    pointed at Supabase. Local downgrades (localhost/docker/RDS) still work.
    """
    host = (bind.engine.url.host or "").lower()
    if "supabase" in host:
        raise RuntimeError(_DOWNGRADE_ON_SUPABASE_BLOCKED)


def downgrade() -> None:
    bind = op.get_bind()
    _refuse_supabase_downgrade(bind)  # never loosen RLS on Supabase (root CLAUDE.md rule #1)
    bind.execute(text("ALTER TABLE chunk ENABLE ROW LEVEL SECURITY"))
    bind.execute(text(f"DROP POLICY IF EXISTS {_CHUNK_SCOPE_POLICY} ON chunk"))
    bind.execute(text(_POLICY_WITH_FLOOR))
