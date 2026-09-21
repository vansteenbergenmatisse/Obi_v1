"""customer-scope isolation backstop: RESTRICTIVE RLS on chunk + curated (Phase 11.1a / ADR-0014)

The mews/opera/toast/general boundary was enforced only by an app-layer ``tags && :scopes``
predicate gated behind a fail-OPEN feature flag (``enable_knowledge_scope_filtering``): flag off, or
one dropped predicate, returned every customer's rows to everyone. Source isolation already fails
*closed* via the ADR-0004 ``chunk_source_read`` policy; the customer axis did not.

This adds a second policy on the customer axis, keyed on a new per-transaction GUC
``app.allowed_knowledge_scopes`` that mirrors ``app.allowed_sources``:

* ``chunk_scope_read`` on ``chunk``
* ``curated_knowledge_entry_scope_read`` on ``curated_knowledge_entry``

Both are ``AS RESTRICTIVE`` so they **AND** with the existing permissive source/reader policies — a
second *permissive* policy would OR, weakening isolation. Semantics (see
``schema.apply_*_scope_rls``): unset GUC -> denies the *tagged* rows (fail closed); a scope list ->
``tags``-overlap; an untagged (``cardinality(tags)=0``) row is global; the explicit ``'*'`` sentinel
-> unrestricted opt-out (the internal/eval path; the public path always resolves a real scope list).
``chunk``'s stricter source-keyed policy and the 0009 reader policies are untouched.

Idempotent, and distinct from Phase 13.1 (0009, reader read-access) — this adds the tenant policy
0009 deliberately did not.

Revision ID: 0010_customer_scope_rls
Revises: 0009_reconcile_non_chunk_rls
Create Date: 2026-09-10
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from schema import schema

revision: str = "0010_customer_scope_rls"
down_revision: str | None = "0009_reconcile_non_chunk_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    schema.apply_chunk_scope_rls(bind)  # RESTRICTIVE customer-scope policy, ANDs with source policy
    schema.apply_curated_scope_rls(bind)  # same axis on the curated layer


def downgrade() -> None:
    bind = op.get_bind()
    schema.drop_chunk_scope_rls(bind)  # leaves chunk_source_read + RLS enable state intact
    schema.drop_curated_scope_rls(bind)
