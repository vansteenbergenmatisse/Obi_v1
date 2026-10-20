"""chat_session table for directed-connection chat-start (panel mi-session, substep 9.2.1 / Option A
Stage 4, ADR-directed-source-target-routing-labels)

Adds ``chat_session``: one row per directed-connection chat, keyed on the VERIFIED edge identity
(``subject_hash`` — the sha256 of the issuer-namespaced token subject, mirroring
``query_trace.subject_hash`` / ``router._idempotency_cache_key`` — plus ``company_id``), never the
caller-supplied conversation id. Chat-start resolves the connection once and stores ``business_id``,
``source_slug``, ``target_slug``, ``labels`` and ``connection_block``; every later question reuses
the row instead of re-resolving (never-bend rule 8). A partner switch refires chat-start and
replaces the labels + block in place (D7). ``source_slug``/``target_slug`` are nullable: an
unrecognized system leaves ``labels = {obi-general}`` and an "unknown" connection block (step 5).

The table is written + read via the writer (owner) engine, which bypasses RLS
(ADR-supabase-postgres-store-without-force-rls NO FORCE),
so the chat path is unaffected. RLS is still ENABLEd with NO policy so the Supabase public REST
roles (anon/authenticated, which hold a blanket GRANT SELECT) are default-denied — the same Phase
13.1 rationale that keeps every non-chunk table fenced (never-bend rule 1). No GUC, no policy: the
binding to a subject is the composite primary key at the application layer, not an RLS predicate.

Idempotent (``IF NOT EXISTS`` / ``DROP ... IF EXISTS``): the 0001 baseline builds current ORM
metadata via ``create_all`` (now including this table), so a fresh ``upgrade head`` already has the
table when 0017 runs; RLS is the one thing ``create_all`` does not express, so it is set here.

The downgrade drops the table cleanly (reversible — never-bend rule 11); it is safe on any host
(dropping a default-denied, writer-only table loosens no isolation).

Revision ID: 0017_chat_session
Revises: 0016_chunk_labels
Create Date: 2026-10-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0017_chat_session"
down_revision: str | None = "0016_chunk_labels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "chat_session"


def upgrade() -> None:
    op.execute(
        f"CREATE TABLE IF NOT EXISTS {_TABLE} ("
        "subject_hash text NOT NULL, "
        "company_id text NOT NULL, "
        "business_id text NOT NULL, "
        "source_slug text, "
        "target_slug text, "
        "labels text[] NOT NULL DEFAULT '{}', "
        "connection_block text NOT NULL, "
        "created_at timestamptz NOT NULL DEFAULT now(), "
        "updated_at timestamptz NOT NULL DEFAULT now(), "
        f"CONSTRAINT {_TABLE}_pkey PRIMARY KEY (subject_hash, company_id)"
        ")"
    )
    # Fence the Supabase public REST roles out (Phase 13.1 / rule 1): RLS ENABLEd with no policy
    # default-denies every non-owner role; the writer (owner) bypasses it
    # (ADR-supabase-postgres-store-without-force-rls NO FORCE).
    bind = op.get_bind()
    bind.execute(text(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {_TABLE}")
