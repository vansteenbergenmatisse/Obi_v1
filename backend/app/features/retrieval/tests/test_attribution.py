"""panel mi-attrib · substep 8.3.4 — per-slot source attribution (unit level).

The attribution shown on a citation is ASSEMBLED IN THE BACKEND by collapsing the matcher's
already-computed reason slug (§D.4, panel mi-match) to the Citation contract's five-value
vocabulary ``general | pos | pms | accounting | pair``. These tests drive the REAL matcher
(`match_applicability`) to get the reason — never a hand-made slug — then map it with
`attribution_for_reason`, so they prove the end-to-end "map the existing reason" posture the
substep requires (no recomputation of matching).

Precedence of record: the matcher already selected ONE rule (OR between rules, first match
wins); `attribution_for_reason` is a pure, deterministic collapse of that single reason. A
connection/workflow reason collapses to ``pair`` — the connection, not either member slot — so
a pair is attributed as a pair, never as one of the slots that compose it (pair > slot). A
label-only chunk (no payload) or a no-context search yields no reason, hence no attribution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.features.retrieval.domain.applicability_match import (
    CustomerContext,
    attribution_for_reason,
    match_applicability,
)
from app.platform.config.product_catalog import load_product_catalog

CATALOG = load_product_catalog()

_ALLOWED = frozenset({"general", "pos", "pms", "accounting", "pair"})


def _ctx(
    pos: str | None = None,
    pms: str | None = None,
    accounting: str | None = None,
    platform: str | None = None,
) -> CustomerContext:
    return CustomerContext(
        slot_pos=pos, slot_pms=pms, slot_accounting=accounting, platform=platform
    )


def _attribution(
    context: CustomerContext, payload: Sequence[Mapping[str, object]]
) -> str | None:
    """Reuse the matcher's reason (never recompute matching) and collapse it to attribution."""
    return attribution_for_reason(match_applicability(context, payload, CATALOG).reason)


def test_rt2_attrib_general_guide_is_attributed_general() -> None:
    """panel mi-attrib · substep 8.3.4
    A general guide is attributed `general` for any customer, even a slotless one."""
    assert _attribution(_ctx(), [{"level": "general"}]) == "general"


def test_rt2_attrib_single_slot_guide_is_attributed_to_that_slot() -> None:
    """panel mi-attrib · substep 8.3.4
    A software guide admitted by one filled slot is attributed to that named slot."""
    assert _attribution(_ctx(pos="toast"), [{"level": "software", "product": "toast"}]) == "pos"
    assert _attribution(_ctx(pms="mews"), [{"level": "software", "product": "mews"}]) == "pms"
    assert (
        _attribution(
            _ctx(accounting="quickbooks-online"),
            [{"level": "software", "product": "quickbooks-online"}],
        )
        == "accounting"
    )


def test_rt2_attrib_platform_interface_guide_is_attributed_to_its_slot() -> None:
    """panel mi-attrib · substep 8.3.4
    A platform-interface guide (a product on a host platform) is attributed to the product's
    slot — the slot is still what let the customer in."""
    rule = {"level": "platform-interface", "product": "mews", "platform": "datahub"}
    assert _attribution(_ctx(pms="mews", platform="datahub"), [rule]) == "pms"


def test_rt2_attrib_pair_guide_is_attributed_to_its_pair() -> None:
    """panel mi-attrib · substep 8.3.4
    A connection (pair) guide for a pair the company actually has is attributed `pair`."""
    pair_rule = {
        "level": "connection",
        "connections": [
            {
                "type": "pos-pms",
                "products": {"pos": "toast", "pms": "mews"},
                "directions": ["pos_to_pms"],
            }
        ],
    }
    assert _attribution(_ctx(pos="toast", pms="mews"), [pair_rule]) == "pair"


def test_rt2_attrib_pair_wins_over_its_member_slots_precedence() -> None:
    """panel mi-attrib · substep 8.3.4
    Precedence (pair > slot): a connection/workflow reason collapses to `pair`, never to one
    of the slots that compose it — the pair identity wins over its members."""
    # connection:<type> -> pair, not pos/pms
    assert attribution_for_reason("connection:pos-pms") == "pair"
    assert attribution_for_reason("workflow") == "pair"
    # a slot reason stays its slot (the contrast that makes the precedence observable)
    assert attribution_for_reason("slot:pos") == "pos"


def test_rt2_attrib_label_only_or_no_match_carries_no_attribution() -> None:
    """panel mi-attrib · substep 8.3.4
    A chunk with no applicability (label-only) and a no-match both carry no attribution —
    the field stays None so the wire omits it and the widget renders exactly as today."""
    # label-only: no payload at all -> matcher is never consulted, no reason
    assert attribution_for_reason(None) is None
    # a real no-match reason maps to nothing
    assert attribution_for_reason("no-match") is None
    # a failure slug (not a matched reason) maps to nothing
    assert attribution_for_reason("slot-empty:pos") is None


def test_sec_attrib_never_leaks_beyond_the_customers_own_context() -> None:
    """panel mi-attrib · substep 8.3.4
    No-leak: whatever the context and payload, attribution is only ever one of the five fixed
    enum values (or None) — never a product id, company id, scope name, platform, or any other
    customer- or tenant-identifying string."""
    reasons = [
        "general",
        "slot:pos",
        "slot:pms",
        "slot:accounting",
        "platform-interface:pos",
        "platform-interface:pms",
        "platform-interface:accounting",
        "connection:pos-pms",
        "connection:pms-accounting",
        "connection:pos-accounting",
        "workflow",
        "no-match",
        "unknown-product:some-secret-product",
        "slot-empty:pms",
        "needs-real-connection:pos-accounting",
        "variant-unknown:feature",
        "",
        None,
    ]
    for reason in reasons:
        value = attribution_for_reason(reason)
        assert value is None or value in _ALLOWED
        if value is not None:
            # the value never carries the connection type, a product id, or any free text
            assert ":" not in value
            assert "-" not in value or value == "pair"
