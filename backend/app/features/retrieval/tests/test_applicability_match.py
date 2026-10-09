"""panel mi-match · substep 8.2.3 — deterministic matching (unit level).

Pure-function tests: ``(CustomerContext, stamped applicability payload) → MatchResult``.
AND within one rule on the same actual connection, OR between rules, launch pairs derived
from filled slots only (POS–PMS and PMS–Accounting; a direct POS–Accounting pair NEVER
derives from three filled slots — it needs a real connection record, §D.4/O1). Incomplete
context serves the applicable general guidance and asks for the missing configuration;
it never broadens. Payloads below are the exact JSON shape 8.2.2 stamps on chunks
(``applies_to_payload``) — no second vocabulary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.features.retrieval.domain.applicability_match import (
    ConnectionRecord,
    CustomerContext,
    MatchResult,
    derive_connections,
    match_applicability,
)
from app.platform.config.product_catalog import load_product_catalog

CATALOG = load_product_catalog()


def _ctx(
    pos: str | None = None,
    pms: str | None = None,
    accounting: str | None = None,
    platform: str | None = None,
    connections: tuple[ConnectionRecord, ...] = (),
) -> CustomerContext:
    return CustomerContext(
        slot_pos=pos,
        slot_pms=pms,
        slot_accounting=accounting,
        platform=platform,
        connections=connections,
    )


def _conn_rule(type_: str, products: dict[str, str], directions: list[str]) -> dict[str, object]:
    return {
        "level": "connection",
        "connections": [{"type": type_, "products": products, "directions": directions}],
    }


def _record(type_: str, products: dict[str, str], directions: tuple[str, ...]) -> ConnectionRecord:
    return ConnectionRecord(
        connection_type=type_,
        products=tuple(sorted(products.items())),
        directions=directions,
    )


MEWS_QB = _conn_rule(
    "pms-accounting",
    {"pms": "mews", "accounting": "quickbooks-online"},
    ["pms_to_accounting"],
)
OPERA_XERO = _conn_rule(
    "pms-accounting", {"pms": "opera-cloud", "accounting": "xero"}, ["pms_to_accounting"]
)
TOAST_MEWS = _conn_rule("pos-pms", {"pos": "toast", "pms": "mews"}, ["pos_to_pms"])
TOAST_QB = _conn_rule(
    "pos-accounting", {"pos": "toast", "accounting": "quickbooks-online"}, ["pos_to_accounting"]
)
WORKFLOW_TOAST_MEWS_QB: dict[str, object] = {
    "level": "workflow",
    "bindings": ["same-instance", "same-property"],
    "connections": [
        {
            "type": "pos-pms",
            "products": {"pos": "toast", "pms": "mews"},
            "directions": ["pos_to_pms"],
        },
        {
            "type": "pms-accounting",
            "products": {"pms": "mews", "accounting": "quickbooks-online"},
            "directions": ["pms_to_accounting"],
        },
    ],
}


def _match(context: CustomerContext, payload: Sequence[Mapping[str, object]]) -> MatchResult:
    return match_applicability(context, payload, CATALOG)


# --- the three negative cases (red-first) ------------------------------------------------


def test_rt2_match_mews_xero_cross_match_impossible() -> None:
    """panel mi-match · substep 8.2.3
    A page applying to Mews/QuickBooks OR OperaCloud/Xero never matches Mews/Xero —
    rules never blend: each complete rule must hold on one actual connection."""
    result = _match(_ctx(pms="mews", accounting="xero"), [MEWS_QB, OPERA_XERO])
    assert result.matched is False
    assert result.reason == "no-match"
    # The Mews/Xero pair is real and derived — the rules simply do not cover it; no ask.
    assert result.missing == ()


def test_rt2_match_products_existing_somewhere_never_satisfy_a_connection_rule() -> None:
    """panel mi-match · substep 8.2.3
    Toast/OperaCloud plus Mews/QuickBooks at one property never qualifies for Toast/Mews
    guidance: both products exist somewhere, but no single actual connection joins them."""
    context = _ctx(
        connections=(
            _record(
                "pos-pms",
                {"pos": "toast", "pms": "opera-cloud"},
                ("pos_to_pms", "pms_to_pos"),
            ),
            _record(
                "pms-accounting",
                {"pms": "mews", "accounting": "quickbooks-online"},
                ("pms_to_accounting",),
            ),
        )
    )
    result = _match(context, [TOAST_MEWS])
    assert result.matched is False
    assert result.reason == "no-match"


def test_rt2_match_three_slots_never_derive_a_pos_accounting_pair() -> None:
    """panel mi-match · substep 8.2.3
    Three filled slots never produce a direct POS–Accounting pair — that needs a real
    connection record; the no-match names the missing connection so the answer can ask."""
    context = _ctx(pos="toast", pms="mews", accounting="quickbooks-online")
    derived = derive_connections(context, CATALOG)
    assert all(c.connection_type != "pos-accounting" for c in derived)
    result = _match(context, [TOAST_QB])
    assert result.matched is False
    assert result.missing == ("connection:pos-accounting",)


# --- the positive case per level ---------------------------------------------------------


def test_rt2_match_general_level_matches_any_context() -> None:
    """panel mi-match · substep 8.2.3
    A general rule matches every context, even one with no filled slot at all."""
    result = _match(_ctx(), [{"level": "general"}])
    assert result.matched is True
    assert result.reason == "general"
    assert result.rule_index == 0


def test_rt2_match_software_level_matches_the_filled_slot() -> None:
    """panel mi-match · substep 8.2.3
    A software-level rule for Mews matches a context whose PMS slot holds mews, and the
    reason names the slot that let it in (per-slot attribution, §D.13 keuze 3)."""
    result = _match(_ctx(pms="mews"), [{"level": "software", "product": "mews"}])
    assert result.matched is True
    assert result.reason == "slot:pms"


def test_rt2_match_software_level_different_product_never_matches() -> None:
    """panel mi-match · substep 8.2.3
    A software rule for Mews never matches a context whose PMS slot holds opera-cloud —
    and this is not an ask: the configuration is known, just different."""
    result = _match(_ctx(pms="opera-cloud"), [{"level": "software", "product": "mews"}])
    assert result.matched is False
    assert result.missing == ()


def test_rt2_match_platform_interface_requires_product_and_platform() -> None:
    """panel mi-match · substep 8.2.3
    A platform-interface rule (Mews inside Data Hub) ANDs the product slot with the host
    platform: right platform matches, wrong platform never does."""
    rule = {"level": "platform-interface", "product": "mews", "platform": "datahub"}
    hit = _match(_ctx(pms="mews", platform="datahub"), [rule])
    assert hit.matched is True
    assert hit.reason == "platform-interface:pms"
    miss = _match(_ctx(pms="mews", platform="mews"), [rule])
    assert miss.matched is False


def test_rt2_match_platform_unknown_asks_never_broadens() -> None:
    """panel mi-match · substep 8.2.3
    An unknown host platform never matches a platform-interface rule; the result flags
    the missing configuration instead of broadening."""
    rule = {"level": "platform-interface", "product": "mews", "platform": "datahub"}
    result = _match(_ctx(pms="mews", platform=None), [rule])
    assert result.matched is False
    assert result.missing == ("platform",)


def test_rt2_match_connection_level_matches_the_derived_pair() -> None:
    """panel mi-match · substep 8.2.3
    A Mews/QuickBooks connection rule matches the PMS–Accounting pair derived from the
    two filled slots the company actually has."""
    result = _match(_ctx(pms="mews", accounting="quickbooks-online"), [MEWS_QB])
    assert result.matched is True
    assert result.reason == "connection:pms-accounting"


def test_rt2_match_explicit_any_binds_to_the_actual_connection() -> None:
    """panel mi-match · substep 8.2.3
    An explicit any on the accounting side matches the company's ACTUAL accounting
    connection — and still needs one: with the accounting slot empty it asks, never
    broadens."""
    rule = _conn_rule("pms-accounting", {"pms": "mews", "accounting": "any"}, ["pms_to_accounting"])
    hit = _match(_ctx(pms="mews", accounting="xero"), [rule])
    assert hit.matched is True
    assert hit.reason == "connection:pms-accounting"
    miss = _match(_ctx(pms="mews"), [rule])
    assert miss.matched is False
    assert miss.missing == ("slot:accounting",)


def test_rt2_match_workflow_matches_two_linked_derived_connections() -> None:
    """panel mi-match · substep 8.2.3
    A Toast→Mews→QuickBooks workflow rule matches when both linked connections derive
    from the three filled slots (one company, one property: the binding holds by
    construction); losing the accounting slot drops it to an ask."""
    full = _match(
        _ctx(pos="toast", pms="mews", accounting="quickbooks-online"), [WORKFLOW_TOAST_MEWS_QB]
    )
    assert full.matched is True
    assert full.reason == "workflow"
    partial = _match(_ctx(pos="toast", pms="mews"), [WORKFLOW_TOAST_MEWS_QB])
    assert partial.matched is False
    assert partial.missing == ("slot:accounting",)


def test_rt2_match_or_between_rules_second_rule_matches() -> None:
    """panel mi-match · substep 8.2.3
    Rules OR together: a payload whose first rule needs a connection the company lacks
    still matches through its second, software-level rule."""
    result = _match(_ctx(pms="mews"), [MEWS_QB, {"level": "software", "product": "mews"}])
    assert result.matched is True
    assert result.reason == "slot:pms"
    assert result.rule_index == 1


def test_rt2_match_real_connection_record_unlocks_the_direct_pair() -> None:
    """panel mi-match · substep 8.2.3
    A direct Toast/QuickBooks rule matches ONLY through a real POS–Accounting connection
    record — the thing three filled slots can never produce."""
    record = _record(
        "pos-accounting",
        {"pos": "toast", "accounting": "quickbooks-online"},
        ("pos_to_accounting",),
    )
    context = _ctx(pos="toast", pms="mews", accounting="quickbooks-online", connections=(record,))
    result = _match(context, [TOAST_QB])
    assert result.matched is True
    assert result.reason == "connection:pos-accounting"


def test_rt2_match_direction_must_be_enabled_on_the_same_connection() -> None:
    """panel mi-match · substep 8.2.3
    A rule requiring pos_to_pms never matches a real Toast–Mews connection with only
    pms_to_pos enabled — the required flow must be enabled on that same connection."""
    one_way = _record("pos-pms", {"pos": "toast", "pms": "mews"}, ("pms_to_pos",))
    result = _match(_ctx(connections=(one_way,)), [TOAST_MEWS])
    assert result.matched is False
    both_ways = _record("pos-pms", {"pos": "toast", "pms": "mews"}, ("pos_to_pms", "pms_to_pos"))
    assert _match(_ctx(connections=(both_ways,)), [TOAST_MEWS]).matched is True


def test_rt2_match_incomplete_context_serves_general_and_asks() -> None:
    """panel mi-match · substep 8.2.3
    Incomplete context serves the applicable general guidance and asks for the missing
    configuration; it never broadens to connection-level matches."""
    context = _ctx(pms="mews")  # accounting unknown/absent
    assert _match(context, [{"level": "general"}]).matched is True
    result = _match(context, [MEWS_QB])
    assert result.matched is False
    assert result.missing == ("slot:accounting",)


def test_rt2_match_variant_requirement_without_context_never_matches() -> None:
    """panel mi-match · substep 8.2.3
    A variant requirement the launch context cannot verify never matches — the result
    asks for the variant instead of assuming it."""
    rule = {
        "level": "software",
        "product": "mews",
        "variants": {"accounting-flow": "invoice-based"},
    }
    result = _match(_ctx(pms="mews"), [rule])
    assert result.matched is False
    assert result.missing == ("variant:accounting-flow",)


def test_rt2_match_derived_pairs_come_from_filled_slots_only() -> None:
    """panel mi-match · substep 8.2.3
    Launch pairs derive from filled slots only: one filled slot derives nothing; POS+PMS
    derives the POS–PMS connection (both §D.2 directions); PMS+Accounting derives the
    PMS–Accounting connection."""
    assert derive_connections(_ctx(pms="mews"), CATALOG) == ()
    pos_pms = derive_connections(_ctx(pos="toast", pms="mews"), CATALOG)
    assert [c.connection_type for c in pos_pms] == ["pos-pms"]
    assert set(pos_pms[0].directions) == {"pos_to_pms", "pms_to_pos"}
    assert dict(pos_pms[0].products) == {"pos": "toast", "pms": "mews"}
    pms_acc = derive_connections(_ctx(pms="mews", accounting="xero"), CATALOG)
    assert [c.connection_type for c in pms_acc] == ["pms-accounting"]
    assert dict(pms_acc[0].products) == {"pms": "mews", "accounting": "xero"}
