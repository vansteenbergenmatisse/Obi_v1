"""panel mi-catalog · substep 8.1.1 — The product catalog gets a loader.

The one product file (`knowledge-base/config/product_catalog.json`) is validated at startup
against the 8 rules in docs/Final_docs/5-integration-context/catalog.md §3, in the fail-fast
style of knowledge_scopes.py: a bad entry stops the backend before it can mis-scope anyone,
each failure naming the offending entry. A valid catalog exposes product lookups, alias
resolution (operacloud → opera-cloud) and the launch allowlist; an unmatched value fails
closed (empty resolution, never a fallback).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.platform.config.product_catalog import (
    DEFAULT_PRODUCT_CATALOG_PATH,
    load_product_catalog,
)

_REAL_CATALOG: dict[str, Any] = json.loads(DEFAULT_PRODUCT_CATALOG_PATH.read_text())


def _write_catalog(tmp_path: Path, data: dict[str, Any]) -> Path:
    """A temp catalog file from a dict — never edits the real committed file."""
    path = tmp_path / "product_catalog.json"
    path.write_text(json.dumps(data))
    return path


def _write_platforms(tmp_path: Path, integration_keys: list[str]) -> Path:
    """A temp platforms.json carrying only the integrations map the cross-check reads."""
    path = tmp_path / "platforms.json"
    path.write_text(json.dumps({"integrations": {key: [] for key in integration_keys}}))
    return path


def _catalog(**overrides: Any) -> dict[str, Any]:
    """A deep copy of the real committed catalog with top-level overrides applied."""
    data: dict[str, Any] = json.loads(json.dumps(_REAL_CATALOG))
    data.update(overrides)
    return data


# --- the 8 validation rules of catalog.md §3, one red-first test each ---


def test_catalog_bad_slug_fails_and_names_it(tmp_path: Path) -> None:
    """panel mi-catalog · substep 8.1.1
    Rule 1: an id or alias that is not a lowercase slug ("OperaCloud") is rejected at
    startup, never silently lowercased, and the message names the entry."""
    data = _catalog()
    data["products"]["opera-cloud"]["aliases"] = ["OperaCloud"]

    with pytest.raises(ValueError, match="OperaCloud"):
        load_product_catalog(_write_catalog(tmp_path, data))


def test_catalog_duplicate_alias_fails_and_names_it(tmp_path: Path) -> None:
    """panel mi-catalog · substep 8.1.1
    Rule 2: an alias listed under two products (or colliding with a canonical id) fails
    startup and the message names the repeated alias."""
    data = _catalog()
    data["products"]["mews"]["aliases"] = ["operacloud"]  # already opera-cloud's alias

    with pytest.raises(ValueError, match="operacloud"):
        load_product_catalog(_write_catalog(tmp_path, data))


def test_catalog_role_outside_the_three_fails(tmp_path: Path) -> None:
    """panel mi-catalog · substep 8.1.1
    Rule 3: a role outside pos | pms | accounting ("crm") fails startup. The entry is
    otherwise inert (no connection types, not on the allowlist) so only rule 3 can
    catch it — a derived check may not stand in for the role check."""
    data = _catalog()
    data["products"]["salesforce"] = {
        "label": "Salesforce",
        "role": "crm",
        "aliases": [],
        "connection_types": [],
    }

    with pytest.raises(ValueError, match="crm"):
        load_product_catalog(_write_catalog(tmp_path, data))


def test_catalog_unknown_connection_type_fails(tmp_path: Path) -> None:
    """panel mi-catalog · substep 8.1.1
    Rule 4: a product naming a connection type that is not a key of the top-level
    connection_types ("pos-crm") fails startup."""
    data = _catalog()
    data["products"]["toast"]["connection_types"] = ["pos-pms", "pos-crm"]

    with pytest.raises(ValueError, match="pos-crm"):
        load_product_catalog(_write_catalog(tmp_path, data))


def test_catalog_role_not_in_connection_type_fails(tmp_path: Path) -> None:
    """panel mi-catalog · substep 8.1.1
    Rule 4 (second half): a product listing a connection type whose roles do not include
    the product's own role fails startup."""
    data = _catalog()
    # xero is accounting; pos-pms joins only pos + pms.
    data["products"]["xero"]["connection_types"] = ["pos-pms"]

    with pytest.raises(ValueError, match="pos-pms"):
        load_product_catalog(_write_catalog(tmp_path, data))


