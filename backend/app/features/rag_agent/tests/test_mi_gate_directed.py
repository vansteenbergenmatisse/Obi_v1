"""Substep 9.3.1 (panels mi-gate / mi-contract): `build_auth_context` accepts the directed
source → target connection form (Option A, ADR-0020) and refuses an unknown source or target with
a 400 BEFORE any search.

The directed form routes on a `source_system → target_system` + `business_id` triple, not the
three membership slots. For it the gate runs only checks 1-2 (shape + catalog membership, via the
SAME lenient `resolve_system` chat-start uses) and check 4 (vend rights — may this issuer vend both
systems); the slot role check (3) and the launch allowlist (5) lapse (ADR-0020 D4/D5). An unknown
source or target fails closed as the 400-before-search family; a system the issuer may not vend is
the 401 family. Company isolation is carried as `company_id = business_id`.

Synthetic registry like test_mi_gate_slots.py; the real committed product catalog is the gate's
default, so these tests pin the shipped catalog ids (toast=pos, mews=pms, xero=accounting)."""

from __future__ import annotations

import json

import pytest

from app.features.rag_agent.application.auth_context import (
    IntegrationNotAllowedError,
    InvalidSlotValueError,
    TargetNotEnabledError,
    UnknownIntegrationError,
    build_auth_context,
)
from app.features.rag_agent.server.token_verifier import VerifiedClaims
from app.platform.config.platforms import load_platform_registry
from app.platform.config.product_catalog import (
    DEFAULT_PRODUCT_CATALOG_PATH,
    load_product_catalog,
)

_RECOGNIZED = frozenset({"obi-general-test", "obi-mews-test", "obi-toast-test"})
_HUB_ISS = "https://hub.example.com"


def _all_enabled_catalog(tmp_path):
    """The committed catalog with `enabled_targets` removed → absent ⇒ ALL products enabled.
    These role/vend tests pass it so they isolate the directed gate's shape/membership/vend
    behavior from the Task 5 enablement axis (which has its own tests below); otherwise the
    shipped `enabled_targets` (mews/toast/opera-cloud) would entangle an accounting target."""
    data = json.loads(DEFAULT_PRODUCT_CATALOG_PATH.read_text())
    data.pop("enabled_targets", None)
    p = tmp_path / "catalog_all_enabled.json"
    p.write_text(json.dumps(data))
    return load_product_catalog(p)


def _registry(tmp_path, allowed_integrations):
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


def _directed(*, source, target, business_id="B-3075"):
    return VerifiedClaims(
        issuer=_HUB_ISS,
        subject="u1",
        company_id=None,
        company_name=None,
        integration=None,
        source_system=source,
        target_system=target,
        business_id=business_id,
    )


def test_rt1_directed_form_accepted(tmp_path):
    """panel mi-gate · substep 9.3.1
    The gate accepts a directed toast → mews connection: it resolves both systems in the catalog,
    carries them as source/target slugs and keys the context on business_id as company_id."""
    reg = _registry(tmp_path, ["toast", "mews"])
    ctx = build_auth_context(_directed(source="toast", target="mews"), reg)
    assert ctx.source_slug == "toast"
    assert ctx.target_slug == "mews"
    assert ctx.company_id == "B-3075"
    assert ctx.token_subject is not None
    assert ctx.allowed_scopes == ()  # ADR-0021: scopes retired


def test_rt1_directed_unknown_source_is_400_before_search(tmp_path):
    """panel mi-gate · substep 9.3.1
    An unknown source system fails closed as UnknownIntegrationError — the 400-before-any-search
    family (§D.11), raised before any retrieval touches the database."""
    reg = _registry(tmp_path, ["toast", "mews"])
    with pytest.raises(UnknownIntegrationError):
        build_auth_context(_directed(source="wordpress", target="mews"), reg)
    assert issubclass(UnknownIntegrationError, InvalidSlotValueError)


def test_rt1_directed_unknown_target_is_400_before_search(tmp_path):
    """panel mi-gate · substep 9.3.1
    An unknown target system fails closed as UnknownIntegrationError (400 before any search),
    symmetric with an unknown source."""
    reg = _registry(tmp_path, ["toast", "mews"])
    with pytest.raises(UnknownIntegrationError):
        build_auth_context(_directed(source="toast", target="hotel-9000"), reg)


