"""panel mi-match · substep 8.2.3 — the stamped JSONB payload matches through the matcher.

Database level: a chunk row carrying the exact ``applies_to_payload`` shape 8.2.2 stamps
(validated record → JSON → the ``chunk.applicability`` JSONB column from migration 0015)
is read back through a real local Postgres and fed to ``match_applicability`` unchanged —
proving the stored shape and the matcher consume one vocabulary, with no re-parsing step
between the database and the decision. The engine bootstrap is the shared
``app.tests.db_harness`` (root conftest ``_shared_db_schema``); per-test truncation comes
from this directory's ``conftest.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.ingestion import applies_to_payload, validate_applies_to
from app.features.retrieval.domain.applicability_match import (
    CustomerContext,
    match_applicability,
)
from app.platform.config import get_settings
from app.platform.config.product_catalog import load_product_catalog
from schema.enums import DocState, PageStatus
from schema.models import KIND_CHILD, Chunk, Document, DocumentVersion, PageSource

pytestmark = pytest.mark.db

CATALOG = load_product_catalog()

_PAGE = 8230


def _seed_stamped_chunk(session: Session, payload: list[dict[str, object]]) -> None:
    """One page_source ⇄ document ⇄ document_version chain plus one active child chunk
    stamped with ``payload`` — the rows 8.2.2's sync path writes, minimally."""
    now = datetime.now(UTC)
    dim = get_settings().embedding_dim
    session.add(
        PageSource(
            page_id=_PAGE,
            space_id=_PAGE,
            source_id="confluence:default",
            current_cf_version=1,
            page_status=PageStatus.current,
            title=f"Page {_PAGE}",
            source_url=f"https://example.test/{_PAGE}",
            source_modified_at=now,
            content_hash=b"ch",
            structure_hash=b"sh",
            attachment_manifest_hash=b"none",
            access_scope_hash=b"none",
            labels_hash=b"none",
            parser_version=1,
            chunker_version=1,
            contextualization_version=1,
            embedding_model="fake",
            embedding_dim=dim,
            retrieval_schema_version=1,
            applicability=payload,
        )
    )
    session.add(Document(id=_PAGE, page_id=_PAGE))
    session.add(
        DocumentVersion(
            id=_PAGE,
            document_id=_PAGE,
            page_id=_PAGE,
            cf_version=1,
            state=DocState.active,
            content_hash=b"ch",
            structure_hash=b"sh",
            parser_version=1,
            chunker_version=1,
            contextualization_version=1,
            embedding_model="fake",
            embedding_dim=dim,
            retrieval_schema_version=1,
        )
    )
    session.flush()
    session.add(
        Chunk(
            doc_version_id=_PAGE,
            page_id=_PAGE,
            cf_version=1,
            kind=KIND_CHILD,
            stable_key=b"sk",
            positional_key=b"pk",
            content_key=b"ck",
            content_hash=b"ch",
            seq=0,
            heading_path=[],
            location={},
            display_content="x",
            retrieval_content="x",
            tokens=1,
            title=f"Page {_PAGE}",
            space_id=_PAGE,
            source_id="confluence:default",
            tags=["obi-mews-test"],
            source_url=f"https://example.test/{_PAGE}",
            is_active=True,
            page_status=PageStatus.current,
            retrieval_schema_version=1,
            embedding_model="fake",
            access_scope=b"",
            embedding=[1.0] + [0.0] * (dim - 1),
            applicability=payload,
        )
    )
    session.commit()


def test_rt2_match_stamped_jsonb_payload_round_trips_through_the_matcher(
    session: Session,
) -> None:
    """panel mi-match · substep 8.2.3
    The exact JSONB payload stamped on a chunk (validated record → applies_to_payload →
    chunk.applicability) matches the right customer context after a real Postgres
    round-trip, and never the Mews/Xero cross context."""
    record = validate_applies_to(
        [
            {
                "level": "connection",
                "connection": "pms-accounting",
                "pms": "mews",
                "accounting": "quickbooks-online",
                "directions": "pms_to_accounting",
            }
        ],
        CATALOG,
        frozenset({"datahub"}),
    )
    _seed_stamped_chunk(session, applies_to_payload(record))
    session.expire_all()

    stored = session.execute(select(Chunk.applicability).where(Chunk.page_id == _PAGE)).scalar_one()
    assert stored is not None

    right = CustomerContext(slot_pos=None, slot_pms="mews", slot_accounting="quickbooks-online")
    hit = match_applicability(right, stored, CATALOG)
    assert hit.matched is True
    assert hit.reason == "connection:pms-accounting"

    cross = CustomerContext(slot_pos=None, slot_pms="mews", slot_accounting="xero")
    assert match_applicability(cross, stored, CATALOG).matched is False
