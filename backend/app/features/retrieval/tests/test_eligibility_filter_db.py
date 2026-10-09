"""panel mi-filter · substep 8.3.1 — eligibility filtering inside the database.

Database level: real chunk rows carrying the exact stamped ``applies_to_payload`` JSONB
(8.2.2's shape, built through the same validator) are searched through ``dense_search`` /
``keyword_search`` with :class:`EligibilityParams` derived from a customer context — and the
SQL predicate must agree with ``match_applicability`` (the §D.4 matcher is the oracle):
eligible = general + each filled slot + the pairs the company actually has; an explicitly
non-matching record excludes at ANY vector similarity; a chunk with NO record keeps
label-only behavior (absence never excludes — the §D.11 default); fewer than the 75-cap
eligible chunks are served as-is, never padded; recall equals the exact filtered baseline.

Seeding follows ``test_vector_data_nearest.py`` (page chain + one active child chunk whose
cosine distance to the query vector is controlled exactly); the engine bootstrap is the
shared ``app.tests.db_harness`` via the root conftest, truncation per test from this
directory's ``conftest.py``.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.features.ingestion import applies_to_payload, validate_applies_to
from app.features.retrieval.application.retriever import HybridRetriever
from app.features.retrieval.domain.applicability_match import (
    CustomerContext,
    eligibility_params,
    match_applicability,
)
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.features.retrieval.infrastructure.search_repo import (
    dense_search,
    fetch_rerank_texts,
    keyword_search,
)
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import get_settings
from app.platform.config.product_catalog import load_product_catalog
from schema import engine as engine_mod
from schema.enums import DocState, PageStatus
from schema.models import KIND_CHILD, Chunk, Document, DocumentVersion, PageSource

pytestmark = pytest.mark.db  # panel mi-filter · substep 8.3.1: real local Postgres

CATALOG = load_product_catalog()
PLATFORMS = frozenset({"datahub"})


def _payload(rules: list[dict[str, str]]) -> list[dict[str, object]]:
    """The exact stamped shape: authored rules → validator → applies_to_payload (8.2.2)."""
    return applies_to_payload(validate_applies_to(rules, CATALOG, PLATFORMS))


P_GENERAL = _payload([{"level": "general"}])
P_TOAST = _payload([{"level": "software", "product": "toast"}])
P_MEWS = _payload([{"level": "software", "product": "mews"}])
P_QBO = _payload([{"level": "software", "product": "quickbooks-online"}])
P_POS_PMS = _payload(
    [
        {
            "level": "connection",
            "connection": "pos-pms",
            "pos": "toast",
            "pms": "mews",
            "directions": "any",
        }
    ]
)
P_PMS_ACC = _payload(
    [
        {
            "level": "connection",
            "connection": "pms-accounting",
            "pms": "mews",
            "accounting": "quickbooks-online",
            "directions": "pms_to_accounting",
        }
    ]
)
P_POS_ACC = _payload(
    [
        {
            "level": "connection",
            "connection": "pos-accounting",
            "pos": "toast",
            "accounting": "quickbooks-online",
            "directions": "pos_to_accounting",
        }
    ]
)
P_PLATFORM = _payload([{"level": "platform-interface", "product": "toast", "platform": "datahub"}])
P_WORKFLOW = _payload(
    [
        {
            "level": "workflow",
            "binding": "same-instance",
            "connection-1": "pos-pms",
            "connection-1-pos": "toast",
            "connection-1-pms": "mews",
            "connection-1-directions": "any",
            "connection-2": "pms-accounting",
            "connection-2-pms": "mews",
            "connection-2-accounting": "quickbooks-online",
            "connection-2-directions": "any",
        }
    ]
)
P_VARIANT = _payload([{"level": "general", "variant-feature": "room-charges"}])

CTX_FULL = CustomerContext(
    slot_pos="toast", slot_pms="mews", slot_accounting="quickbooks-online", platform="datahub"
)
CTX_POS_PMS = CustomerContext(slot_pos="toast", slot_pms="mews")
CTX_PMS_ONLY = CustomerContext(slot_pms="mews")  # the legacy one-filled-slot shape
CTX_ACC_ONLY = CustomerContext(slot_accounting="quickbooks-online")
CTX_EMPTY = CustomerContext()


def _elig(context: CustomerContext):
    return eligibility_params(context, CATALOG)


def _query_vector(dim: int) -> list[float]:
    return [1.0] + [0.0] * (dim - 1)


def _unit_vector(dim: int, cos_sim: float) -> list[float]:
    other = math.sqrt(max(0.0, 1.0 - cos_sim * cos_sim))
    return [cos_sim, other] + [0.0] * (dim - 2)


def _seed_page(
    session: Session,
    *,
    page_id: int,
    cos_sim: float,
    payload: list[dict[str, object]] | None,
    text: str = "x",
) -> None:
    """One page chain + one active child chunk stamped with ``payload`` (None = no record),
    embedded so its cosine distance to the query vector is exactly ``1 - cos_sim``."""
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
            applicability=payload,
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
            display_content=text,
            retrieval_content=text,
            tokens=1,
            title=f"Page {page_id}",
            space_id=page_id,
            source_id="confluence:default",
            tags=["obi-general-test"],
            source_url=f"https://example.test/{page_id}",
            is_active=True,
            page_status=PageStatus.current,
            retrieval_schema_version=1,
            embedding_model="fake",
            access_scope=b"",
            embedding=_unit_vector(dim, cos_sim),
            applicability=payload,
        )
    )
    session.flush()
    # The keyword path needs a real tsvector (no trigger in the test schema — same approach as
    # test_vector_data_keyword.py's seeder).
    session.execute(
        sql_text("UPDATE chunk SET tsv = to_tsvector('english', :body) WHERE page_id = :pid"),
        {"body": text, "pid": page_id},
    )


def _dense_ids(session: Session, context: CustomerContext, limit: int = 50) -> set[int]:
    dim = get_settings().embedding_dim
    rows = dense_search(session, _query_vector(dim), None, limit, dim, eligibility=_elig(context))
    return {pid for pid, _ in rows}


def test_rt2_filter_slot_inclusion_and_exclusion_per_slot(session: Session) -> None:
    """panel mi-filter · substep 8.3.1
    Eligible = general + guides for each FILLED slot: a software rule's page is included
    exactly when its product fills that slot, excluded for every context that does not."""
    _seed_page(session, page_id=82001, cos_sim=0.9, payload=P_TOAST)
    _seed_page(session, page_id=82002, cos_sim=0.8, payload=P_MEWS)
    _seed_page(session, page_id=82003, cos_sim=0.7, payload=P_QBO)
    _seed_page(session, page_id=82004, cos_sim=0.6, payload=P_GENERAL)
    session.commit()

    assert _dense_ids(session, CTX_POS_PMS) == {82001, 82002, 82004}
    assert _dense_ids(session, CTX_ACC_ONLY) == {82003, 82004}
    assert _dense_ids(session, CTX_FULL) == {82001, 82002, 82003, 82004}
    assert _dense_ids(session, CTX_EMPTY) == {82004}


def test_rt2_filter_pair_inclusion_and_exclusion_per_pair(session: Session) -> None:
    """panel mi-filter · substep 8.3.1
    Eligible pairs are the ones the company ACTUALLY has: POS+PMS filled → the POS–PMS pair,
    PMS+Accounting filled → that pair; a direct POS–Accounting guide is never eligible from
    three filled slots (no derived pair — it needs a real connection record)."""
    _seed_page(session, page_id=82011, cos_sim=0.9, payload=P_POS_PMS)
    _seed_page(session, page_id=82012, cos_sim=0.8, payload=P_PMS_ACC)
    _seed_page(session, page_id=82013, cos_sim=0.7, payload=P_POS_ACC)
    session.commit()

    assert _dense_ids(session, CTX_FULL) == {82011, 82012}  # pos-acc never derived
    assert _dense_ids(session, CTX_POS_PMS) == {82011}
    assert _dense_ids(session, CTX_PMS_ONLY) == set()


def test_rt2_filter_excluded_page_never_appears_at_any_similarity(session: Session) -> None:
    """panel mi-filter · substep 8.3.1
    An excluded page never appears among the candidates regardless of vector similarity: the
    excluded chunk IS the query vector (distance 0, the best possible hit) and still never
    returns — on the dense path and the keyword path alike."""
    _seed_page(session, page_id=82021, cos_sim=1.0, payload=P_QBO, text="alpha bravo charlie")
    _seed_page(session, page_id=82022, cos_sim=0.2, payload=P_GENERAL, text="alpha bravo charlie")
    session.commit()

    assert _dense_ids(session, CTX_POS_PMS, limit=5) == {82022}
    kw = keyword_search(session, "alpha bravo", None, 5, eligibility=_elig(CTX_POS_PMS))
    assert {pid for pid, _ in kw} == {82022}


def test_rt2_filter_fewer_than_cap_served_as_is_never_padded(session: Session) -> None:
    """panel mi-filter · substep 8.3.1
    Up to rerank_candidate_k (the 75 setting) eligible chunks return; when only 3 are
    eligible the result is exactly those 3 — never padded with excluded pages, never a
    second query to fill the shortfall."""
    cap = get_settings().rerank_candidate_k
    assert cap == 75  # the §D.5 candidate cap is a setting, defaulting to 75
    for i, pid in enumerate((82031, 82032, 82033)):
        _seed_page(session, page_id=pid, cos_sim=0.5 - i * 0.05, payload=P_GENERAL)
    for i, pid in enumerate((82041, 82042, 82043, 82044, 82045)):
        _seed_page(session, page_id=pid, cos_sim=0.99 - i * 0.01, payload=P_QBO)
    session.commit()

    dim = get_settings().embedding_dim
    rows = dense_search(session, _query_vector(dim), None, cap, dim, eligibility=_elig(CTX_POS_PMS))
    assert [pid for pid, _ in rows] == [82031, 82032, 82033]  # as-is, no padding


def test_rt2_filter_absent_record_keeps_label_only_behavior(session: Session) -> None:
    """panel mi-filter · substep 8.3.1
    A chunk with NO applicability record stays eligible wherever access allows (absence
    never excludes — the documented §D.11 default); only an explicit non-matching record
    excludes (a variant requirement is unverifiable at launch, so it never matches)."""
    _seed_page(session, page_id=82051, cos_sim=0.9, payload=None)
    _seed_page(session, page_id=82052, cos_sim=0.8, payload=P_VARIANT)
    session.commit()

    assert _dense_ids(session, CTX_EMPTY) == {82051}
    assert _dense_ids(session, CTX_FULL) == {82051}


def test_rt2_filter_legacy_single_slot_context_parity(session: Session) -> None:
    """panel mi-filter · substep 8.3.1
    A legacy token (one filled slot) keeps today's behavior: general + unstamped pages still
    serve, its own slot's guides serve, and only explicitly-other records are excluded."""
    _seed_page(session, page_id=82061, cos_sim=0.9, payload=P_GENERAL)
    _seed_page(session, page_id=82062, cos_sim=0.8, payload=None)
    _seed_page(session, page_id=82063, cos_sim=0.7, payload=P_MEWS)
    _seed_page(session, page_id=82064, cos_sim=0.6, payload=P_TOAST)
    _seed_page(session, page_id=82065, cos_sim=0.5, payload=P_POS_PMS)
    session.commit()

    assert _dense_ids(session, CTX_PMS_ONLY) == {82061, 82062, 82063}


