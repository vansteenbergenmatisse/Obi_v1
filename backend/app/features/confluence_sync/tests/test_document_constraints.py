"""Table-shape tests for document — panel d-document, substep 0.5.4.

`test_versioning_document.py` already proves the *behavior* end-to-end through the real sync path
(one row per page, a stable id across rebuilds). These tests prove the table's own shape at the
Postgres level instead: `document.page_id` is UNIQUE (fires independent of any business-logic
dedup), and its FK to `page_source.page_id` is DEFERRABLE INITIALLY DEFERRED — checked at commit,
not at flush (the "insert-order cycle on first index" the column's own comment names,
models.py:186-190).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from schema.enums import PageStatus
from schema.models import Document, PageSource

pytestmark = (
    pytest.mark.db
)  # substep 0.5.4: real local Postgres via this dir's session-scoped conftest


def _page_source(page_id: int) -> PageSource:
    return PageSource(
        page_id=page_id,
        space_id=1,
        current_cf_version=1,
        page_status=PageStatus.current,
        title="t",
        source_url="https://example.test/x",
        source_modified_at=datetime(2026, 6, 1, tzinfo=UTC),
        content_hash=b"\x00" * 32,
        structure_hash=b"\x00" * 32,
        attachment_manifest_hash=b"\x00" * 32,
        access_scope_hash=b"\x00" * 32,
        labels_hash=b"\x00" * 32,
        parser_version=1,
        chunker_version=1,
        contextualization_version=1,
        embedding_model="test-model",
        embedding_dim=8,
        retrieval_schema_version=1,
    )


def test_d_document_page_id_unique_constraint(session):
    """panel d-document · substep 0.5.4
    document.page_id is UNIQUE: two Document rows sharing the same page_id cannot both flush —
    the second raises IntegrityError, independent of the (separately deferred) FK check."""
    session.add(_page_source(7001))
    session.flush()

    session.add(Document(page_id=7001))
    session.flush()

    session.add(Document(page_id=7001))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_d_document_page_id_fk_deferred_to_commit(session):
    """panel d-document · substep 0.5.4
    document.page_id's FK to page_source.page_id is DEFERRABLE INITIALLY DEFERRED: inserting a
    Document row before any matching page_source row exists flushes without error — not checked
    immediately. The constraint only fires at commit, and only because the referenced row is
    still missing by then."""
    session.add(Document(page_id=7002))
    session.flush()  # must not raise: the FK check is deferred, not immediate

    with pytest.raises(IntegrityError):
        session.commit()  # page_source row for 7002 was never created
    session.rollback()


def test_d_document_page_id_fk_satisfied_before_commit(session):
    """panel d-document · substep 0.5.4
    Adding the missing page_source row later in the same transaction — after the Document row,
    before commit — satisfies the deferred check: commit succeeds. This is the insert-order cycle
    the deferral exists for (models.py:186-190)."""
    session.add(Document(page_id=7003))
    session.flush()

    session.add(_page_source(7003))
    session.flush()

    session.commit()  # must not raise: the page_source row exists by commit time
