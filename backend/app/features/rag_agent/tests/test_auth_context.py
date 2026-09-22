"""Task A2 (PLAN 11.1c): frozen AuthContext + integration->scope resolution.

Includes done-when 3a — two contexts that differ only by `company_id` resolve to identical
scopes (company_id is audit-only in v1, never a scope axis; this replaces the dropped mews-2
browser proof from the spec)."""

from __future__ import annotations

import json

import pytest

from app.features.rag_agent.application.auth_context import (
    InactivePlatformError,
    IntegrationNotAllowedError,
    UnknownIntegrationError,
    build_auth_context,
    general_only_context,
)
from app.features.rag_agent.server.token_verifier import VerifiedClaims
from app.platform.config.platforms import load_platform_registry

_RECOGNIZED = frozenset({"obi-general-test", "obi-mews-test", "obi-toast-test"})


def _build_registry(tmp_path, platforms, integrations, *, allow_empty=True):
    p = tmp_path / "platforms.json"
    p.write_text(json.dumps({"platforms": platforms, "integrations": integrations}))
    return load_platform_registry(p, _RECOGNIZED, allow_empty=allow_empty)


def _entry(issuer, *, active=True, allowed_integrations):
    return {
        "issuer": issuer,
        "jwks_url": "j",
        "domains": [],
        "lifetime_minutes": 60,
        "algs": ["RS256"],
        "active": active,
        "allowed_integrations": allowed_integrations,
    }


def _registry(tmp_path):
    # mews is the self-serving platform under test; `other` is a SECOND active platform that also
    # vends the mews integration, so the CIP-4 two-issuer identity tests (same `sub`, different
    # issuer) both resolve to a scoped context now that build_auth_context gates on the active
    # platform + its allowed_integrations (AUTH-1 / CIP-A1).
    return _build_registry(
        tmp_path,
        {
            "mews": _entry("https://app.mews.com", allowed_integrations=["mews"]),
            "other": _entry("https://other.example.com", allowed_integrations=["mews"]),
        },
        {"mews": ["obi-mews-test"]},
        allow_empty=False,
    )


def _claims(**over):
    base = dict(
        issuer="https://app.mews.com",
        subject="u1",
        company_id="c1",
        company_name="Hotel",
        integration="mews",
    )
    base.update(over)
    return VerifiedClaims(**base)


def test_builds_scoped_context(tmp_path):
    ctx = build_auth_context(_claims(), _registry(tmp_path))
    assert ctx.integration == "mews"
    assert ctx.allowed_scopes == ("obi-general-test", "obi-mews-test")
    assert ctx.principal is None  # v1: embedded users are principal-less
    assert ctx.allowed_sources == ("confluence:default",)
    # CIP-4: token_subject is issuer-namespaced (NUL-separated), not the bare `sub`
    assert ctx.token_subject == "https://app.mews.com\x00u1"
    assert ctx.company_id == "c1"


def test_company_id_only_difference_yields_identical_scopes(tmp_path):
    reg = _registry(tmp_path)
    a = build_auth_context(_claims(company_id="c1"), reg)
    b = build_auth_context(_claims(company_id="c2"), reg)
    assert a.allowed_scopes == b.allowed_scopes  # done-when 3a


def test_no_business_values_is_general_only(tmp_path):
    ctx = build_auth_context(
        _claims(company_id=None, company_name=None, integration=None), _registry(tmp_path)
    )
    assert ctx.allowed_scopes == ("obi-general-test",)
    assert ctx.integration is None
    # CIP-4: still token-identified, and issuer-namespaced
    assert ctx.token_subject == "https://app.mews.com\x00u1"


def test_unknown_integration_raises(tmp_path):
    with pytest.raises(UnknownIntegrationError):
        build_auth_context(_claims(integration="wordpress"), _registry(tmp_path))


# --- AUTH-1 / CIP-A2: an inactive platform is not served at the AuthContext boundary ------------


