"""panel mi-applies · substep 8.2.1 — the "Applies to" schema.

Unit tests for the validated applicability record: the five levels (general ·
software · platform-interface · connection · workflow) plus variant requirements,
explicit any, loud named failures, one vocabulary (the product catalog). The
five §D.3 worked examples are the positive fixtures. No network, no database.
"""

from __future__ import annotations

import pytest

from app.features.ingestion.domain.applicability import (
    ApplicabilityValidationError,
    AppliesTo,
    validate_applies_to,
    validate_rule,
)
from app.platform.config.product_catalog import (
    Product,
    ProductCatalog,
    load_product_catalog,
)

# The real committed catalog: deterministic, read once, no network.
CATALOG = load_product_catalog()

# Platform vocabulary for level 3 — platforms.json keys; base lands with O7.
PLATFORMS = frozenset({"datahub", "obi-test"})


def _rule(fields: dict[str, str]):
    return validate_rule(fields, CATALOG, PLATFORMS)


def _reason(fields: dict[str, str]) -> str:
    with pytest.raises(ApplicabilityValidationError) as exc:
        _rule(fields)
    return exc.value.reason


# ---------------------------------------------------------------- positive —
# each of the five levels validates with an example (See-check), and every
# §D.3 worked example is expressible.


def test_in2_applies_general_level_validates() -> None:
    """panel mi-applies · substep 8.2.1
    Level 1: general guidance validates with no product fields at all."""
    rule = _rule({"level": "general"})
    assert rule.level == "general"
    assert rule.product is None and rule.connections == ()


def test_in2_applies_software_level_validates_mews() -> None:
    """panel mi-applies · substep 8.2.1
    Worked example 1: general Mews guidance → software level, product mews."""
    rule = _rule({"level": "software", "product": "mews"})
    assert rule.level == "software"
    assert rule.product == "mews"


def test_in2_applies_platform_interface_level_validates() -> None:
    """panel mi-applies · substep 8.2.1
    Level 3: Mews inside Data Hub — product plus a known platform."""
    rule = _rule({"level": "platform-interface", "product": "mews", "platform": "datahub"})
    assert rule.product == "mews"
    assert rule.platform == "datahub"


def test_in2_applies_connection_level_names_products_roles_type_directions() -> None:
    """panel mi-applies · substep 8.2.1
    Worked example 3 (Mews→QuickBooks): a connection-level record names the
    products, their roles, the connection type and the flow directions."""
    rule = _rule(
        {
            "level": "connection",
            "connection": "pms-accounting",
            "pms": "mews",
            "accounting": "quickbooks-online",
            "directions": "pms_to_accounting",
        }
    )
    (spec,) = rule.connections
    assert spec.connection_type == "pms-accounting"
    assert dict(spec.products) == {"pms": "mews", "accounting": "quickbooks-online"}
    assert spec.directions == ("pms_to_accounting",)


def test_in2_applies_explicit_any_accounting_target_validates() -> None:
    """panel mi-applies · substep 8.2.1
    Worked example 2: Mews connected to ANY supported accounting target — the
    any is authored explicitly and kept literally (it tracks the catalog)."""
    rule = _rule(
        {
            "level": "connection",
            "connection": "pms-accounting",
            "pms": "mews",
            "accounting": "any",
            "directions": "pms_to_accounting",
        }
    )
    (spec,) = rule.connections
    assert dict(spec.products)["accounting"] == "any"


def test_in2_applies_toast_mews_room_charge_direction_validates() -> None:
    """panel mi-applies · substep 8.2.1
    Worked example 4: Toast-to-Mews room charges — the actual pos_to_pms flow
    direction, not the whole pos-pms connection."""
    rule = _rule(
        {
            "level": "connection",
            "connection": "pos-pms",
            "pos": "toast",
            "pms": "mews",
            "directions": "pos_to_pms",
        }
    )
    (spec,) = rule.connections
    assert spec.directions == ("pos_to_pms",)


