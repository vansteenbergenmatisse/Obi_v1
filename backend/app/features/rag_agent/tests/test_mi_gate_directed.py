"""Substep 9.3.1 + ADR-0023 (panels mi-gate / mi-contract): `build_auth_context` accepts the
directed source → target connection form (Option A, ADR-0020).

ADR-0023 (owner, 2026-10-20): only the SOURCE system decides eligibility. A source can have
hundreds of targets, so the target is assumed supported and never checked — an unknown target is
carried as `target_slug=None`. The source must resolve in the catalog, be vendable by the issuer
(401 otherwise) and be in `enabled_sources` (403 otherwise; an unknown source is also 403, so Obi
hides rather than errors). Company isolation is carried as `company_id = business_id`.

Synthetic registry like test_mi_gate_slots.py; the real committed product catalog is the gate's
default, so these tests pin the shipped catalog (enabled_sources = mews, toast, opera-cloud)."""

from __future__ import annotations

import json

import pytest

from app.features.rag_agent.application.auth_context import (
    IntegrationNotAllowedError,
    SourceNotEnabledError,
    build_auth_context,
)
from app.features.rag_agent.server.token_verifier import VerifiedClaims
from app.platform.config.platforms import load_platform_registry

_RECOGNIZED = frozenset({"obi-general-test", "obi-mews-test", "obi-toast-test"})
_HUB_ISS = "https://hub.example.com"


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


def test_rt1_directed_unknown_source_is_hidden_before_search(tmp_path):
    """panel mi-gate · ADR-0023 (source-only eligibility)
    A source system the catalog does not know is not a source we support, so Obi is hidden for it:
    SourceNotEnabledError (the 403 hide family), raised before any retrieval touches the database."""
    reg = _registry(tmp_path, ["toast", "mews"])
    with pytest.raises(SourceNotEnabledError):
        build_auth_context(_directed(source="wordpress", target="mews"), reg)


def test_rt1_directed_unknown_target_is_accepted_with_no_target_slug(tmp_path):
    """panel mi-gate · ADR-0023 (source-only eligibility)
    A source can have hundreds of targets, so the target is never checked: an unknown target
    (NetSuite is not in the catalog) is accepted and carried as target_slug None, never a
    fabricated system. The source still routes."""
    reg = _registry(tmp_path, ["toast", "mews"])
    ctx = build_auth_context(_directed(source="toast", target="NetSuite"), reg)
    assert ctx.source_slug == "toast"
    assert ctx.target_slug is None
    assert ctx.company_id == "B-3075"


def test_rt1_directed_source_resolves_by_display_name(tmp_path):
    """panel mi-gate · ADR-0023
    Base sends display names ("Opera Cloud"), not slugs; the source resolves through the same
    lenient resolver chat-start uses."""
    reg = _registry(tmp_path, ["opera-cloud"])
    ctx = build_auth_context(_directed(source="Opera Cloud", target="PEP PMS"), reg)
    assert ctx.source_slug == "opera-cloud"
    assert ctx.target_slug is None


def test_rt1_directed_vend_rights_bind_the_source(tmp_path):
    """panel mi-gate · substep 9.3.1 + ADR-0023
    Check 4 (vend rights) still binds the SOURCE: a hub trusted to vend only mews may not assert
    toast as its source — IntegrationNotAllowedError (401), the cross-issuer boundary."""
    reg = _registry(tmp_path, ["mews"])
    with pytest.raises(IntegrationNotAllowedError):
        build_auth_context(_directed(source="toast", target="mews"), reg)


def test_rt1_directed_target_is_never_vend_checked(tmp_path):
    """panel mi-gate · ADR-0023
    The target is assumed supported: a known target the issuer does not vend (xero) is accepted
    and still carried as the target slug, so the four routing labels can use it."""
    reg = _registry(tmp_path, ["toast"])
    ctx = build_auth_context(_directed(source="toast", target="xero"), reg)
    assert ctx.source_slug == "toast"
    assert ctx.target_slug == "xero"


def test_rt1_directed_accounting_target_is_first_class(tmp_path):
    """panel mi-gate · substep 9.3.1
    ADR-0020 D5: accounting is a first-class target — a mews → xero (PMS → accounting) connection
    is accepted, and since ADR-0023 the target's own enablement is never checked."""
    reg = _registry(tmp_path, ["mews", "xero"])
    ctx = build_auth_context(_directed(source="mews", target="xero"), reg)
    assert ctx.source_slug == "mews"
    assert ctx.target_slug == "xero"


# --- ADR-0023 (panel mi-gate): the source-enablement visibility gate (after vend rights) ---


def test_mi_gate_directed_refuses_disabled_source(tmp_path):
    """panel mi-gate · ADR-0023
    A verified, vendable directed connection whose SOURCE product is not in the catalog's
    `enabled_sources` (the shipped catalog omits xero) is refused with SourceNotEnabledError — the
    403 family that keeps Obi hidden. Only the source gates."""
    reg = _registry(tmp_path, ["mews", "xero"])  # issuer vends both → vend rights pass
    with pytest.raises(SourceNotEnabledError):
        build_auth_context(_directed(source="xero", target="mews"), reg)


def test_mi_gate_directed_allows_every_enabled_source(tmp_path):
    """panel mi-gate · ADR-0023
    Each shipped enabled source (mews, toast, opera-cloud) is accepted, whatever the target."""
    reg = _registry(tmp_path, ["mews", "toast", "opera-cloud"])
    for source in ("mews", "toast", "opera-cloud"):
        ctx = build_auth_context(_directed(source=source, target="NetSuite"), reg)
        assert ctx.source_slug == source


def test_mi_gate_directed_vend_violation_is_401_before_enablement(tmp_path):
    """panel mi-gate · ADR-0023 (precedence)
    A known source the issuer may not vend is IntegrationNotAllowedError (401) — raised at check 4,
    BEFORE the enablement check placed after it: vend → 401, then not-enabled → 403."""
    reg = _registry(tmp_path, ["mews"])  # does NOT vend xero
    with pytest.raises(IntegrationNotAllowedError):
        build_auth_context(_directed(source="xero", target="mews"), reg)
    assert not issubclass(SourceNotEnabledError, IntegrationNotAllowedError)


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
