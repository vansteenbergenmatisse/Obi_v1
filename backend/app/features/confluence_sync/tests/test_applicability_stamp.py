"""panel mi-applies · substep 8.2.2 — applicability lands on the chunks.

Database tests through the real sync path (fixture gateway, real worker, local pgvector
Postgres): sync validates and stamps the "Applies to" record on page_source and every
chunk; a table-only edit rides the §D.0 metadata-only restamp route (same
document_version id, zero embed calls); an invalid table fails the sync loudly by named
reason and the previously indexed state survives; a record on an untagged or classified
page grants nothing (membership stays labels-only). Fixture page 3011 (space 400): v1
valid software table · v2 valid connection table, content otherwise identical · v3 table
removed · v4 invalid unknown product.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once
from schema.models import Chunk, PageSource

from ._helpers import (
    enqueue_sync,
    install_counting_embedder,
    page_row_counts,
    read,
)

pytestmark = pytest.mark.db

_PAGE = 3011

# The stamped JSON payloads the validated fixture tables serialize to (applies_to_payload).
_V1_SOFTWARE = [{"level": "software", "product": "mews"}]
_V2_CONNECTION = [
    {
        "level": "connection",
        "connections": [
            {
                "type": "pms-accounting",
                "products": {"accounting": "quickbooks-online", "pms": "mews"},
                "directions": ["pms_to_accounting"],
            }
        ],
    }
]

_ZERO_ROWS = {
    "chunk": 0,
    "document_version": 0,
    "document": 0,
    "page_source": 0,
    "page_restriction": 0,
}


def _sync(gateway, settings, version: int, key: str):
    gateway.set_version(_PAGE, version)
    enqueue_sync(_PAGE, version, key=key)
    return run_once(gateway, settings, owner="test")


def _outcome(result) -> SyncOutcome:
    assert result is not None and isinstance(result.outcome, SyncOutcome), repr(result)
    return result.outcome


def _page_state() -> tuple[int | None, object, list]:
    """(active_doc_version_id, page_source.applicability, every chunk's applicability)."""
    with read() as s:
        ps = s.get(PageSource, _PAGE)
        assert ps is not None
        chunks = (
            s.execute(select(Chunk.applicability).where(Chunk.page_id == _PAGE)).scalars().all()
        )
        return ps.active_doc_version_id, ps.applicability, list(chunks)


def test_in2_applies_first_index_stamps_record_on_every_chunk(gateway, settings):
    """panel mi-applies · substep 8.2.2
    Sync validates the authored table and stamps the record on page_source and every chunk
    (parents and children); the table itself is metadata, never chunk content."""
    gateway.set_labels(_PAGE, ["obi-general"])
    assert _outcome(_sync(gateway, settings, 1, "applies-first:3011")).action == "indexed"

    version_id, ps_applies, chunk_applies = _page_state()
    assert version_id is not None
    assert ps_applies == _V1_SOFTWARE
    assert chunk_applies and all(a == _V1_SOFTWARE for a in chunk_applies)
    with read() as s:
        contents = (
            s.execute(select(Chunk.display_content).where(Chunk.page_id == _PAGE)).scalars().all()
        )
    assert contents and all("applies to" not in text.lower() for text in contents)


def test_in2_applies_metadata_edit_restamps_same_version_no_reembed(gateway, settings, monkeypatch):
    """panel mi-applies · substep 8.2.2
    A metadata edit (only the Applies-to table changed, content identical) restamps the
    existing chunks over the §D.0 restamp route: same document_version id, zero embed
    calls, stale eligibility replaced; a repeat sync is no_change."""
    gateway.set_labels(_PAGE, ["obi-general"])
    _sync(gateway, settings, 1, "applies-seed:3011")
    version_before, ps_applies, _ = _page_state()
    assert ps_applies == _V1_SOFTWARE

    counter = install_counting_embedder(monkeypatch, settings)
    outcome = _outcome(_sync(gateway, settings, 2, "applies-edit:3011"))
    assert outcome.action == "metadata_only"
    assert "applicability_restamped" in outcome.classes

    version_after, ps_applies, chunk_applies = _page_state()
    assert version_after == version_before  # same version id — no rebuild
    assert ps_applies == _V2_CONNECTION  # stale eligibility invalidated
    assert chunk_applies and all(a == _V2_CONNECTION for a in chunk_applies)
    assert counter.calls == 0  # no re-embed
    with read() as s:
        ps = s.get(PageSource, _PAGE)
        assert ps is not None and ps.current_cf_version == 2  # the revision is consumed

    assert _outcome(_sync(gateway, settings, 2, "applies-repeat:3011")).action == "no_change"
    assert counter.calls == 0


def test_in2_applies_record_removed_restamps_back_to_label_only(gateway, settings, monkeypatch):
    """panel mi-applies · substep 8.2.2
    Removing the Applies-to table restamps every chunk back to NULL — the documented
    label-only default — still metadata-only: same version id, zero embed calls."""
    gateway.set_labels(_PAGE, ["obi-general"])
    _sync(gateway, settings, 1, "applies-seed-rm:3011")
    version_before, ps_applies, _ = _page_state()
    assert ps_applies == _V1_SOFTWARE

    counter = install_counting_embedder(monkeypatch, settings)
    outcome = _outcome(_sync(gateway, settings, 3, "applies-remove:3011"))
    assert outcome.action == "metadata_only"

    version_after, ps_applies, chunk_applies = _page_state()
    assert version_after == version_before
    assert ps_applies is None
    assert chunk_applies and all(a is None for a in chunk_applies)
    assert counter.calls == 0


def test_in2_applies_invalid_table_fails_the_sync_loudly(gateway, settings, monkeypatch):
    """panel mi-applies · substep 8.2.2
    An invalid table (unknown product) fails the sync by named reason — never a silent
    fallback to label-only — and the previously indexed state survives untouched."""
    gateway.set_labels(_PAGE, ["obi-general"])
    _sync(gateway, settings, 1, "applies-seed-bad:3011")
    version_before, _, _ = _page_state()

    counter = install_counting_embedder(monkeypatch, settings)
    result = _sync(gateway, settings, 4, "applies-bad:3011")
    assert result is not None and result.status == "failed"
    assert "unknown-product" in (result.error or "")

    version_after, ps_applies, chunk_applies = _page_state()
    assert version_after == version_before  # the v1 build is still the active one
    assert ps_applies == _V1_SOFTWARE
    assert chunk_applies and all(a == _V1_SOFTWARE for a in chunk_applies)
    assert counter.calls == 0


def test_in2_applies_record_on_untagged_or_classified_page_grants_nothing(gateway, settings):
    """panel mi-applies · substep 8.2.2
    An applicability record never grants access: a page with a valid table but no
    recognized label is not indexed, and the classified label still purges — zero rows
    either way (membership stays labels-only; applicability only narrows relevance)."""
    gateway.set_labels(_PAGE, ["random-unrelated-label"])
    assert _outcome(_sync(gateway, settings, 1, "applies-untagged:3011")).action == "skipped"
    assert page_row_counts(_PAGE) == _ZERO_ROWS

    gateway.set_labels(_PAGE, ["obi-general", "classified"])
    outcome = _outcome(_sync(gateway, settings, 1, "applies-classified:3011"))
    assert outcome.action in ("skipped", "purged")
    assert page_row_counts(_PAGE) == _ZERO_ROWS
