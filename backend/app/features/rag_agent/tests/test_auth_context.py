"""Task A2 (PLAN 11.1c): frozen AuthContext + integration->scope resolution.

Includes done-when 3a — two contexts that differ only by `company_id` resolve to identical
scopes (company_id is audit-only in v1, never a scope axis; this replaces the dropped mews-2
browser proof from the spec)."""

from __future__ import annotations

import json

import pytest

from app.features.rag_agent.application.auth_context import (
    UnknownIntegrationError,
    build_auth_context,
    general_only_context,
)
from app.features.rag_agent.server.token_verifier import VerifiedClaims
from app.platform.config.platforms import load_platform_registry


def _registry(tmp_path):
    p = tmp_path / "platforms.json"
    p.write_text(
        json.dumps(
            {
                "platforms": {
                    "mews": {
                        "issuer": "https://app.mews.com",
                        "jwks_url": "j",
                        "domains": ["app.mews.com"],
                        "lifetime_minutes": 60,
                        "algs": ["RS256"],
                        "active": True,
                    }
                },
                "integrations": {"mews": ["obi-mews-test"]},
            }
        )
    )
    return load_platform_registry(
        p, frozenset({"obi-general-test", "obi-mews-test"}), allow_empty=False
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
