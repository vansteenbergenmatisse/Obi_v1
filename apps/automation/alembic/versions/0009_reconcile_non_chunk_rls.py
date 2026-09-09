"""reader RLS on non-chunk tables: keep anon out, let rag_reader in (Phase 13.1)

The retrieval read path runs as the non-owner rag_reader role and reads page_source /
page_restriction (the page-principal ACL, ``fetch_page_scopes``) and curated_knowledge_entry (the
curated answer layer). On Supabase those tables had ROW LEVEL SECURITY enabled with no policy, so
rag_reader (non-BYPASSRLS) was default-denied and read zero rows — the page ACL silently failed open
and the curated layer went dark.

The naive fix — disabling RLS — is unsafe on Supabase: the PostgREST roles anon/authenticated hold
blanket GRANT SELECT on every public table, so RLS is the only thing keeping the corpus off the
public REST endpoint. Disabling it would expose every row to the unauthenticated anon role.

So this migration keeps RLS enabled on the non-chunk tables (anon/authenticated stay default-denied)
and adds a ``FOR SELECT TO rag_reader USING (true)`` policy to the reader's read set, so only
rag_reader is let back in. chunk keeps its stricter source-keyed policy. This is a different axis
from Phase 11.1a (customer-scope isolation): 0009 restores reader read-access, it does not add or
weaken any tenant policy.

The reader policy is skipped when the rag_reader role does not exist yet (a fresh ``alembic
upgrade`` runs before the role is provisioned); ``setup_supabase.py provision-reader`` re-runs
``apply_reader_rls`` once the role exists.

Revision ID: 0009_reconcile_non_chunk_rls
Revises: 0008_drop_force_rls
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.platform.db import schema

revision: str = "0009_reconcile_non_chunk_rls"
down_revision: str | None = "0008_drop_force_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    schema.enable_non_chunk_rls(bind)  # anon/authenticated default-denied (safe on a fresh deploy)
    schema.apply_reader_rls(bind)  # let rag_reader back into its read set (skipped if role absent)


def downgrade() -> None:
    bind = op.get_bind()
    schema.drop_reader_rls(bind)
    # WARNING: disabling RLS re-exposes the non-chunk tables to the public anon REST role on
    # Supabase. Only downgrade a store with no PostgREST/anon exposure (local docker, RDS fallback).
    schema.disable_non_chunk_rls(bind)