def test_catalog_bad_legacy_alias_expansion_fails(tmp_path: Path) -> None:
    """panel mi-catalog · substep 8.1.1
    Rule 5: a legacy_aliases value naming a non-existent canonical id fails startup."""
    data = _catalog(legacy_aliases={"toast-opera": ["toast", "no-such-product"]})

    with pytest.raises(ValueError, match="no-such-product"):
        load_product_catalog(_write_catalog(tmp_path, data))


def test_catalog_legacy_alias_two_products_one_role_fails(tmp_path: Path) -> None:
    """panel mi-catalog · substep 8.1.1
    Rule 5 (second half): a legacy expansion putting two products of the same role in one
    slot (mews + opera-cloud, both pms) fails startup."""
    data = _catalog(legacy_aliases={"mews-opera": ["mews", "opera-cloud"]})

    with pytest.raises(ValueError, match="mews-opera"):
        load_product_catalog(_write_catalog(tmp_path, data))


def test_catalog_allowlist_role_mismatch_fails(tmp_path: Path) -> None:
    """panel mi-catalog · substep 8.1.1
    Rule 6: a launch_allowlist entry whose role does not match the list it sits in
    (mews under pos) fails startup."""
    data = _catalog(launch_allowlist={"pos": ["toast", "mews"], "pms": ["mews"]})

    with pytest.raises(ValueError, match="mews"):
        load_product_catalog(_write_catalog(tmp_path, data))


@pytest.mark.parametrize("reserved", ["classified", "general", "obi-general-test", "obi-x"])
def test_catalog_reserved_name_fails(tmp_path: Path, reserved: str) -> None:
    """panel mi-catalog · substep 8.1.1
    Rule 7: the reserved names (classified, general, obi-general-test, any obi-*) never
    appear in the file — as an alias they stop startup."""
    data = _catalog()
    data["products"]["toast"]["aliases"] = [reserved]

    with pytest.raises(ValueError, match=reserved):
        load_product_catalog(_write_catalog(tmp_path, data))


def test_catalog_platforms_key_without_catalog_id_fails(tmp_path: Path) -> None:
    """panel mi-catalog · substep 8.1.1
    Rule 8: a platforms.json integrations key that resolves to no catalog id or alias
    ("lightspeed") fails startup — the two files may never disagree."""
    catalog_path = _write_catalog(tmp_path, _catalog())
    platforms_path = _write_platforms(tmp_path, ["mews", "toast", "lightspeed"])

    with pytest.raises(ValueError, match="lightspeed"):
        load_product_catalog(catalog_path, platforms_path=platforms_path)


# --- the valid catalog: lookups, alias resolution, allowlist, fail-closed ---


def test_catalog_real_committed_file_loads() -> None:
    """panel mi-catalog · substep 8.1.1
    The real committed catalog passes all 8 rules (incl. the cross-check against the real
    platforms.json) and exposes product lookups and the launch allowlist."""
    catalog = load_product_catalog()

    assert set(catalog.products) == {"toast", "mews", "opera-cloud", "quickbooks-online", "xero"}
    assert catalog.products["toast"].role == "pos"
    assert catalog.products["opera-cloud"].role == "pms"
    assert catalog.launch_allowlist == {"pos": frozenset({"toast"}), "pms": frozenset({"mews"})}


def test_catalog_alias_operacloud_resolves_to_opera_cloud() -> None:
    """panel mi-catalog · substep 8.1.1
    operacloud resolves to opera-cloud: alias resolution is one-to-one, canonical ids
    resolve to themselves."""
    catalog = load_product_catalog()

    assert catalog.resolve("operacloud") == ("opera-cloud",)
    assert catalog.resolve("opera-cloud") == ("opera-cloud",)


def test_catalog_unknown_value_fails_closed() -> None:
    """panel mi-catalog · substep 8.1.1
    An unmatched value resolves to nothing — fail closed, never a fallback or a fuzzy
    match (the gate turns this into a 400 before any search)."""
    catalog = load_product_catalog()

    assert catalog.resolve("lightspeed") == ()
    assert catalog.resolve("Toast") == ()  # no silent lowercasing at resolve time either


def test_catalog_every_platforms_integration_key_resolves() -> None:
    """panel mi-catalog · substep 8.1.1
    Every key of the real platforms.json integrations map resolves to a catalog id."""
    from app.platform.config.platforms import DEFAULT_PLATFORMS_PATH

    catalog = load_product_catalog()
    integrations = json.loads(DEFAULT_PLATFORMS_PATH.read_text())["integrations"]

    for key in integrations:
        assert catalog.resolve(key), f"integration key {key!r} resolves to no catalog id"
