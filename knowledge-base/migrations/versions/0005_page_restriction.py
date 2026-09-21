"""page_restriction: persisted per-page principal ACL (PLAN 4.3)

Replaces the fixture-fed ``PrincipalPermissionPolicy``'s in-memory restriction dict with a real,
queryable per-page ACL table. Presence of any row for a page means it is restricted to the listed
principals; absence means unrestricted — the same contract the pure policy already implements.
Written by ``confluence_sync``'s ``handle_sync_page`` whenever a page's restriction list changes
(the existing ``classify()`` ``permissions_changed`` class already detects this); read by
``retrieval``'s ``HybridRetriever._search`` alongside RLS as the second, page-level security layer
(ADR-0004 §page-level ACL / ADR-0005 §9). ``rag_reader``'s ``GRANT SELECT ON ALL TABLES`` +
``ALTER DEFAULT PRIVILEGES`` (01-roles.sql) already cover this new table — no separate grant
needed.

Revision ID: 0005_page_restriction
Revises: 0004_source_scope
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_page_restriction"
down_revision: str | None = "0004_source_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS page_restriction (
            page_id bigint NOT NULL REFERENCES page_source(page_id) ON DELETE CASCADE,
            principal varchar(128) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_page_restriction PRIMARY KEY (page_id, principal)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS page_restriction")
