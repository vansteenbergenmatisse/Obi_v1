"""Substep 8.1.3 (panel mi-gate): `build_auth_context` accepts the three-slot context.

The five checks of docs/Final_docs/5-integration-context/decision-memo.md §4, in order —
shape → membership (catalog) → role agreement → vend rights → allowlist — each with its own
red-first test, plus the owner-decided edge cases: an empty slot never refuses, a filled
Accounting slot outside support is inert for eligibility (O4), and a legacy single-integration
note behaves exactly as one filled slot.

The product catalog is the real committed `knowledge-base/config/product_catalog.json` (the
gate's default), so these tests also pin the shipped launch allowlist: Toast as POS, Mews as
PMS. Registries are synthetic temp files, like test_auth_context.py."""

from __future__ import annotations

import json

import pytest

from app.features.rag_agent.application.auth_context import (
    IntegrationNotAllowedError,
    InvalidSlotValueError,
    SlotNotOnAllowlistError,
    UnknownIntegrationError,
    build_auth_context,
)
from app.features.rag_agent.server.token_verifier import ContextSlots, VerifiedClaims
from app.platform.config.platforms import load_platform_registry

_RECOGNIZED = frozenset({"obi-general-test", "obi-mews-test", "obi-toast-test"})
_HUB_ISS = "https://hub.example.com"


def _registry(tmp_path, allowed_integrations):
    """One active hub-style platform whose vend set is the test's choice. The integrations map
    carries every value a test may vend; opera-cloud and xero map to no product scope (no scope
    tag exists for them — O9 open), which is exactly the committed situation."""
    p = tmp_path / "platforms.json"
    p.write_text(
        json.dumps(
            {
                "platforms": {
                    "hub": {
                        "issuer": _HUB_ISS,
                        "jwks_url": f"{_HUB_ISS}/j",
                        "domains": [],
                        "lifetime_minutes": 60,
                        "algs": ["RS256"],
                        "active": True,
                        "allowed_integrations": allowed_integrations,
                    }
                },
                "integrations": {
                    "mews": [],
                    "toast": [],
                    "opera-cloud": [],
                    "xero": [],
                },
            }
        )
    )
    return load_platform_registry(p, _RECOGNIZED, allow_empty=False)


def _slot_claims(*, pos=None, pms=None, accounting=None, company_id="c1"):
    return VerifiedClaims(
        issuer=_HUB_ISS,
        subject="u1",
        company_id=company_id,
        company_name=None,
        integration=None,
        slots=ContextSlots(pos=pos, pms=pms, accounting=accounting),
    )


def _legacy_claims(integration):
    return VerifiedClaims(
        issuer=_HUB_ISS,
        subject="u1",
        company_id="c1",
        company_name="Co",
        integration=integration,
    )


# --- check 1 · shape ----------------------------------------------------------------------------


def test_rt1_slot_shape_rejects_a_malformed_value(tmp_path):
    """panel mi-gate · substep 8.1.3
    Check 1 (shape): a filled slot value that is not a short lowercase slug is refused as
    invalid (the 400-before-search family) — BEFORE any catalog lookup, so the failure is the
    plain shape error, not membership's UnknownIntegrationError subclass."""
    reg = _registry(tmp_path, ["mews"])
    with pytest.raises(InvalidSlotValueError) as excinfo:
        build_auth_context(_slot_claims(pms="Mews Hotel!"), reg)
    # shape fired first: membership (check 2) never saw the value
    assert not isinstance(excinfo.value, UnknownIntegrationError)


def test_rt1_filled_slots_without_company_id_are_invalid(tmp_path):
    """panel mi-gate · substep 8.1.3
    Check 1 (shape): company_id must be present when a slot is filled (decision-memo §4 rule 1)
    — a filled slot with no company identity is refused in the 400 family."""
    reg = _registry(tmp_path, ["mews"])
    with pytest.raises(InvalidSlotValueError):
        build_auth_context(_slot_claims(pms="mews", company_id=None), reg)


# --- check 2 · membership against the catalog ---------------------------------------------------


def test_rt1_unknown_slot_value_fails_closed(tmp_path):
    """panel mi-gate · substep 8.1.3
    Check 2 (membership): a well-shaped slot value that resolves to no catalog product fails
    closed as UnknownIntegrationError — the 400-before-any-search family (§D.11), raised even
    though the platform's vend set could never have admitted it (membership runs before vend)."""
    reg = _registry(tmp_path, ["mews"])
    with pytest.raises(UnknownIntegrationError):
        build_auth_context(_slot_claims(pos="wordpress"), reg)
    # the membership failure is part of the 400 family the router maps before any search
    assert issubclass(UnknownIntegrationError, InvalidSlotValueError)


# --- check 3 · role agreement -------------------------------------------------------------------


