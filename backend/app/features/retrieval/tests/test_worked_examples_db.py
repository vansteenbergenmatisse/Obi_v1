"""panels mi-validate · mi-match · mi-filter · substep 8.5.1 — the five worked examples
reproduce their EXACT include AND exclude documentation lists end to end (database level).

plan.md §D.9 states the five concrete examples as categories of documentation to include and
exclude. This module makes each example a single end-to-end retrieval test: it seeds a small
corpus of pages whose stamped applicability payloads realise those categories, runs the REAL
``HybridRetriever.retrieve_with_context`` under the example's verified customer context (the one
search the whole pipeline uses — in-SQL eligibility, 8.3.1; context-aware rerank, 8.3.2;
per-slot attribution, 8.3.4), and asserts BOTH the exact set of included page ids AND the exact
set of excluded page ids — never a count. The inclusion REASON is inspected per result through
the attribution each hit carries (``general`` / ``pos`` / ``pms`` / ``accounting`` / ``pair``),
which the backend assembles from the §D.4 matcher reason — so every example also proves that
inclusion reasons are inspectable per result (panel mi-validate).

The §D.9 categories map onto the launch catalog vocabulary like this (documented, not a
weakening — the oracle is §D.9, transcribed exactly into concrete pages):

- "general" -> a ``general`` rule (always eligible).
- "Mews" / "QuickBooks" / "Toast" / "Xero" / "Opera Cloud" guidance -> a ``software`` rule for
  that canonical product, eligible only when its catalog role fills the matching slot.
- "accounting" guidance for a QuickBooks customer -> that customer's actual accounting product
  (QuickBooks Online) — the launch catalog carries no separate accounting-scope payload (no
  accounting scope tag exists yet; catalog.md §5 / decision-memo O9), so the accounting
  guidance a customer sees IS its accounting product's guidance.
- "Mews/QuickBooks" / "Mews/Xero" / "room-charge" (Toast->Mews) / direct "Toast/QuickBooks"
  guidance -> a ``connection`` rule for that pair; eligible only for a connection the company
  actually has (derived from filled slots, or a real connection record the context carries).
- the three-system "workflow guidance" -> a ``workflow`` rule binding Toast->Mews and
  Mews->QuickBooks on the same instance.

Example 5 — the Toast/OperaCloud + Mews/QuickBooks property — cannot be expressed by the
single-product-per-role launch token (it has two PMS products). It is modelled faithfully by a
context carrying the two REAL connection records it actually has (Toast<->OperaCloud and
Mews<->QuickBooks) and empty slots, exactly the ``CustomerContext.connections`` shape the matcher
accepts (context-contract §9). Its headline assertion — a Toast/Mews pair guide is NEVER
eligible — is the cross-matching regression guard (panel mi-match).

Seeding mirrors ``test_eligibility_filter_db.py``: one page chain + one active child chunk per
page, every page sharing one body + query term so the keyword path returns every eligible page,
``k`` set above the corpus size so ranking can never drop an eligible page (an excluded page is
absent only because the SQL eligibility predicate removed it, never because of the limit).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.features.ingestion import applies_to_payload, validate_applies_to
from app.features.retrieval.application.retriever import HybridRetriever
from app.features.retrieval.domain.applicability_match import (
    AttributionValue,
    ConnectionRecord,
    CustomerContext,
)
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import get_settings
from app.platform.config.product_catalog import load_product_catalog
from schema import engine as engine_mod
from schema.enums import DocState, PageStatus
from schema.models import KIND_CHILD, Chunk, Document, DocumentVersion, PageSource

pytestmark = pytest.mark.db  # panels mi-validate/mi-match/mi-filter · substep 8.5.1

CATALOG = load_product_catalog()
PLATFORMS = frozenset({"datahub"})

# Every seeded page shares this body so the keyword path returns them all; the query is the same
# text, so eligibility — not ranking — is the only thing that ever removes a page.
_BODY = "integration charges invoices guest sync mapping workflow"


def _payload(rules: list[dict[str, str]]) -> list[dict[str, object]]:
    """The exact stamped shape: authored rules -> validator -> applies_to_payload (8.2.2)."""
    return applies_to_payload(validate_applies_to(rules, CATALOG, PLATFORMS))


P_GENERAL = _payload([{"level": "general"}])
P_TOAST = _payload([{"level": "software", "product": "toast"}])
P_MEWS = _payload([{"level": "software", "product": "mews"}])
P_QBO = _payload([{"level": "software", "product": "quickbooks-online"}])
P_XERO = _payload([{"level": "software", "product": "xero"}])
P_OPERA = _payload([{"level": "software", "product": "opera-cloud"}])
# Toast->Mews room charges (POS->PMS direction) and Mews->Toast guest info (PMS->POS direction):
# two directions of the ONE Toast/Mews connection.
P_ROOMCHARGE = _payload(
    [
        {
            "level": "connection",
            "connection": "pos-pms",
            "pos": "toast",
            "pms": "mews",
            "directions": "pos_to_pms",
        }
    ]
)
P_GUESTINFO = _payload(
    [
        {
            "level": "connection",
            "connection": "pos-pms",
            "pos": "toast",
            "pms": "mews",
            "directions": "pms_to_pos",
        }
    ]
)
P_MEWS_QBO = _payload(
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
P_MEWS_XERO = _payload(
    [
        {
            "level": "connection",
            "connection": "pms-accounting",
            "pms": "mews",
            "accounting": "xero",
            "directions": "pms_to_accounting",
        }
    ]
)
P_TOAST_OPERA = _payload(
    [
        {
            "level": "connection",
            "connection": "pos-pms",
            "pos": "toast",
            "pms": "opera-cloud",
            "directions": "any",
        }
    ]
)
# A direct Toast->QuickBooks guide (POS->Accounting): never eligible from slots alone (§5.2).
P_TOAST_QBO = _payload(
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
# The three-system workflow: Toast->Mews room charges feeding Mews->QuickBooks, same instance.
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


def _seed_page(session: Session, *, page_id: int, payload: list[dict[str, object]] | None) -> None:
    """One page chain + one active child chunk stamped with ``payload`` (None = no record).

    Every chunk gets the same embedding and body text, so keyword + dense both return every
    seeded page; only the SQL eligibility predicate ever removes one."""
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
            display_content=_BODY,
            retrieval_content=_BODY,
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
            embedding=[1.0] + [0.0] * (dim - 1),
            applicability=payload,
        )
    )
    session.flush()
    # No tsvector trigger in the test schema (same as the sibling db seeders): populate it.
    session.execute(
        sql_text("UPDATE chunk SET tsv = to_tsvector('english', :body) WHERE page_id = :pid"),
        {"body": _BODY, "pid": page_id},
    )


def _retrieve(context: CustomerContext) -> dict[int, AttributionValue | None]:
    """Run the real retriever end to end and return ``{page_id: attribution}`` for every hit."""
    settings = get_settings()
    retriever = HybridRetriever(
        engine_mod.get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
    )
    result = retriever.retrieve_with_context(_BODY, None, k=20, customer_context=context)
    return {int(hit.page_id): hit.attribution for hit in result.hits}


# ---------------------------------------------------------------------------------------------
# Example 1 — "Why are my Mews invoices missing in QuickBooks?"
#   include: general, Mews, QuickBooks (accounting), Mews/QuickBooks; exclude: Mews/Xero and the
#   unrelated room-charge (Toast/Mews) instructions (the customer has no POS).  [§D.9 example 1]
# ---------------------------------------------------------------------------------------------
def test_rt2_example1_mews_invoices_missing_in_quickbooks(session: Session) -> None:
    """panels mi-validate/mi-filter · substep 8.5.1
    A Mews+QuickBooks customer gets exactly general, Mews, QuickBooks and the Mews/QuickBooks
    guide; Mews/Xero, the unrelated room-charge guide, Xero and Toast guides are all excluded."""
    _seed_page(session, page_id=85101, payload=P_GENERAL)
    _seed_page(session, page_id=85102, payload=P_MEWS)
    _seed_page(session, page_id=85103, payload=P_QBO)
    _seed_page(session, page_id=85104, payload=P_MEWS_QBO)
    _seed_page(session, page_id=85105, payload=P_MEWS_XERO)
    _seed_page(session, page_id=85106, payload=P_ROOMCHARGE)
    _seed_page(session, page_id=85107, payload=P_XERO)
    _seed_page(session, page_id=85108, payload=P_TOAST)
    session.commit()

    got = _retrieve(CustomerContext(slot_pms="mews", slot_accounting="quickbooks-online"))

    assert got == {
        85101: "general",
        85102: "pms",
        85103: "accounting",
        85104: "pair",
    }  # exact include list + inspectable inclusion reason per result
    assert {85105, 85106, 85107, 85108}.isdisjoint(got)  # exact exclude list


# ---------------------------------------------------------------------------------------------
# Example 2 — "Why are Toast room charges missing in Mews?"  use the verified POS->PMS
#   connection and its relevant guidance.  [§D.9 example 2]
# ---------------------------------------------------------------------------------------------
def test_rt2_example2_toast_room_charges_missing_in_mews(session: Session) -> None:
    """panels mi-validate/mi-filter · substep 8.5.1
    A Toast+Mews customer gets general, Toast, Mews and BOTH directions of the one Toast/Mews
    connection (the room-charge POS->PMS guide included, attributed `pair`); the accounting
    guides and the direct Toast/QuickBooks guide are excluded (no accounting slot)."""
    _seed_page(session, page_id=85121, payload=P_GENERAL)
    _seed_page(session, page_id=85122, payload=P_TOAST)
    _seed_page(session, page_id=85123, payload=P_MEWS)
    _seed_page(session, page_id=85124, payload=P_ROOMCHARGE)
    _seed_page(session, page_id=85125, payload=P_GUESTINFO)
    _seed_page(session, page_id=85126, payload=P_MEWS_QBO)
    _seed_page(session, page_id=85127, payload=P_QBO)
    _seed_page(session, page_id=85128, payload=P_TOAST_QBO)
    session.commit()

    got = _retrieve(CustomerContext(slot_pos="toast", slot_pms="mews"))

    assert got == {
        85121: "general",
        85122: "pos",
        85123: "pms",
        85124: "pair",  # the POS->PMS room-charge guidance the question is about
        85125: "pair",  # same connection, PMS->POS direction also eligible
    }
    assert {85126, 85127, 85128}.isdisjoint(got)


# ---------------------------------------------------------------------------------------------
# Example 3 — "Why is Mews guest information unavailable in Toast?"  use the enabled PMS->POS
#   direction.  [§D.9 example 3]
# ---------------------------------------------------------------------------------------------
def test_rt2_example3_mews_guest_info_unavailable_in_toast(session: Session) -> None:
    """panels mi-validate/mi-filter · substep 8.5.1
    The same Toast+Mews customer gets general, Toast, Mews and the enabled PMS->POS guest-info
    guide (attributed `pair`); Mews/Xero and Opera-Cloud guides are excluded."""
    _seed_page(session, page_id=85141, payload=P_GENERAL)
    _seed_page(session, page_id=85142, payload=P_TOAST)
    _seed_page(session, page_id=85143, payload=P_MEWS)
    _seed_page(session, page_id=85144, payload=P_GUESTINFO)
    _seed_page(session, page_id=85145, payload=P_ROOMCHARGE)
    _seed_page(session, page_id=85146, payload=P_MEWS_XERO)
    _seed_page(session, page_id=85147, payload=P_OPERA)
    session.commit()

    got = _retrieve(CustomerContext(slot_pos="toast", slot_pms="mews"))

    assert got == {
        85141: "general",
        85142: "pos",
        85143: "pms",
        85144: "pair",  # the enabled PMS->POS direction
        85145: "pair",  # the POS->PMS direction of the same connection
    }
    assert {85146, 85147}.isdisjoint(got)


# ---------------------------------------------------------------------------------------------
# Example 4 — "Why are restaurant charges not reaching QuickBooks?" (property with Toast/Mews
#   AND Mews/QuickBooks)  include BOTH relevant connections and the workflow guidance; exclude a
#   direct Toast/QuickBooks guide unless that connection actually exists.  [§D.9 example 4]
# ---------------------------------------------------------------------------------------------
def test_rt2_example4_restaurant_charges_not_reaching_quickbooks(session: Session) -> None:
    """panels mi-validate/mi-filter · substep 8.5.1
    The full three-slot customer gets general, each slot guide, BOTH its connections
    (Toast/Mews and Mews/QuickBooks) and the three-system workflow guide (all attributed
    `pair`); the direct Toast/QuickBooks guide is excluded — that connection does not exist."""
    _seed_page(session, page_id=85161, payload=P_GENERAL)
    _seed_page(session, page_id=85162, payload=P_TOAST)
    _seed_page(session, page_id=85163, payload=P_MEWS)
    _seed_page(session, page_id=85164, payload=P_QBO)
    _seed_page(session, page_id=85165, payload=P_ROOMCHARGE)
    _seed_page(session, page_id=85166, payload=P_MEWS_QBO)
    _seed_page(session, page_id=85167, payload=P_WORKFLOW)
    _seed_page(session, page_id=85168, payload=P_TOAST_QBO)
    session.commit()

    got = _retrieve(
        CustomerContext(
            slot_pos="toast",
            slot_pms="mews",
            slot_accounting="quickbooks-online",
            platform="datahub",
        )
    )

    assert got == {
        85161: "general",
        85162: "pos",
        85163: "pms",
        85164: "accounting",
        85165: "pair",  # the Toast/Mews connection
        85166: "pair",  # the Mews/QuickBooks connection
        85167: "pair",  # the three-system workflow
    }
    assert 85168 not in got  # the direct Toast/QuickBooks guide — no real connection (§5.2)


# ---------------------------------------------------------------------------------------------
# Example 5 — a property with Toast/OperaCloud AND Mews/QuickBooks must NOT qualify for
#   Toast/Mews guidance merely because both products are present somewhere.  [§D.9 example 5]
#   This is the headline cross-matching guard (panel mi-match). The two-PMS property cannot be
#   expressed by the single-product-per-role launch token, so it is modelled by the two REAL
#   connection records it actually has, with empty slots (context-contract §9).
# ---------------------------------------------------------------------------------------------
def test_rt2_example5_two_connections_never_cross_match_toast_mews(session: Session) -> None:
    """panels mi-match/mi-validate/mi-filter · substep 8.5.1
    With Toast<->OperaCloud and Mews<->QuickBooks (and no Toast<->Mews connection), the property
    gets general and its two real connection guides; a Toast/Mews pair guide — both directions —
    and the three-system workflow are NEVER eligible, and neither are the bare Toast and Mews
    software guides (no filled slot). Fails loudly if cross-matching ever regresses."""
    _seed_page(session, page_id=85181, payload=P_GENERAL)
    _seed_page(session, page_id=85182, payload=P_TOAST_OPERA)
    _seed_page(session, page_id=85183, payload=P_MEWS_QBO)
    _seed_page(session, page_id=85184, payload=P_ROOMCHARGE)  # Toast/Mews — MUST be excluded
    _seed_page(session, page_id=85185, payload=P_GUESTINFO)  # Toast/Mews other direction
    _seed_page(session, page_id=85186, payload=P_WORKFLOW)  # needs a Toast/Mews connection
    _seed_page(session, page_id=85187, payload=P_MEWS)  # Mews present only in a connection
    _seed_page(session, page_id=85188, payload=P_TOAST)  # Toast present only in a connection
    session.commit()

    context = CustomerContext(
        connections=(
            ConnectionRecord(
                connection_type="pos-pms",
                products=(("pos", "toast"), ("pms", "opera-cloud")),
                directions=("pos_to_pms", "pms_to_pos"),
            ),
            ConnectionRecord(
                connection_type="pms-accounting",
                products=(("pms", "mews"), ("accounting", "quickbooks-online")),
                directions=("pms_to_accounting",),
            ),
        )
    )
    got = _retrieve(context)

    assert got == {
        85181: "general",
        85182: "pair",  # the real Toast/OperaCloud connection
        85183: "pair",  # the real Mews/QuickBooks connection
    }
    # The headline: Toast/Mews guidance never qualifies from two unrelated connections.
    assert 85184 not in got
    assert 85185 not in got
    assert 85186 not in got
    assert {85184, 85185, 85186, 85187, 85188}.isdisjoint(got)
