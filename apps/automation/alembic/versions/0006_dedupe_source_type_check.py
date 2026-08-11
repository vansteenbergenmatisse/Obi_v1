"""dedupe the source_type/root_type CHECK constraints (PLAN 4.6.8)

0001's baseline built `chunk`/`page_source` via `schema.create_all()` against the ORM metadata,
which at the time passed an explicit `name="ck_{tbl}_source_type"` to `CheckConstraint` — but
`Base.metadata`'s naming convention (`ck_%(table_name)s_%(constraint_name)s`) re-interpolates any
name it's given, producing the double-prefixed `ck_chunk_ck_chunk_source_type` /
`ck_page_source_ck_page_source_source_type` on a fresh `create_all()` run, not the canonical name.
0002 then ran `DROP CONSTRAINT IF EXISTS ck_{tbl}_source_type` (the canonical name) before adding
one back — which silently matched nothing on a 0001-built database, so it added a *second*,
correctly-named constraint instead of replacing the first. Both constraints have carried the
identical predicate ever since, on every database that ran the full 0001->0002 migration path —
harmless today, but risky the day `source_type`'s allowed values are ever extended (only one of
the two constraints would get updated).

`models.py` is fixed alongside this migration (`sqlalchemy.schema.conv(...)` around each explicit
CHECK-constraint name, so a fresh `create_all()` now produces the canonical name directly — a new
`0001->head` run no longer creates the duplicate at all). This migration cleans up the duplicate
that already exists on any database that ran the old, buggy path. `source_scope` (added by 0004
via raw DDL, not `create_all()`) never had a live duplicate, but its ORM declaration carried the
same bug for any future all-`create_all()` build, so its two constraints are defensively dropped
and recreated here too, for symmetry and to guard a `create_all()`-only rebuild.

Revision ID: 0006_dedupe_source_type_check
Revises: 0005_page_restriction
Create Date: 2026-08-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_dedupe_source_type_check"
down_revision: str | None = "0005_page_restriction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_TYPE_CHECK = "source_type IN ('confluence', 'zendesk', 'notion', 'upload')"
_ROOT_TYPE_CHECK = "root_type IN ('space', 'page')"

# (table, buggy double-prefixed name a create_all() run produced pre-fix)
_DUPES = [
    ("chunk", "ck_chunk_ck_chunk_source_type", _SOURCE_TYPE_CHECK),
    ("page_source", "ck_page_source_ck_page_source_source_type", _SOURCE_TYPE_CHECK),
    ("source_scope", "ck_source_scope_ck_source_scope_root_type", _ROOT_TYPE_CHECK),
    ("source_scope", "ck_source_scope_ck_source_scope_source_type", _SOURCE_TYPE_CHECK),
]


def upgrade() -> None:
    # Idempotent: IF EXISTS means this is a no-op on a database that never had the bug (e.g. one
    # built fresh from the now-fixed models.py, or `source_scope`, which was never duplicated on
    # a real migrated database in the first place).
    for tbl, bad_name, _check in _DUPES:
        op.execute(f"ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS {bad_name}")


def downgrade() -> None:
    # Restores the exact pre-migration shape: the buggy duplicate re-added alongside the
    # canonical constraint (which this migration never touches).
    for tbl, bad_name, check in _DUPES:
        op.execute(f"ALTER TABLE {tbl} ADD CONSTRAINT {bad_name} CHECK ({check})")
