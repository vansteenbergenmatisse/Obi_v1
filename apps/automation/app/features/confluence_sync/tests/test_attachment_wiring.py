"""Attachment content flows into the searchable chunk index (fixes/phase-2 wiring).

Closes the last open finding from docs/rag/fixes/phase-2.md: `attachment_extraction.py` was
fully built and tested in isolation but had zero production call sites, so attachment content
(PDF/DOCX/XLSX/CSV/HTML) was never chunked/embedded/searchable. This wires it into the real sync
path end-to-end over the fixture corpus, which already ships real .txt/.csv/.md attachments for
pages 1001/1002 plus placeholder binaries for the pdf/xlsx parser paths.
"""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.sync_service import handle_sync_page
from app.platform.clients.fixture_confluence_client import FixtureConfluenceGateway
from app.platform.config import Settings
from app.platform.db.engine import session_scope
from app.platform.db.models import PageSource

from ._helpers import active_child_chunks, index_page

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest


def _texts(page_id: int) -> list[str]:
    return [c.display_content for c in active_child_chunks(page_id)]


def test_text_attachment_content_is_indexed_and_searchable(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    index_page(gateway, settings, 1001, 1)
    blob = " ".join(_texts(1001))
    assert "Sign the code of conduct" in blob  # welcome-checklist.txt
    # "Carol" / "HR Lead" appear only in team-roster.csv, not in the page's own body (unlike
    # "Alice"/"team-onboarding", which the page body also happens to mention) — an unambiguous
    # proof the CSV attachment's own content was indexed, not just body text that overlaps it.
    assert "Carol" in blob and "HR Lead" in blob  # team-roster.csv, flattened


def test_i2_tobuild_body_and_attachment_blocks_both_reach_chunker(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    """panel i2-tobuild · substep 0.5.2
    On a rebuild, the body blocks AND the attachment blocks are unioned before being handed to
    ingestion stage 3's chunker (sync_service.py: ``blocks=blocks + attachment_blocks``) — neither
    set silently drops the other. Proven here by a phrase found only in page 1001's v1 body
    ("Approvals take up to three business days", from the Getting Access section) and a phrase
    found only in its welcome-checklist.txt attachment ("Sign the code of conduct"), both landing
    in the same page's active chunk set from a single sync.
    """
    index_page(gateway, settings, 1001, 1)
    blob = " ".join(_texts(1001))
    assert "Approvals take up to three business days" in blob  # body-derived
    assert "Sign the code of conduct" in blob  # attachment-derived


def test_markdown_attachment_content_is_indexed(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    index_page(gateway, settings, 1002, 1)
    blob = " ".join(_texts(1002))
    assert "make rollback ENV=production" in blob  # rollback-notes.md


def test_placeholder_pdf_and_xlsx_degrade_to_no_chunk_not_a_crash(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    # page 1002's architecture-diagram.pdf / capacity-plan.xlsx are backed by a plain-text
    # placeholder file, not a real binary — native parsing must fail closed to "" (never raise),
    # so attachment_to_blocks contributes nothing for them, not garbage text.
    with session_scope() as s:
        outcome = handle_sync_page(s, page_id=1002, gateway=gateway, settings=settings)
    assert outcome.action == "indexed"
    blob = " ".join(_texts(1002))
    assert "architecture-diagram" not in blob
    assert "PLACEHOLDER" not in blob


def test_attachment_chunks_inherit_page_acl_and_source(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    index_page(gateway, settings, 1001, 1)
    checklist_chunk = next(
        c for c in active_child_chunks(1001) if "code of conduct" in c.display_content
    )
    assert checklist_chunk.page_id == 1001
    assert checklist_chunk.source_type == "confluence"
    assert checklist_chunk.is_active is True


def test_resyncing_unchanged_page_is_a_true_no_change_not_a_spurious_rebuild(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    """Regression proof: content_hash/structure_hash must stay body-only.

    If attachment text were folded into the persisted content_hash/structure_hash, the next
    sync's freshly computed (body-only) hash would permanently disagree with what's stored,
    spuriously reclassifying every subsequent sync as body_changed and re-downloading/re-
    embedding attachments on every reconciliation tick even when nothing changed.
    """
    index_page(gateway, settings, 1001, 1)
    with session_scope() as s:
        outcome = handle_sync_page(s, page_id=1001, gateway=gateway, settings=settings)
    assert outcome.action == "no_change"


def test_i2_nochange_no_change_resync_still_stamps_last_reconciled_at(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    """panel i2-nochange · substep 0.5.2
    When the fingerprint equals the stored one, the no-change path still updates
    last_reconciled_at before it stops -- it is a reconciliation touch, not a total no-op."""
    index_page(gateway, settings, 1001, 1)
    with session_scope() as s:
        before = s.get(PageSource, 1001)
        assert before is not None
        assert before.last_reconciled_at is None  # untouched by the initial index

    with session_scope() as s:
        outcome = handle_sync_page(s, page_id=1001, gateway=gateway, settings=settings)
    assert outcome.action == "no_change"

    with session_scope() as s:
        after = s.get(PageSource, 1001)
        assert after is not None
        assert after.last_reconciled_at is not None  # stamped by the no-change resync


def test_unchanged_attachment_reuses_embedding_across_a_body_driven_rebuild(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    """An unrelated body edit (v1 -> v3) still carries forward the unchanged attachment's chunk
    with its prior embedding reused (diff_chunks), not recomputed — the diff mechanism is content-
    addressed via the attachment's own title-keyed heading path, agnostic to origin."""
    index_page(gateway, settings, 1001, 1)
    before = next(c for c in active_child_chunks(1001) if "code of conduct" in c.display_content)
    embedding_before = before.embedding
    stable_key_before = before.stable_key

    index_page(gateway, settings, 1001, 3)  # v3 body edit; attachments unchanged
    after = next(c for c in active_child_chunks(1001) if "code of conduct" in c.display_content)
    assert after.stable_key == stable_key_before
    assert after.embedding == embedding_before


def test_oversized_attachment_metadata_is_skipped_before_download(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    tiny_cap = settings.model_copy(update={"confluence_attachment_max_bytes": 10})
    index_page(gateway, tiny_cap, 1001, 1)
    blob = " ".join(_texts(1001))
    assert "Sign the code of conduct" not in blob
    assert "HR Lead" not in blob


def test_unfetchable_attachment_is_skipped_not_a_sync_failure(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    attachments = gateway.get_attachments(1001)
    checklist = next(a for a in attachments if a["title"] == "welcome-checklist.txt")
    gateway.set_attachment_content(checklist["downloadLink"], None)  # simulate a failed download

    with session_scope() as s:
        outcome = handle_sync_page(s, page_id=1001, gateway=gateway, settings=settings)

    assert outcome.action == "indexed"
    blob = " ".join(_texts(1001))
    assert "Sign the code of conduct" not in blob  # the failed one is absent
    assert "HR Lead" in blob  # the sibling attachment still indexed fine


def test_attachment_only_change_is_metadata_only_disclosed_limitation(
    gateway: FixtureConfluenceGateway, settings: Settings
) -> None:
    """A newly-added attachment with no other page change stays metadata_only, not indexed yet.

    Documents a real, deliberate limitation (sync_service.py's _REBUILD_CLASSES comment): Confluence
    attachments carry their own version numbers independent of the page's cf_version, and
    DocumentVersion's uq_document_version_idem constraint is unique per (document, cf_version,
    schema, model) — one build per real page revision. Rebuilding on attachment_changed alone
    (tried first) hit exactly this constraint's IntegrityError in a live run, not a hypothetical.
    The attachment is picked up as soon as any other rebuild-triggering event next occurs.
    """
    index_page(gateway, settings, 1001, 1)
    baseline = set(_texts(1001))

    gateway.set_attachment_content("/download/attachments/1001/new-file.txt", b"brand new content")
    original_get_attachments = gateway.get_attachments

    def get_attachments_with_new_file(page_id: int) -> list[dict]:
        out = original_get_attachments(page_id)
        if page_id == 1001:
            out = [
                *out,
                {
                    "id": "att-1001-new",
                    "title": "new-file.txt",
                    "mediaType": "text/plain",
                    "fileSize": 18,
                    "version": 1,
                    "downloadLink": "/download/attachments/1001/new-file.txt",
                },
            ]
        return out

    gateway.get_attachments = get_attachments_with_new_file  # type: ignore[method-assign]
    with session_scope() as s:
        outcome = handle_sync_page(s, page_id=1001, gateway=gateway, settings=settings)

    assert outcome.action == "metadata_only"  # not "indexed" — no crash, no false success either
    assert set(_texts(1001)) == baseline  # the new attachment is not yet in the chunk index

    # picked up on the next rebuild-triggering event (a body edit, here v1 -> v3)
    with session_scope() as s:
        outcome2 = handle_sync_page(s, page_id=1001, gateway=gateway, settings=settings)
    gateway.set_version(1001, 3)
    with session_scope() as s:
        outcome3 = handle_sync_page(s, page_id=1001, gateway=gateway, settings=settings)
    assert outcome2.action == "no_change"
    assert outcome3.action == "indexed"
    assert "brand new content" in " ".join(_texts(1001))