def test_rt1_role_mismatch_toast_in_pms_slot_is_refused(tmp_path):
    """panel mi-gate · substep 8.1.3
    Check 3 (role agreement): toast is a real catalog product but its role is pos — toast in
    the PMS slot is never valid (decision-memo §4 rule 2) and is refused in the 400 family."""
    reg = _registry(tmp_path, ["mews", "toast"])
    with pytest.raises(InvalidSlotValueError):
        build_auth_context(_slot_claims(pms="toast"), reg)


# --- check 4 · vend rights ----------------------------------------------------------------------


def test_rt1_vend_rights_bind_slots_to_the_issuing_platform(tmp_path):
    """panel mi-gate · substep 8.1.3
    Check 4 (vend rights, CIP-A1 generalized): a platform trusted to vend only mews may not
    fill the POS slot with toast — IntegrationNotAllowedError (401), exactly the legacy
    cross-issuer posture."""
    reg = _registry(tmp_path, ["mews"])
    with pytest.raises(IntegrationNotAllowedError):
        build_auth_context(_slot_claims(pos="toast", pms="mews"), reg)


# --- check 5 · launch allowlist -----------------------------------------------------------------


def test_rt1_pms_opera_cloud_outside_allowlist_is_refused(tmp_path):
    """panel mi-gate · substep 8.1.3
    Check 5 (allowlist): PMS = opera-cloud is a real, vendable catalog product that is NOT on
    the launch allowlist (Toast as POS, Mews as PMS) — the session is refused. Raised only
    AFTER membership/role/vend passed, proving the check order."""
    reg = _registry(tmp_path, ["mews", "opera-cloud"])
    with pytest.raises(SlotNotOnAllowlistError):
        build_auth_context(_slot_claims(pms="opera-cloud"), reg)


def test_rt1_empty_pos_with_mews_pms_serves(tmp_path):
    """panel mi-gate · substep 8.1.3
    An empty slot never refuses: a Mews hotel with no POS gets a scoped context — general +
    mews scopes, PMS slot filled with the canonical id, the other slots empty."""
    reg = _registry(tmp_path, ["mews"])
    ctx = build_auth_context(_slot_claims(pms="mews"), reg)
    assert ctx.allowed_scopes == ()  # ADR-routing-labels-sole-content-axis: scopes retired
    assert ctx.slot_pms == "mews"
    assert ctx.slot_pos is None and ctx.slot_accounting is None
    assert ctx.company_id == "c1"


def test_rt1_accounting_outside_support_is_inert_never_refuses(tmp_path):
    """panel mi-gate · substep 8.1.3
    O4 (closed, decision round 2): the allowlist gates POS/PMS only — a filled Accounting slot
    outside support (xero, no scope tag exists) never refuses; it is inert for eligibility.
    The context serves with the supported slots' scopes and carries the accounting slot."""
    reg = _registry(tmp_path, ["mews", "xero"])
    ctx = build_auth_context(_slot_claims(pms="mews", accounting="xero"), reg)
    assert ctx.allowed_scopes == ()  # ADR-routing-labels-sole-content-axis: scopes retired
    assert ctx.slot_accounting == "xero"
    assert ctx.slot_pms == "mews"


def test_rt1_all_empty_slots_are_general_only(tmp_path):
    """panel mi-gate · substep 8.1.3
    A structured note with every slot empty never refuses — it degrades to general-only,
    exactly like a legacy note with no business values."""
    reg = _registry(tmp_path, ["mews"])
    ctx = build_auth_context(_slot_claims(), reg)
    assert ctx.allowed_scopes == ()  # ADR-routing-labels-sole-content-axis: scopes retired
    assert ctx.slot_pos is None and ctx.slot_pms is None and ctx.slot_accounting is None


# --- legacy note = one filled slot --------------------------------------------------------------


def test_rt1_legacy_note_reads_as_one_filled_slot(tmp_path):
    """panel mi-gate · substep 8.1.3
    A legacy single-integration note behaves exactly as one filled slot: integration="mews"
    fills the PMS slot (the product's catalog role) and yields the same scopes and slots as
    the structured one-slot note."""
    reg = _registry(tmp_path, ["mews"])
    legacy = build_auth_context(_legacy_claims("mews"), reg)
    structured = build_auth_context(_slot_claims(pms="mews"), reg)
    assert legacy.allowed_scopes == structured.allowed_scopes
    assert legacy.slot_pms == structured.slot_pms == "mews"
    assert legacy.slot_pos is None and legacy.slot_accounting is None
    assert legacy.integration == "mews"  # the raw legacy claim is still carried for audit


def test_rt1_legacy_alias_resolves_via_the_catalog_then_hits_the_allowlist(tmp_path):
    """panel mi-gate · substep 8.1.3
    Legacy alias values resolve through the catalog before validation (§D.11): integration
    "operacloud" resolves to canonical opera-cloud, passes membership/role/vend — and is then
    refused by the allowlist as a filled PMS slot outside it. The exception type proves the
    alias carried the value all the way to check 5."""
    reg = _registry(tmp_path, ["mews", "opera-cloud"])
    with pytest.raises(SlotNotOnAllowlistError):
        build_auth_context(_legacy_claims("operacloud"), reg)
