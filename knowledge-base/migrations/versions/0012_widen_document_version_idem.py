"""widen uq_document_version_idem to the full pipeline identity (PLAN 3b/3c)

The idempotency constraint on ``document_version`` was
``(document_id, cf_version, retrieval_schema_version, embedding_model)`` — but
``change_detection.index_config_changed`` also treats ``parser_version``, ``chunker_version`` and
``contextualization_version`` as rebuild triggers. A config-only bump (e.g. bumping
``contextualization_version`` to force a clean re-embed at the *same* Confluence revision) therefore
tried to insert a second ``document_version`` row at the same key and raised a ``UniqueViolation``,
so the re-embed silently failed and the corpus stayed pinned to the old build. Observed live on the
obi-*-test pages (Toast/Mews stuck on ``contextualization_version=1`` after a bump).

Fix: recreate the constraint including the three pipeline-version columns, so a config bump gets a
distinct key (a new version) while a true idempotent replay — identical everything — still collides.

Reversible: ``downgrade`` restores the original four-column constraint. Idempotent (drop IF EXISTS
then create) for the same reason as the rest of this chain: a fresh DB already carries the widened
constraint via ``schema.create_all`` on the 0001 baseline; 0012 is the explicit record for a
mid-chain deploy.

Revision ID: 0012_widen_document_version_idem
Revises: 0011_query_trace_subject_hash
Create Date: 2026-09-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012_widen_document_version_idem"
down_revision: str | None = "0011_query_trace_subject_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAME = "uq_document_version_idem"
_WIDE = (
    "document_id, cf_version, parser_version, chunker_version, "
    "contextualization_version, retrieval_schema_version, embedding_model"
)
_NARROW = "document_id, cf_version, retrieval_schema_version, embedding_model"


def upgrade() -> None:
    op.execute(f"ALTER TABLE document_version DROP CONSTRAINT IF EXISTS {_NAME}")
    op.execute(f"ALTER TABLE document_version ADD CONSTRAINT {_NAME} UNIQUE ({_WIDE})")


def downgrade() -> None:
    op.execute(f"ALTER TABLE document_version DROP CONSTRAINT IF EXISTS {_NAME}")
    op.execute(f"ALTER TABLE document_version ADD CONSTRAINT {_NAME} UNIQUE ({_NARROW})")