def test_inactive_platform_token_is_denied(tmp_path):
    """AUTH-1 / CIP-A2: a validly-verified token whose issuing platform is active=false must NOT
    receive scoped access — the gate consults the registry's ACTIVE view (platform_for), not the
    verify-only by_issuer view. An inactive platform should not be served at all."""
    reg = _build_registry(
        tmp_path,
        {
            "mews": _entry("https://app.mews.com", allowed_integrations=["mews"]),
            "toast": _entry(
                "https://pos.toasttab.com", active=False, allowed_integrations=["toast"]
            ),
        },
        {"mews": ["obi-mews-test"], "toast": ["obi-toast-test"]},
    )
    claims = VerifiedClaims(
        issuer="https://pos.toasttab.com",
        subject="u1",
        company_id="c1",
        company_name="R",
        integration="toast",
    )
    with pytest.raises(InactivePlatformError):
        build_auth_context(claims, reg)


def test_inactive_platform_general_only_token_also_denied(tmp_path):
    """AUTH-1 / CIP-A2: even a general-only (integration=None) token from an inactive platform is
    denied — an inactive platform is not served, business values or not."""
    reg = _build_registry(
        tmp_path,
        {
            "mews": _entry("https://app.mews.com", allowed_integrations=["mews"]),
            "toast": _entry(
                "https://pos.toasttab.com", active=False, allowed_integrations=["toast"]
            ),
        },
        {"mews": ["obi-mews-test"], "toast": ["obi-toast-test"]},
    )
    claims = VerifiedClaims(
        issuer="https://pos.toasttab.com",
        subject="u1",
        company_id=None,
        company_name=None,
        integration=None,
    )
    with pytest.raises(InactivePlatformError):
        build_auth_context(claims, reg)


def test_active_platform_general_only_is_allowed(tmp_path):
    """A token with integration=None from an ACTIVE platform stays general-only (allowed) — the
    active gate does not block the tokenless-business-values path."""
    ctx = build_auth_context(
        _claims(company_id=None, company_name=None, integration=None), _registry(tmp_path)
    )
    assert ctx.allowed_scopes == ("obi-general-test",)
    assert ctx.integration is None
    assert ctx.token_subject == "https://app.mews.com\x00u1"


# --- CIP-A1: the integration claim is bound to the issuing platform's allow-list ----------------


def test_cross_issuer_integration_is_rejected(tmp_path):
    """CIP-A1: a token signed by issuer A (mews, allowed only ["mews"]) that claims issuer B's
    integration (toast) is REJECTED — a trusted issuer can no longer assert any integration and
    reach another tenant's scopes."""
    reg = _build_registry(
        tmp_path,
        {
            "mews": _entry("https://app.mews.com", allowed_integrations=["mews"]),
            "toast": _entry("https://pos.toasttab.com", allowed_integrations=["toast"]),
        },
        {"mews": ["obi-mews-test"], "toast": ["obi-toast-test"]},
    )
    claims = VerifiedClaims(
        issuer="https://app.mews.com",
        subject="u1",
        company_id="c1",
        company_name="Hotel",
        integration="toast",  # mews is not allowed to assert toast
    )
    with pytest.raises(IntegrationNotAllowedError):
        build_auth_context(claims, reg)


def test_hub_vends_multiple_product_integrations(tmp_path):
    """CIP-A1 (hub model): the Data-Hub-style platform is allowed to assert several product
    integrations and each resolves to that product's scopes."""
    reg = _build_registry(
        tmp_path,
        {"datahub": _entry("https://hub.example.com", allowed_integrations=["mews", "toast"])},
        {"mews": ["obi-mews-test"], "toast": ["obi-toast-test"]},
    )

    def _hub_claims(integration):
        return VerifiedClaims(
            issuer="https://hub.example.com",
            subject="u1",
            company_id="c1",
            company_name="Co",
            integration=integration,
        )

    assert build_auth_context(_hub_claims("mews"), reg).allowed_scopes == (
        "obi-general-test",
        "obi-mews-test",
    )
    assert build_auth_context(_hub_claims("toast"), reg).allowed_scopes == (
        "obi-general-test",
        "obi-toast-test",
    )


