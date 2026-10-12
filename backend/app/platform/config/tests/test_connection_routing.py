"""panel mi-route · substep 9.1.1 — the catalog resolves a directed connection.

Option A (ADR-0020, D4/D7): every chat is one directed source→target connection
and the catalog turns that pair into exactly four ordered Confluence label boxes —
``obi-general``, ``{source.slug}-general``, ``{target.slug}-general``,
``{source.slug}-to-{target.kind}`` (kind = the target product's role). ``resolve_system``
matches a name/slug/alias case-insensitively; an unknown source OR target yields
``[obi-general]`` alone, never a wildcard. Label-form validation accepts only the three
routing forms with a catalog slug. No network, no database — the real committed catalog.

NOTE on the worked examples: plan §"The routing rule" lists five rows, two of which use
illustrative systems that are deliberately NOT in the committed catalog (``Lightspeed``)
or use a short illustrative slug (``quickbooks``). Per plan line "Lightspeed and Opera
Cloud are example systems. Build the real catalog from the labels that exist in
Confluence.", these are mapped to the committed canonical ids (``opera-cloud``,
``quickbooks-online``); the slug in a box is always the canonical catalog id. The
illustrative non-catalog ``Lightspeed`` row is proved as the unknown-source fallback below.
"""

from __future__ import annotations

import pytest

from app.platform.config.product_catalog import (
    GENERAL_LABEL,
    load_product_catalog,
)

# The real committed catalog: deterministic, read once, no network.
CATALOG = load_product_catalog()


# ---------------------------------------------------------------- the five examples —
# each directed connection resolves to EXACTLY its four ordered boxes (plan routing rule).

_FIVE_EXAMPLES = [
    # Toast → Mews (POS → PMS)
    ("toast", "mews", ["obi-general", "toast-general", "mews-general", "toast-to-pms"]),
    # Toast → Opera Cloud (POS → PMS): stands in for the illustrative Lightspeed → Opera
    # Cloud row, exercising the hyphenated committed slug opera-cloud.
    (
        "toast",
        "opera-cloud",
        ["obi-general", "toast-general", "opera-cloud-general", "toast-to-pms"],
    ),
    # Mews → Toast (PMS → POS): direction is primary — mews-to-pos, not toast-to-pms.
    ("mews", "toast", ["obi-general", "mews-general", "toast-general", "mews-to-pos"]),
    # Mews → QuickBooks Online (PMS → ACCOUNTING)
    (
        "mews",
        "quickbooks-online",
        ["obi-general", "mews-general", "quickbooks-online-general", "mews-to-accounting"],
    ),
    # Toast → QuickBooks Online (POS → ACCOUNTING): accounting is a first-class target (D5).
    (
        "toast",
        "quickbooks-online",
        ["obi-general", "toast-general", "quickbooks-online-general", "toast-to-accounting"],
    ),
]


@pytest.mark.parametrize(("source", "target", "expected"), _FIVE_EXAMPLES)
def test_rt1_build_labels_five_examples_resolve_to_four_ordered_boxes(
    source: str, target: str, expected: list[str]
) -> None:
    """panel mi-route · substep 9.1.1
    The five example connections each resolve to exactly their four ordered boxes."""
    assert CATALOG.build_labels(source, target) == expected


def test_rt1_build_labels_direction_box_uses_target_kind_not_product() -> None:
    """panel mi-route · substep 9.1.1
    The fourth box is {source.slug}-to-{target.kind} — the target's catalog role
    (accounting), never the target product id (quickbooks-online)."""
    labels = CATALOG.build_labels("mews", "quickbooks-online")
    assert labels[3] == "mews-to-accounting"


# ---------------------------------------------------------------- unknown fallback —
# an unknown source OR target yields [obi-general] alone, never a wildcard.


def test_rt1_build_labels_unknown_source_yields_obi_general_only() -> None:
    """panel mi-route · substep 9.1.1
    The illustrative Lightspeed (not in the committed catalog) as source yields
    [obi-general] alone — never a wildcard, never a lightspeed box."""
    assert CATALOG.build_labels("Lightspeed", "opera-cloud") == [GENERAL_LABEL]


def test_rt1_build_labels_unknown_target_yields_obi_general_only() -> None:
    """panel mi-route · substep 9.1.1
    An unknown target yields [obi-general] alone — never a wildcard."""
    assert CATALOG.build_labels("toast", "nonesuch") == [GENERAL_LABEL]


# ---------------------------------------------------------------- resolve_system —
# matches name/slug/alias case-insensitively; an unmatched value is a clear miss.


def test_rt1_resolve_system_matches_canonical_id_case_insensitively() -> None:
    """panel mi-route · substep 9.1.1
    resolve_system matches the canonical id ignoring case."""
    product = CATALOG.resolve_system("TOAST")
    assert product is not None and product.id == "toast"


def test_rt1_resolve_system_matches_alias_and_display_name() -> None:
    """panel mi-route · substep 9.1.1
    resolve_system matches a per-product alias (operacloud) and the display name
    with spacing (Opera Cloud), both to the canonical id opera-cloud."""
    by_alias = CATALOG.resolve_system("OperaCloud")
    by_name = CATALOG.resolve_system("  opera cloud ")
    assert by_alias is not None and by_alias.id == "opera-cloud"
    assert by_name is not None and by_name.id == "opera-cloud"


def test_rt1_resolve_system_unknown_is_a_clear_miss() -> None:
    """panel mi-route · substep 9.1.1
    An unmatched value resolves to None — a clear miss, never a fuzzy match."""
    assert CATALOG.resolve_system("lightspeed") is None


# ---------------------------------------------------------------- label-form validation —
# accepts obi-general / {slug}-general / {slug}-to-(pos|pms|accounting); rejects the rest.


@pytest.mark.parametrize(
    "label",
    [
        "obi-general",
        "toast-general",
        "opera-cloud-general",
        "toast-to-pms",
        "mews-to-pos",
        "mews-to-accounting",
        "toast-to-accounting",
    ],
)
def test_rt1_is_valid_label_accepts_the_valid_forms(label: str) -> None:
    """panel mi-route · substep 9.1.1
    Label-form validation accepts obi-general, {slug}-general and
    {slug}-to-(pos|pms|accounting) with a catalog slug."""
    assert CATALOG.is_valid_label(label) is True


@pytest.mark.parametrize(
    "label",
    [
        "toast-to-pmss",  # kind is not one of pos/pms/accounting
        "toast-to-hotel",  # kind is not a real role
        "lightspeed-general",  # slug is not a catalog id
        "lightspeed-to-pms",  # slug is not a catalog id
        "general",  # not the obi-general form
        "toast",  # bare slug is not a label
    ],
)
def test_rt1_is_valid_label_rejects_malformed(label: str) -> None:
    """panel mi-route · substep 9.1.1
    A malformed label (toast-to-pmss, toast-to-hotel, an unknown slug) is rejected."""
    assert CATALOG.is_valid_label(label) is False


def test_rt1_build_labels_only_emits_valid_labels() -> None:
    """panel mi-route · substep 9.1.1
    Every box build_labels emits for a known connection passes label-form validation."""
    labels = CATALOG.build_labels("toast", "quickbooks-online")
    assert all(CATALOG.is_valid_label(label) for label in labels)
