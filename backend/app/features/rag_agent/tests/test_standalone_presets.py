"""Substep 8.4.1 (panel mi-presets): backend-validated standalone test presets.

The standalone/test environment (§D.8) picks a pretend customer setup from a fixed list and Obi
treats it exactly like a real one — SAME gate, SAME eligibility. Each preset expresses only a
verified-context shape (company_id + the three §D.13 slots); validation runs the preset through
the ONE real gate (`build_auth_context`, substep 8.1.3), so a preset can never express a context
the backend would refuse. The product catalog is the real committed
`knowledge-base/config/product_catalog.json`, so these tests pin the shipped launch allowlist
(Toast as POS, Mews as PMS) exactly as `test_mi_gate_slots.py` does."""

from __future__ import annotations

import pytest

from app.features.rag_agent.application.auth_context import (
    InvalidSlotValueError,
    SlotNotOnAllowlistError,
)
from app.features.rag_agent.application.standalone_presets import (
    PresetSlots,
    StandalonePreset,
    load_standalone_presets,
    standalone_registry,
    validate_preset,
)
from app.platform.config.product_catalog import load_product_catalog

# The four §D.2 flow directions the presets must cover, plus the three-system workflow (O10).
_EXPECTED_FLOW_TYPES = {
    "pos_to_pms",
    "pms_to_pos",
    "pms_to_accounting",
    "pos_to_accounting",
    "three_system",
}


def _catalog():
    return load_product_catalog()


def test_widget_every_shipped_preset_passes_the_same_gate_as_a_real_note():
    """panel mi-presets · substep 8.4.1
    Each preset passes the same gate validation (`build_auth_context`) as a real note — none is a
    context the backend would refuse — and the validated context carries the preset's slots."""
    catalog = _catalog()
    registry = standalone_registry(catalog=catalog)

    presets = load_standalone_presets()
    assert len(presets) == 5

    for preset in presets:
        context = validate_preset(preset, registry, catalog=catalog)
        assert context.company_id == preset.company_id
        assert context.slot_pos == preset.slots.pos
        assert context.slot_pms == preset.slots.pms
        assert context.slot_accounting == preset.slots.accounting


def test_widget_presets_cover_the_four_flow_types_plus_the_three_system_workflow():
    """panel mi-presets · substep 8.4.1
    The shipped list covers each of the four flow types plus the Toast/Mews/QuickBooks
    three-system workflow (§D.8 / §D.9 example 4)."""
    presets = load_standalone_presets()
    assert {p.flow_type for p in presets} == _EXPECTED_FLOW_TYPES

    three = next(p for p in presets if p.flow_type == "three_system")
    assert three.slots.pos == "toast"
    assert three.slots.pms == "mews"
    assert three.slots.accounting == "quickbooks-online"


def test_sec_a_preset_cannot_express_an_out_of_allowlist_context():
    """panel mi-presets · substep 8.4.1
    A preset holding a real catalog product outside the launch allowlist (Opera Cloud as PMS) is
    refused by the same gate — exactly as a real note would be — so it can never be saved."""
    catalog = _catalog()
    registry = standalone_registry(catalog=catalog)

    refused = StandalonePreset(
        id="bad-allowlist",
        label="Opera Cloud (not on the launch allowlist)",
        flow_type="pms_to_accounting",
        company_id="preset-bad",
        slots=PresetSlots(pos=None, pms="opera-cloud", accounting="xero"),
    )
    with pytest.raises(SlotNotOnAllowlistError):
        validate_preset(refused, registry, catalog=catalog)


def test_sec_a_preset_cannot_express_a_role_mismatched_context():
    """panel mi-presets · substep 8.4.1
    A preset putting a product in the wrong slot (Mews — a PMS — in the POS slot) is refused by
    the same role check the gate runs for a real note."""
    catalog = _catalog()
    registry = standalone_registry(catalog=catalog)

    refused = StandalonePreset(
        id="bad-role",
        label="Mews in the POS slot",
        flow_type="pos_to_pms",
        company_id="preset-bad-role",
        slots=PresetSlots(pos="mews", pms=None, accounting=None),
    )
    with pytest.raises(InvalidSlotValueError):
        validate_preset(refused, registry, catalog=catalog)