def test_rt2_filter_platform_interface_and_workflow_follow_the_matcher(
    session: Session,
) -> None:
    """panel mi-filter · substep 8.3.1
    Platform-interface rules need the filled slot AND the verified host platform (an unknown
    platform never broadens); workflow rules need every linked connection the company
    actually has — two filled slots alone never satisfy the three-system workflow."""
    _seed_page(session, page_id=82071, cos_sim=0.9, payload=P_PLATFORM)
    _seed_page(session, page_id=82072, cos_sim=0.8, payload=P_WORKFLOW)
    session.commit()

    assert _dense_ids(session, CTX_FULL) == {82071, 82072}
    assert _dense_ids(session, CustomerContext(slot_pos="toast")) == set()  # platform unknown
    assert _dense_ids(session, CTX_POS_PMS) == set()  # workflow needs the accounting pair too


def test_rt2_filter_rerank_texts_apply_the_same_eligibility(session: Session) -> None:
    """panel mi-filter · substep 8.3.1
    The rerank-text fetch enforces the same eligibility as the search — an excluded page id
    passed explicitly still yields no rerank candidate (never reranked back in)."""
    _seed_page(session, page_id=82081, cos_sim=0.9, payload=P_GENERAL)
    _seed_page(session, page_id=82082, cos_sim=0.8, payload=P_QBO)
    session.commit()

    candidates = fetch_rerank_texts(session, [82081, 82082], None, eligibility=_elig(CTX_POS_PMS))
    assert set(candidates) == {82081}