def test_self_serving_platform_asserting_own_integration_is_allowed(tmp_path):
    """CIP-A1: the ordinary case — a self-serving platform asserting its OWN integration works."""
    ctx = build_auth_context(_claims(integration="mews"), _registry(tmp_path))
    assert ctx.allowed_scopes == ("obi-general-test", "obi-mews-test")


def test_general_only_context_helper():
    ctx = general_only_context()
    assert ctx.allowed_scopes == ("obi-general-test",)
    assert ctx.token_subject is None
    assert ctx.principal is None
    assert ctx.allowed_sources == ("confluence:default",)


def test_issuer_participates_in_identity_key(tmp_path):
    """Gap CIP-4: the identity key is issuer-namespaced, so it is not the bare `sub` claim — the
    (already-verified) issuer must appear in `token_subject`, separated by NUL."""
    ctx = build_auth_context(_claims(subject="u1"), _registry(tmp_path))
    assert ctx.token_subject == "https://app.mews.com\x00u1"
    assert "\x00" in ctx.token_subject


def test_same_subject_different_issuer_yields_distinct_token_subject(tmp_path):
    """Gap CIP-4: two trusted issuers that both mint the same `sub` must NOT collide on the
    identity key — otherwise their rate-limit / idempotency / answer-cache buckets and audit
    fingerprint would cross-contaminate."""
    reg = _registry(tmp_path)
    a = build_auth_context(_claims(issuer="https://app.mews.com", subject="shared"), reg)
    b = build_auth_context(_claims(issuer="https://other.example.com", subject="shared"), reg)
    assert a.token_subject is not None and b.token_subject is not None
    assert a.token_subject != b.token_subject
    # both still carry the same underlying sub — only the issuer namespace distinguishes them
    assert a.token_subject.endswith("\x00shared")
    assert b.token_subject.endswith("\x00shared")


def test_general_only_branch_is_also_issuer_namespaced(tmp_path):
    """Gap CIP-4: the no-business-values branch (still token-identified) is namespaced too, so a
    tokened general-only user of one issuer can't collide with another issuer's same `sub`."""
    reg = _registry(tmp_path)
    a = build_auth_context(
        _claims(
            issuer="https://app.mews.com",
            subject="g",
            integration=None,
            company_id=None,
            company_name=None,
        ),
        reg,
    )
    b = build_auth_context(
        _claims(
            issuer="https://other.example.com",
            subject="g",
            integration=None,
            company_id=None,
            company_name=None,
        ),
        reg,
    )
    assert a.integration is None and b.integration is None
    assert a.token_subject != b.token_subject


def test_namespaced_subject_yields_distinct_downstream_identity_keys(tmp_path):
    """Gap CIP-4: prove the namespacing actually separates the four identity-keyed mechanisms —
    the rate-limit key, the idempotency key, the answer-cache key, and the audit subject hash —
    for two issuers sharing a `sub`. Each key must differ across the two contexts."""
    from starlette.requests import Request

    from app.features.rag_agent.application.answer_cache import _cache_key
    from app.features.rag_agent.schemas import ChatMessage
    from app.features.rag_agent.server.router import _idempotency_cache_key, _rate_limit_key
    from app.shared.hashing import sha256_text

    reg = _registry(tmp_path)
    a = build_auth_context(_claims(issuer="https://app.mews.com", subject="shared"), reg)
    b = build_auth_context(_claims(issuer="https://other.example.com", subject="shared"), reg)

    req = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "headers": [],
            "query_string": b"",
            "client": ("198.51.100.7", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )
    history = [ChatMessage(role="user", content="what is the vpn policy")]

    assert a.token_subject is not None and b.token_subject is not None
    # rate-limit key (C2): sha256 over the namespaced subject
    assert _rate_limit_key(req, a) != _rate_limit_key(req, b)
    # answer-cache key (PLAN 5)
    assert _cache_key(history, a) != _cache_key(history, b)
    # idempotency key (C7): same header value, different identity -> different key
    key_a = _idempotency_cache_key("idem-1", a, history)
    key_b = _idempotency_cache_key("idem-1", b, history)
    assert key_a != key_b
    # audit subject fingerprint (C9): sha256(token_subject)
    assert sha256_text(a.token_subject).hex() != sha256_text(b.token_subject).hex()