def test_in2_applies_workflow_two_linked_connections_validates() -> None:
    """panel mi-applies · substep 8.2.1
    Worked example 5: Toast→Mews→QuickBooks — two connections linked through
    the same Mews instance at the same property."""
    rule = _rule(
        {
            "level": "workflow",
            "binding": "same-instance, same-property",
            "connection-1": "pos-pms",
            "connection-1-pos": "toast",
            "connection-1-pms": "mews",
            "connection-1-directions": "pos_to_pms",
            "connection-2": "pms-accounting",
            "connection-2-pms": "mews",
            "connection-2-accounting": "quickbooks-online",
            "connection-2-directions": "pms_to_accounting",
        }
    )
    assert rule.bindings == ("same-instance", "same-property")
    assert len(rule.connections) == 2
    shared = set(dict(rule.connections[0].products).values()) & set(
        dict(rule.connections[1].products).values()
    )
    assert "mews" in shared


def test_in2_applies_two_rules_or_together() -> None:
    """panel mi-applies · substep 8.2.1
    §D.4: Mews/QuickBooks OR OperaCloud/Xero is two separate complete rules —
    the record keeps them separate, never merges them into Mews/Xero."""
    record = validate_applies_to(
        [
            {
                "level": "connection",
                "connection": "pms-accounting",
                "pms": "mews",
                "accounting": "quickbooks-online",
                "directions": "pms_to_accounting",
            },
            {
                "level": "connection",
                "connection": "pms-accounting",
                "pms": "opera-cloud",
                "accounting": "xero",
                "directions": "pms_to_accounting",
            },
        ],
        CATALOG,
        PLATFORMS,
    )
    assert isinstance(record, AppliesTo)
    assert len(record.rules) == 2
    first, second = (dict(r.connections[0].products) for r in record.rules)
    assert first == {"pms": "mews", "accounting": "quickbooks-online"}
    assert second == {"pms": "opera-cloud", "accounting": "xero"}


def test_in2_applies_alias_resolves_to_canonical() -> None:
    """panel mi-applies · substep 8.2.1
    One vocabulary: an authored alias (operacloud) resolves to the canonical
    catalog id (opera-cloud) before validation, exactly like the gate."""
    rule = _rule({"level": "software", "product": "operacloud"})
    assert rule.product == "opera-cloud"


def test_in2_applies_directions_any_expands_to_the_types_directions() -> None:
    """panel mi-applies · substep 8.2.1
    directions: any is explicit and expands deterministically to every flow
    direction the connection type defines in the catalog."""
    rule = _rule(
        {
            "level": "connection",
            "connection": "pos-pms",
            "pos": "toast",
            "pms": "mews",
            "directions": "any",
        }
    )
    (spec,) = rule.connections
    assert set(spec.directions) == {"pos_to_pms", "pms_to_pos"}


def test_in2_applies_variant_requirements_validate() -> None:
    """panel mi-applies · substep 8.2.1
    Variant requirements (feature, accounting flow, version) ride any level as
    optional restrictions and are kept on the rule."""
    rule = _rule(
        {
            "level": "software",
            "product": "mews",
            "variant-feature": "open-balance",
            "variant-accounting-flow": "accrual",
            "variant-version": "2",
        }
    )
    assert dict(rule.variants) == {
        "feature": "open-balance",
        "accounting-flow": "accrual",
        "version": "2",
    }


def test_in2_applies_catalog_exposes_connection_directions() -> None:
    """panel mi-applies · substep 8.2.1
    The catalog loader exposes each connection type's flow directions — the
    schema never defines a second direction vocabulary."""
    assert set(CATALOG.connection_directions["pos-pms"]) == {"pos_to_pms", "pms_to_pos"}
    assert CATALOG.connection_directions["pms-accounting"] == ("pms_to_accounting",)


# ---------------------------------------------------------------- negative —
# each malformed variant fails with a named reason; a missing field never
# silently becomes a wildcard.


def test_in2_applies_missing_level_fails_loudly() -> None:
    """panel mi-applies · substep 8.2.1
    A record with no level fails loudly with the named missing field."""
    assert _reason({"product": "mews"}) == "missing-field:level"


def test_in2_applies_unknown_level_fails() -> None:
    """panel mi-applies · substep 8.2.1
    A level outside the five is a named failure, never a guess."""
    assert _reason({"level": "integration"}) == "unknown-level"