def test_rt2_filter_sql_mirrors_the_matcher_oracle(session: Session) -> None:
    """panel mi-filter · substep 8.3.1
    The SQL predicate and match_applicability are one semantics: for every stamped payload
    and every context shape, the pages the search returns are exactly the pages the matcher
    accepts (plus the no-record pages, which never reach the matcher)."""
    payloads: dict[int, list[dict[str, object]] | None] = {
        82101: P_GENERAL,
        82102: P_TOAST,
        82103: P_MEWS,
        82104: P_QBO,
        82105: P_POS_PMS,
        82106: P_PMS_ACC,
        82107: P_POS_ACC,
        82108: P_PLATFORM,
        82109: P_WORKFLOW,
        82110: P_VARIANT,
        82111: None,
    }
    for i, (pid, payload) in enumerate(sorted(payloads.items())):
        _seed_page(session, page_id=pid, cos_sim=0.9 - i * 0.01, payload=payload)
    session.commit()

    for context in (CTX_FULL, CTX_POS_PMS, CTX_PMS_ONLY, CTX_ACC_ONLY, CTX_EMPTY):
        expected = {
            pid
            for pid, payload in payloads.items()
            if payload is None or match_applicability(context, payload, CATALOG).matched
        }
        assert _dense_ids(session, context) == expected, f"context={context}"