def test_rt1_directed_vend_rights_bind_both_systems(tmp_path):
    """panel mi-gate · substep 9.3.1
    Check 4 (vend rights): a hub trusted to vend only mews may not assert a toast → mews
    connection — IntegrationNotAllowedError (401), the same cross-issuer boundary as the slot
    form's vend check."""
    reg = _registry(tmp_path, ["mews"])
    with pytest.raises(IntegrationNotAllowedError):
        build_auth_context(_directed(source="toast", target="mews"), reg)


def test_rt1_directed_accounting_target_is_first_class(tmp_path):
    """panel mi-gate · substep 9.3.1
    ADR-0020 D5: accounting is a first-class target with no launch-ALLOWLIST gate — a
    mews → xero (PMS → accounting) connection is accepted when the issuer vends both. Uses an
    all-enabled catalog so this isolates the allowlist-lapse claim from the Task 5 enablement
    axis (the shipped catalog does not enable xero — see the enablement tests below)."""
    reg = _registry(tmp_path, ["mews", "xero"])
    ctx = build_auth_context(
        _directed(source="mews", target="xero"), reg, catalog=_all_enabled_catalog(tmp_path)
    )
    assert ctx.source_slug == "mews"
    assert ctx.target_slug == "xero"


# --- Task 5 (panel mi-gate): the target-enablement visibility gate (after vend rights) ---


def test_mi_gate_directed_refuses_disabled_target(tmp_path):
    """panel mi-gate · Task 5
    A verified, vendable directed connection whose TARGET product is not in the catalog's
    `enabled_targets` (the shipped catalog omits xero) is refused with TargetNotEnabledError —
    the 403 family that keeps Obi hidden for a not-yet-live integration. The source's enablement
    is irrelevant: only the target gates."""
    reg = _registry(tmp_path, ["mews", "xero"])  # issuer vends both → vend rights pass
    with pytest.raises(TargetNotEnabledError):
        build_auth_context(_directed(source="mews", target="xero"), reg)


def test_mi_gate_directed_allows_enabled_target(tmp_path):
    """panel mi-gate · Task 5
    A directed connection whose target IS enabled (mews, in the shipped `enabled_targets`) is
    accepted — the enablement gate never fires for a live target."""
    reg = _registry(tmp_path, ["toast", "mews"])
    ctx = build_auth_context(_directed(source="toast", target="mews"), reg)
    assert ctx.target_slug == "mews"


def test_mi_gate_directed_unknown_target_is_400_before_enablement(tmp_path):
    """panel mi-gate · Task 5 (precedence)
    An unknown target fails membership (UnknownIntegrationError, the 400-before-search family)
    BEFORE the enablement check ever runs — precedence: unknown → 400, not a 403."""
    reg = _registry(tmp_path, ["mews", "xero"])
    with pytest.raises(UnknownIntegrationError):
        build_auth_context(_directed(source="mews", target="not-a-real-system"), reg)


def test_mi_gate_directed_vend_violation_is_401_before_enablement(tmp_path):
    """panel mi-gate · Task 5 (precedence)
    A target the issuer may not vend is IntegrationNotAllowedError (401) — raised at check 4,
    BEFORE the enablement check placed after it. So a disabled-AND-unvendable target refuses as
    the 401 vend family, never the 403 enablement family: unknown → 400, vend → 401, not-enabled
    → 403, in that order."""
    reg = _registry(tmp_path, ["mews"])  # does NOT vend xero
    with pytest.raises(IntegrationNotAllowedError):
        build_auth_context(_directed(source="mews", target="xero"), reg)
    assert not issubclass(TargetNotEnabledError, IntegrationNotAllowedError)


def test_sec_body_can_never_carry_the_connection(tmp_path):
    """panel mi-gate · substep 9.3.1
    The request body never decides the connection (never-bend rules 2-3): the gate reads only the
    verified token (build_auth_context takes no body), and the chat body model forbids a
    source/target key outright, so a caller cannot smuggle one past the token."""
    from pydantic import ValidationError

    from app.features.rag_agent.server.router import ChatRequestBody

    with pytest.raises(ValidationError):
        ChatRequestBody(
            history=[{"role": "user", "content": "hi"}],
            source_system="toast",  # type: ignore[call-arg]
            target_system="mews",  # type: ignore[call-arg]
        )
