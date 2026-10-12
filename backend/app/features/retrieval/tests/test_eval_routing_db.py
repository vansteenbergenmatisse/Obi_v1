"""panel mi-hardfilter · substep 9.5.2 — routing-off vs routing-on over a labelled gold stage.

The rule-11 before/after gate on the 9.4.1 directed-connection hard label filter. The bundled gold
set carries no routing labels (the Confluence relabel is the parallel owner task 9.5.1), so this
seeds the ``connection_routing`` gold stage's labelled pages directly in the DB (hermetic, mirroring
``test_label_hardfilter_db.py``) and runs the REAL ``HybridRetriever`` through the evaluation
harness twice per case: once with NO session labels (routing off — the pre-9.4.1 no-op path, every
candidate served) and once under the case's four directed-connection labels (routing on — the hard
filter narrows the candidate set).

Each case's pages share a private ``space_id`` (= the case ``scope``), so the two cases never
contaminate each other; every chunk shares one embedding + body, so dense + keyword return every
in-space page and only the label filter ever removes one. ``k`` is above the seeded corpus so the
served set is decided by the label filter, not by top-k truncation.

The measurement is written to ``backend/eval-reports/routing_lift.json`` (+ ``.md``); ``make eval``
prints it. The asserts are the acceptance contract: recall holds off→on (no gold-set loss),
served_precision rises and served_count falls (routing narrows). Break-it: feed ``on_fn`` no session
labels and the narrowing collapses to zero — the strict ``>``/``<`` asserts go red.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.features.evaluation import (
    EvalCase,
    datasets_dir,
    evaluate_routing_lift,
    load_dataset,
    write_routing_lift_reports,
)
from app.features.retrieval.application.retriever import HybridRetriever
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import get_settings
from schema import engine as engine_mod
from schema.enums import DocState, PageStatus
from schema.models import KIND_CHILD, Chunk, Document, DocumentVersion, PageSource

pytestmark = pytest.mark.db  # panel mi-hardfilter · substep 9.5.2

_BODY = "integration charges invoices guest sync mapping workflow"

# The labelled connection gold stage: one seeded page per (page_id, labels), grouped by the private
# space the case is scoped to. The relevant page is the directed answer; the rest are in-connection
# noise (served by both) or wrong-connection pages (served only by routing-off).
_SEED: dict[int, dict[int, list[str]]] = {
    # case cr-01 toast -> mews (space 95100): toast-to-pms is the answer.
    95100: {
        95101: ["obi-general"],  # in-connection noise
        95102: ["toast-general"],  # in-connection noise
        95103: ["toast-to-pms"],  # RELEVANT — the directed answer
        95104: ["toast-to-accounting"],  # wrong direction -> excluded by routing-on
        95105: ["mews-to-pos"],  # reverse direction -> excluded by routing-on
        95106: ["xero-general"],  # unrelated system -> excluded by routing-on
    },
    # case cr-02 mews -> quickbooks-online (space 95200): mews-to-accounting is the answer.
    95200: {
        95201: ["obi-general"],
        95202: ["mews-general"],
        95203: ["mews-to-accounting"],  # RELEVANT
        95204: ["mews-to-pos"],  # wrong direction -> excluded
        95205: ["toast-to-pms"],  # unrelated connection -> excluded
        95206: ["xero-general"],  # unrelated system -> excluded
    },
}


def _seed_page(session: Session, *, page_id: int, space_id: int, labels: list[str]) -> None:
    """One page chain + one active child chunk carrying ``labels`` in ``space_id``.

    Every chunk shares one embedding + body so dense + keyword return every in-space page; only the
    SQL label filter (and its mirrored RLS policy) ever removes one."""
    now = datetime.now(UTC)
    dim = get_settings().embedding_dim
    session.add(
        PageSource(
            page_id=page_id,
            space_id=space_id,
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
            space_id=space_id,
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


def _seed_all(session: Session) -> None:
    for space_id, pages in _SEED.items():
        for page_id, labels in pages.items():
            _seed_page(session, page_id=page_id, space_id=space_id, labels=labels)
    session.commit()


def _routing_fns() -> tuple[Callable[[EvalCase], list[str]], Callable[[EvalCase], list[str]]]:
    """Build the off (no labels) and on (the case's labels) rankers over one real retriever."""
    settings = get_settings()
    retriever = HybridRetriever(
        engine_mod.get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
    )

    def off_fn(case: EvalCase) -> list[str]:
        return retriever.retrieve(case.question, case.scope, k=50, session_labels=None)

    def on_fn(case: EvalCase) -> list[str]:
        return retriever.retrieve(
            case.question, case.scope, k=50, session_labels=case.session_labels
        )

    return off_fn, on_fn


def test_eval_routing_off_vs_on_records_no_loss_and_narrows(session: Session) -> None:
    """panel mi-hardfilter · substep 9.5.2
    Over the labelled connection gold stage, routing on keeps recall (no gold-set loss against the
    routing-off floor) while it narrows the served set — served_precision rises, served_count falls.
    The measurement is persisted to eval-reports/routing_lift.{json,md}."""
    _seed_all(session)
    dataset = load_dataset(datasets_dir() / "connection_routing.json")
    assert dataset.name == "connection_routing"
    assert dataset.cases  # the gold stage carries labelled connection questions
    assert all(case.session_labels for case in dataset.cases)

    off_fn, on_fn = _routing_fns()
    report = evaluate_routing_lift(dataset, off_fn, on_fn, now_iso="9.5.2")

    assert report.case_count == len(dataset.cases)

    # No gold-set loss: recall does not drop off -> on (and both find the directed answer).
    assert report.after["recall"] == report.before["recall"]
    assert report.after["recall"] == 1.0

    # Routing narrows the candidate set: fewer pages served, higher share of them relevant.
    assert report.after["served_count"] < report.before["served_count"]
    assert report.after["served_precision"] > report.before["served_precision"]

    # Concrete seeded shape: 6 candidates off, 3 (the in-connection labels) on, one relevant each.
    assert report.before["served_count"] == 6.0
    assert report.after["served_count"] == 3.0

    write_routing_lift_reports(report)


def test_eval_routing_off_vs_on_break_it_no_labels_is_zero_lift(session: Session) -> None:
    """panel mi-hardfilter · substep 9.5.2 (break-it)
    Undo the one thing routing-on does — pass NO session labels on the 'on' side — and the narrowing
    collapses: off == on, so served_precision/served_count deltas are exactly zero. This is the red
    the positive test turns green; it never writes the report artifact."""
    _seed_all(session)
    dataset = load_dataset(datasets_dir() / "connection_routing.json")
    off_fn, _ = _routing_fns()

    # The broken 'on' path: identical to off (the label filter is not applied).
    report = evaluate_routing_lift(dataset, off_fn, off_fn, now_iso="9.5.2-break")

    assert report.delta["served_precision"] == 0.0
    assert report.delta["served_count"] == 0.0
    assert report.before == report.after