def test_in2_applies_missing_product_never_becomes_wildcard() -> None:
    """panel mi-applies · substep 8.2.1
    Software level without a product fails loudly — it never widens to all
    products."""
    assert _reason({"level": "software"}) == "missing-field:product"


def test_in2_applies_missing_role_field_never_becomes_wildcard() -> None:
    """panel mi-applies · substep 8.2.1
    A pms-accounting rule that omits the accounting side fails loudly — the
    missing side never silently becomes any."""
    reason = _reason(
        {
            "level": "connection",
            "connection": "pms-accounting",
            "pms": "mews",
            "directions": "pms_to_accounting",
        }
    )
    assert reason == "missing-field:accounting"


def test_in2_applies_missing_directions_fails() -> None:
    """panel mi-applies · substep 8.2.1
    A connection rule without flow directions fails loudly — directions are
    required, never defaulted."""
    reason = _reason(
        {
            "level": "connection",
            "connection": "pos-pms",
            "pos": "toast",
            "pms": "mews",
        }
    )
    assert reason == "missing-field:directions"


def test_in2_applies_product_any_at_software_level_rejected() -> None:
    """panel mi-applies · substep 8.2.1
    product: any at software level is rejected by name — guidance for every
    product is authored as level general, never as a product wildcard."""
    assert _reason({"level": "software", "product": "any"}) == "any-not-allowed"


def test_in2_applies_variant_any_rejected() -> None:
    """panel mi-applies · substep 8.2.1
    A variant of any is rejected — an optional restriction is omitted, not
    wildcarded."""
    reason = _reason({"level": "software", "product": "mews", "variant-feature": "any"})
    assert reason == "any-not-allowed"


def test_in2_applies_unknown_product_fails() -> None:
    """panel mi-applies · substep 8.2.1
    A product outside the catalog fails closed with a named reason."""
    assert _reason({"level": "software", "product": "lightspeed"}) == "unknown-product"


def test_in2_applies_role_mismatch_toast_as_pms_fails() -> None:
    """panel mi-applies · substep 8.2.1
    toast in the pms side of a connection fails — the catalog role decides."""
    reason = _reason(
        {
            "level": "connection",
            "connection": "pos-pms",
            "pos": "mews",
            "pms": "toast",
            "directions": "pos_to_pms",
        }
    )
    assert reason == "role-mismatch"


def test_in2_applies_unknown_connection_type_fails() -> None:
    """panel mi-applies · substep 8.2.1
    A connection type outside the catalog fails with a named reason."""
    reason = _reason(
        {
            "level": "connection",
            "connection": "pos-crm",
            "pos": "toast",
            "directions": "any",
        }
    )
    assert reason == "unknown-connection-type"


def test_in2_applies_direction_outside_type_fails() -> None:
    """panel mi-applies · substep 8.2.1
    A direction the connection type does not define fails with a named reason."""
    reason = _reason(
        {
            "level": "connection",
            "connection": "pos-pms",
            "pos": "toast",
            "pms": "mews",
            "directions": "pms_to_accounting",
        }
    )
    assert reason == "unknown-direction"


def test_in2_applies_unknown_field_fails_never_ignored() -> None:
    """panel mi-applies · substep 8.2.1
    A typo'd field name is a loud failure, never silently ignored — a dropped
    condition would silently widen the rule."""
    reason = _reason({"level": "software", "prodcut": "mews"})
    assert reason == "unknown-field"


def test_in2_applies_unknown_platform_fails() -> None:
    """panel mi-applies · substep 8.2.1
    A platform outside the registry vocabulary fails with a named reason."""
    reason = _reason({"level": "platform-interface", "product": "mews", "platform": "base"})
    assert reason == "unknown-platform"


def test_in2_applies_workflow_single_connection_fails() -> None:
    """panel mi-applies · substep 8.2.1
    A workflow needs at least two linked connections."""
    reason = _reason(
        {
            "level": "workflow",
            "binding": "same-instance",
            "connection-1": "pos-pms",
            "connection-1-pos": "toast",
            "connection-1-pms": "mews",
            "connection-1-directions": "pos_to_pms",
        }
    )
    assert reason == "too-few-connections"


