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
    assert ctx.token_subject == "u1"
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
    assert ctx.token_subject == "u1"


def test_unknown_integration_raises(tmp_path):
    with pytest.raises(UnknownIntegrationError):
        build_auth_context(_claims(integration="wordpress"), _registry(tmp_path))


def test_general_only_context_helper():
    ctx = general_only_context()
    assert ctx.allowed_scopes == ("obi-general-test",)
    assert ctx.token_subject is None
    assert ctx.principal is None
    assert ctx.allowed_sources == ("confluence:default",)