def test_rt2_filter_recall_matches_exact_filtered_baseline(session: Session) -> None:
    """panel mi-filter · substep 8.3.1
    No recall loss against the exact filtered baseline: with 20 seeded pages at distinct
    distances, the filtered top-8 equals the exact baseline computed outside the database
    (matcher-eligible pages ordered by true cosine distance) — filtering happens before the
    limit, so no eligible page is pushed out by an excluded nearer one."""
    sims: dict[int, float] = {}
    for i in range(20):
        pid = 82200 + i
        payload = [P_GENERAL, P_QBO, P_MEWS, P_POS_PMS, None][i % 5]
        cos_sim = 0.95 - i * 0.03
        sims[pid] = cos_sim
        _seed_page(session, page_id=pid, cos_sim=cos_sim, payload=payload)
    session.commit()

    eligible = {
        pid
        for i, pid in enumerate(range(82200, 82220))
        if (p := [P_GENERAL, P_QBO, P_MEWS, P_POS_PMS, None][i % 5]) is None
        or match_applicability(CTX_POS_PMS, p, CATALOG).matched
    }
    exact_top8 = sorted(eligible, key=lambda pid: (1.0 - sims[pid], pid))[:8]

    dim = get_settings().embedding_dim
    rows = dense_search(session, _query_vector(dim), None, 8, dim, eligibility=_elig(CTX_POS_PMS))
    assert [pid for pid, _ in rows] == exact_top8


def test_rt2_filter_retriever_threads_the_context_into_one_filtered_search(
    session: Session,
) -> None:
    """panel mi-filter · substep 8.3.1
    HybridRetriever passes the customer context into the one search transaction: the
    excluded-but-nearest page never reaches the candidates or the reranker, while the same
    retriever without a context (the internal/eval path) still sees both pages."""
    _seed_page(session, page_id=82301, cos_sim=0.95, payload=P_QBO, text="alpha bravo")
    _seed_page(session, page_id=82302, cos_sim=0.3, payload=P_GENERAL, text="alpha bravo")
    session.commit()

    settings = get_settings()
    retriever = HybridRetriever(
        engine_mod.get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
    )
    filtered = retriever.retrieve("alpha bravo", None, k=5, customer_context=CTX_POS_PMS)
    assert filtered == ["82302"]

    unfiltered = retriever.retrieve("alpha bravo", None, k=5)
    assert set(unfiltered) == {"82301", "82302"}