def test_in2_applies_workflow_unlinked_connections_fail() -> None:
    """panel mi-applies · substep 8.2.1
    Two connections that share no concrete product are not a workflow —
    Toast/Mews plus OperaCloud/Xero never qualifies."""
    reason = _reason(
        {
            "level": "workflow",
            "binding": "same-instance",
            "connection-1": "pos-pms",
            "connection-1-pos": "toast",
            "connection-1-pms": "mews",
            "connection-1-directions": "pos_to_pms",
            "connection-2": "pms-accounting",
            "connection-2-pms": "opera-cloud",
            "connection-2-accounting": "xero",
            "connection-2-directions": "pms_to_accounting",
        }
    )
    assert reason == "unlinked-connections"


def test_in2_applies_workflow_any_never_links_connections() -> None:
    """panel mi-applies · substep 8.2.1
    any on both sides never counts as the shared product — a wildcard cannot
    be the link that binds a workflow."""
    reason = _reason(
        {
            "level": "workflow",
            "binding": "same-instance",
            "connection-1": "pos-pms",
            "connection-1-pos": "toast",
            "connection-1-pms": "any",
            "connection-1-directions": "pos_to_pms",
            "connection-2": "pms-accounting",
            "connection-2-pms": "any",
            "connection-2-accounting": "xero",
            "connection-2-directions": "pms_to_accounting",
        }
    )
    assert reason == "unlinked-connections"


def test_in2_applies_workflow_missing_binding_fails() -> None:
    """panel mi-applies · substep 8.2.1
    A workflow without an explicit binding fails loudly — bindings are never
    assumed."""
    reason = _reason(
        {
            "level": "workflow",
            "connection-1": "pos-pms",
            "connection-1-pos": "toast",
            "connection-1-pms": "mews",
            "connection-1-directions": "pos_to_pms",
            "connection-2": "pms-accounting",
            "connection-2-pms": "mews",
            "connection-2-accounting": "xero",
            "connection-2-directions": "pms_to_accounting",
        }
    )
    assert reason == "missing-field:binding"


def test_in2_applies_unknown_binding_fails() -> None:
    """panel mi-applies · substep 8.2.1
    A binding outside the vocabulary fails with a named reason."""
    reason = _reason(
        {
            "level": "workflow",
            "binding": "same-hotel",
            "connection-1": "pos-pms",
            "connection-1-pos": "toast",
            "connection-1-pms": "mews",
            "connection-1-directions": "pos_to_pms",
            "connection-2": "pms-accounting",
            "connection-2-pms": "mews",
            "connection-2-accounting": "xero",
            "connection-2-directions": "pms_to_accounting",
        }
    )
    assert reason == "unknown-binding"


def test_in2_applies_empty_record_fails() -> None:
    """panel mi-applies · substep 8.2.1
    An authored record with zero rules is malformed, never a silent fallback
    to label-only behavior (that default is for pages with NO record)."""
    with pytest.raises(ApplicabilityValidationError) as exc:
        validate_applies_to([], CATALOG, PLATFORMS)
    assert exc.value.reason == "empty-record"


def test_in2_applies_empty_value_fails() -> None:
    """panel mi-applies · substep 8.2.1
    An empty field value is a loud failure, never an implicit any."""
    assert _reason({"level": "software", "product": "   "}) == "empty-value"


def test_in2_applies_ambiguous_legacy_compound_fails() -> None:
    """panel mi-applies · substep 8.2.1
    A legacy compound alias expanding to several products cannot sit in one
    product field — ambiguity is a named failure, never a pick."""
    toast = Product(id="toast", label="Toast", role="pos", aliases=(), connection_types=())
    mews = Product(id="mews", label="Mews", role="pms", aliases=(), connection_types=())
    catalog = ProductCatalog(
        products={"toast": toast, "mews": mews},
        connection_types={"pos-pms": frozenset({"pos", "pms"})},
        legacy_aliases={"toast-mews": ("toast", "mews")},
        launch_allowlist={},
        alias_to_id={},
        connection_directions={"pos-pms": ("pos_to_pms", "pms_to_pos")},
    )
    with pytest.raises(ApplicabilityValidationError) as exc:
        validate_rule({"level": "software", "product": "toast-mews"}, catalog, PLATFORMS)
    assert exc.value.reason == "ambiguous-product"
