"""retire the knowledge-scope RLS axis (ADR-routing-labels-sole-content-axis, superseding ADR-knowledge-scope-tagging-and-filtering/ADR-db-level-customer-scope-isolation-backstop's scope policies)

ADR-routing-labels-sole-content-axis retires the knowledge-scope ``-test`` tag axis entirely: index membership and content
routing now ride the ADR-directed-source-target-routing-labels routing-label axis alone (the ``chunk.labels`` column, the
``app.allowed_labels`` GUC and the ``chunk_labels_read`` RESTRICTIVE policy). This migration drops
the two RESTRICTIVE knowledge-scope policies that implemented the retired axis:

* ``chunk_scope_read`` on ``chunk`` (``schema.drop_chunk_scope_rls``)
* ``curated_knowledge_entry_scope_read`` on ``curated_knowledge_entry`` (``schema.drop_curated_scope_rls``)

After this, the ``app.allowed_knowledge_scopes`` GUC is read by no policy. The retrieval path opts
that GUC out (wildcard) regardless, and the app-layer ``tags && :knowledge_scopes`` predicate is off
by default — so the scope axis no longer restricts anything.

ISOLATION IS PRESERVED. This does **not** disable RLS and does **not** touch the
source/company-isolation axis:

* ``chunk`` keeps RLS ENABLEd with ``chunk_source_read`` (PERMISSIVE, ``app.allowed_sources`` —
  lock 1, source/company isolation) and ``chunk_labels_read`` (RESTRICTIVE, routing). After this
  migration a ``chunk`` row's visibility is ``chunk_source_read AND chunk_labels_read``.
* ``curated_knowledge_entry`` keeps its PERMISSIVE ``curated_knowledge_entry_reader_read`` policy
  (``TO rag_reader``) and the non-chunk anon fences are untouched — so dropping the restrictive
  scope policy re-exposes nothing to anon (unlike the 0009 downgrade; never-bend rule 1 holds).

Unlike 0010/0014 — whose *downgrades* DROP these policies and are therefore blocked on Supabase —
this migration's *upgrade* is the sanctioned, deliberate drop (fix-forward, ADR-routing-labels-sole-content-axis), and its
*downgrade* RE-APPLIES both policies (tightening, never loosening), so the downgrade is safe on any
host and needs no Supabase guard. Idempotent via the schema helpers' ``DROP ... IF EXISTS`` /
``DROP`` + ``CREATE``. Reversible (never-bend rule 11).

Revision ID: 0018_retire_knowledge_scope_rls
Revises: 0017_chat_session
Create Date: 2026-10-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from schema import schema

revision: str = "0018_retire_knowledge_scope_rls"
down_revision: str | None = "0017_chat_session"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # ADR-routing-labels-sole-content-axis: retire the knowledge-scope axis. Drops the two RESTRICTIVE scope policies; leaves
    # chunk RLS ENABLEd with the source (lock 1) + labels (routing) policies, and leaves every
    # non-chunk fence untouched — source/company isolation is unchanged.
    schema.drop_chunk_scope_rls(bind)
    schema.drop_curated_scope_rls(bind)


def downgrade() -> None:
    bind = op.get_bind()
    # Reverse: re-apply both RESTRICTIVE scope policies (tightening — safe on any host).
    schema.apply_chunk_scope_rls(bind)
    schema.apply_curated_scope_rls(bind)
