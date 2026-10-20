"""panels mi-hardfilter · mi-match · substep 9.4.1 — the directed-connection hard label filter.

Option A Stage 6 (ADR-directed-source-target-routing-labels D1/D2): ``_base_filters`` gains ``AND
labels && :session_labels`` at the
same spot as the ``tags`` overlap, threaded through keyword/dense candidate search AND the
rerank-text fetch, with the ``app.allowed_labels`` GUC set in the same path as the scope GUC so the
RESTRICTIVE ``chunk_labels_read`` RLS policy (migration 0016, inert until now) and the app predicate
agree. This module seeds the ``labels`` column directly (hermetic — the Confluence relabel is the
parallel owner content task 9.5.1) and runs the REAL ``HybridRetriever.retrieve_with_context`` under
a Toast→Mews session, asserting the EXACT include AND exclude page sets (never a count):

- a chunk whose only label is ``toast-to-accounting`` or ``mews-to-pos`` is NEVER served, at any
  vector similarity (every seeded chunk shares one embedding + body, so only the filter removes it);
- an empty-labels chunk is never served under an active connection (D2 self-gating);
- the rerank-text fetch applies the SAME predicate (an excluded page is never reranked in);
- recall against an exact filtered baseline (computed outside the DB) records no loss.

Seeding mirrors ``test_worked_examples_db.py``: one page chain + one active child chunk per page,
every page sharing one body + query term so keyword + dense return every page; ``k`` above the
corpus size so ranking can never drop a page — an excluded page is absent ONLY because the label
filter removed it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.features.retrieval.application.retriever import HybridRetriever
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.features.retrieval.infrastructure.search_repo import (
    apply_allowed_labels,
    apply_knowledge_scope,
    apply_source_scope,
    fetch_rerank_texts,
)
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import get_settings
from app.platform.config.product_catalog import load_product_catalog
from schema import engine as engine_mod
from schema.enums import DocState, PageStatus
from schema.models import KIND_CHILD, Chunk, Document, DocumentVersion, PageSource

pytestmark = pytest.mark.db  # panels mi-hardfilter/mi-match · substep 9.4.1

CATALOG = load_product_catalog()

# A Toast (POS) -> Mews (PMS) directed chat's four routing boxes (ProductCatalog.build_labels).
TOAST_TO_MEWS_LABELS = CATALOG.build_labels("toast", "mews")

_BODY = "integration charges invoices guest sync mapping workflow"


def _seed_page(session: Session, *, page_id: int, labels: list[str]) -> None:
    """One page chain + one active child chunk carrying ``labels`` (the raw routing axis).

    Every chunk gets the same embedding and body, so keyword + dense both return every seeded page;
    only the SQL label filter (+ its mirrored RLS policy) ever removes one."""
    now = datetime.now(UTC)
    dim = get_settings().embedding_dim
    session.add(
        PageSource(
            page_id=page_id,
            space_id=page_id,
            source_id="confluence:default",
            current_cf_version=1,
            page_status=PageStatus.current,
            title=f"Page {page_id}",
            source_url=f"https://example.test/{page_id}",
            source_modified_at=now,
            content_hash=f"ch-{page_id}".encode(),
            structure_hash=f"sh-{page_id}".encode(),
            attachment_manifest_hash=b"none",
            access_scope_hash=b"none",
            labels_hash=b"none",
            parser_version=1,
            chunker_version=1,
            contextualization_version=1,
            embedding_model="fake",
            embedding_dim=dim,
            retrieval_schema_version=1,
            labels=labels,
        )
    )
    session.add(Document(id=page_id, page_id=page_id))
    session.add(
        DocumentVersion(
            id=page_id,
            document_id=page_id,
            page_id=page_id,
            cf_version=1,
            state=DocState.active,
            content_hash=f"ch-{page_id}".encode(),
            structure_hash=f"sh-{page_id}".encode(),
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
            doc_version_id=page_id,
            page_id=page_id,
            cf_version=1,
            kind=KIND_CHILD,
            stable_key=f"sk-{page_id}".encode(),
            positional_key=f"pk-{page_id}".encode(),
            content_key=f"ck-{page_id}".encode(),
            content_hash=f"ch-{page_id}".encode(),
            seq=0,
            heading_path=[],
            location={},
            display_content=_BODY,
            retrieval_content=_BODY,
            tokens=1,
            title=f"Page {page_id}",
            space_id=page_id,
            source_id="confluence:default",
            tags=["obi-general-test"],
            labels=labels,
            source_url=f"https://example.test/{page_id}",
            is_active=True,
            page_status=PageStatus.current,
            retrieval_schema_version=1,
            embedding_model="fake",
            access_scope=b"",
            embedding=[1.0] + [0.0] * (dim - 1),
        )
    )
    session.flush()
    session.execute(
        sql_text("UPDATE chunk SET tsv = to_tsvector('english', :body) WHERE page_id = :pid"),
        {"body": _BODY, "pid": page_id},
    )


def _retrieve(session_labels: list[str] | None) -> set[int]:
    """Run the real retriever end to end under ``session_labels`` and return the served page ids."""
    settings = get_settings()
    retriever = HybridRetriever(
        engine_mod.get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
    )
    result = retriever.retrieve_with_context(_BODY, None, k=50, session_labels=session_labels)
    return {int(hit.page_id) for hit in result.hits}


def test_tags_toast_mews_chat_never_sees_wrong_connection_at_any_similarity(
    session: Session,
) -> None:
    """panels mi-hardfilter/mi-match · substep 9.4.1
    A Toast->Mews chat gets exactly the pages whose labels overlap its four routing boxes; a page
    whose ONLY label is toast-to-accounting or mews-to-pos is never served, at any similarity."""
    _seed_page(session, page_id=94101, labels=["obi-general"])
    _seed_page(session, page_id=94102, labels=["toast-general"])
    _seed_page(session, page_id=94103, labels=["toast-to-pms"])  # the directed box
    _seed_page(session, page_id=94104, labels=["toast-to-accounting"])  # wrong direction
    _seed_page(session, page_id=94105, labels=["mews-to-pos"])  # wrong direction
    _seed_page(session, page_id=94106, labels=["xero-general"])  # not in this connection
    session.commit()

    got = _retrieve(TOAST_TO_MEWS_LABELS)

    assert got == {94101, 94102, 94103}  # exact include list
    assert {94104, 94105, 94106}.isdisjoint(got)  # exact exclude list


def test_tags_empty_labels_chunk_never_served_under_active_connection(session: Session) -> None:
    """panel mi-hardfilter · substep 9.4.1 (ADR-directed-source-target-routing-labels D2)
    An unlabelled chunk overlaps nothing, so it is invisible under an active connection filter."""
    _seed_page(session, page_id=94201, labels=["obi-general"])
    _seed_page(session, page_id=94202, labels=[])  # empty labels — self-gating
    session.commit()

    got = _retrieve(TOAST_TO_MEWS_LABELS)

    assert got == {94201}
    assert 94202 not in got


def test_tags_rerank_text_fetch_is_already_label_filtered(session: Session) -> None:
    """panel mi-hardfilter · substep 9.4.1
    The rerank-text fetch applies the same labels predicate, so a wrong-connection page is never
    reranked in even when its id is handed in directly."""
    _seed_page(session, page_id=94301, labels=["toast-to-pms"])
    _seed_page(session, page_id=94302, labels=["mews-to-pos"])  # wrong connection
    session.commit()

    with engine_mod.get_reader_sessionmaker()() as reader:
        apply_source_scope(reader, ("confluence:default",))
        apply_knowledge_scope(reader, None)  # scope opt-out; labels are the axis under test
        apply_allowed_labels(reader, TOAST_TO_MEWS_LABELS)
        got = fetch_rerank_texts(reader, [94301, 94302], None, session_labels=TOAST_TO_MEWS_LABELS)

    assert set(got) == {94301}
    assert 94302 not in got


def test_tags_recall_against_exact_filtered_baseline_records_no_loss(session: Session) -> None:
    """panel mi-hardfilter · substep 9.4.1
    Every page whose labels overlap the session labels is served (no eligible page dropped); the
    retrieved set equals the exact baseline computed outside the DB."""
    seeded = {
        94401: ["obi-general"],
        94402: ["toast-general", "toast-to-pms"],
        94403: ["mews-general"],
        94404: ["toast-to-accounting"],  # excluded
        94405: ["mews-to-pos"],  # excluded
        94406: [],  # excluded (empty)
        94407: ["opera-general"],  # excluded (unrelated system)
    }
    for pid, labels in seeded.items():
        _seed_page(session, page_id=pid, labels=labels)
    session.commit()

    session_labels = set(TOAST_TO_MEWS_LABELS)
    baseline = {pid for pid, labels in seeded.items() if session_labels & set(labels)}

    got = _retrieve(TOAST_TO_MEWS_LABELS)

    assert got == baseline  # no recall loss, no leakage


def test_tags_legacy_token_without_session_labels_is_a_no_op(session: Session) -> None:
    """panel mi-hardfilter · substep 9.4.1
    A legacy/slot chat carries no session labels: the label filter is a no-op (fail-open for the
    relevance axis), so an unlabelled chunk is still served — source/scope locks are the fence."""
    _seed_page(session, page_id=94501, labels=[])
    _seed_page(session, page_id=94502, labels=["toast-to-accounting"])
    session.commit()

    got = _retrieve(None)

    assert got == {94501, 94502}
