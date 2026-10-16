"""Task A3 (PLAN 11.1c): JWT verifier — alg allow-list, JWKS-by-kid, claim checks.

A throwaway RS256 keypair is minted per test; the JWKS client is stubbed via the factory so
no network I/O happens. Every failure mode collapses to a bare TokenError (the router maps
that to a 401 with no detail leaked)."""

from __future__ import annotations

import json
import math
import time
from types import SimpleNamespace
from typing import Any, cast

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.features.rag_agent.server import token_verifier
from app.features.rag_agent.server.token_verifier import TokenError, TokenVerifier
from app.platform.config.platforms import load_platform_registry

ISS = "https://app.mews.com"


@pytest.fixture
def keypair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def registry(tmp_path):
    p = tmp_path / "platforms.json"
    p.write_text(
        json.dumps(
            {
                "platforms": {
                    "mews": {
                        "issuer": ISS,
                        "jwks_url": "https://app.mews.com/j",
                        "domains": ["app.mews.com"],
                        "lifetime_minutes": 60,
                        "algs": ["RS256", "ES256"],
                        "active": True,
                    }
                },
                "integrations": {"mews": []},
            }
        )
    )
    return load_platform_registry(
        p, frozenset({"obi-general-test", "obi-mews-test"}), allow_empty=False
    )


def _verifier(registry, key):
    class _StubJWK:
        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key=key.public_key())

    return TokenVerifier(registry, jwks_client_factory=lambda url: cast(Any, _StubJWK()))


def _sign(key, alg="RS256", **claims):
    now = int(time.time())
    payload = {"iss": ISS, "aud": "obi", "sub": "u1", "iat": now, "exp": now + 3600}
    payload.update(claims)
    return jwt.encode(payload, key, algorithm=alg, headers={"kid": "k1"})


def test_valid_token(registry, keypair):
    tok = _sign(keypair, company_id="c1", company_name="Hotel", integration="mews")
    vc = _verifier(registry, keypair).verify(tok)
    assert vc.subject == "u1"
    assert vc.integration == "mews"
    assert vc.issuer == ISS
    assert vc.company_id == "c1"
    assert vc.company_name == "Hotel"


def test_unknown_issuer_rejected(registry, keypair):
    tok = _sign(keypair, iss="https://evil.example")
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)


def test_hs256_rejected(registry, keypair):
    # Attacker downgrades to HS256. The alg allow-list rejects it BEFORE any signature/key work,
    # so the HMAC secret is irrelevant — what matters is that an HS256 token never gets verified.
    # (PyJWT itself refuses to *encode* HS256 with a PEM key, so the attack token is HMAC-signed
    # with an arbitrary secret; the header still says alg=HS256, which is what we reject on.)
    now = int(time.time())
    tok = jwt.encode(
        {"iss": ISS, "aud": "obi", "sub": "u1", "iat": now, "exp": now + 60},
        "attacker-chosen-secret-padded-to-32-bytes-min",
        algorithm="HS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)


def test_wrong_audience_rejected(registry, keypair):
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(_sign(keypair, aud="not-obi"))


def test_expired_rejected(registry, keypair):
    now = int(time.time())
    tok = jwt.encode(
        {"iss": ISS, "aud": "obi", "sub": "u1", "iat": now - 7200, "exp": now - 3600},
        keypair,
        algorithm="RS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)


def test_lifetime_over_platform_max_rejected(registry, keypair):
    now = int(time.time())
    tok = jwt.encode(
        {"iss": ISS, "aud": "obi", "sub": "u1", "iat": now, "exp": now + 60 * 60 * 5},
        keypair,
        algorithm="RS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)  # 5h > lifetime_minutes 60


def test_missing_iat_rejected(registry, keypair):
    now = int(time.time())
    tok = jwt.encode(
        {"iss": ISS, "aud": "obi", "sub": "u1", "exp": now + 60},
        keypair,
        algorithm="RS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)


def test_partial_business_claims_rejected(registry, keypair):
    # company_id present but company_name/integration missing -> all-three-or-none violated
    tok = _sign(keypair, company_id="c1")
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)


def test_no_business_claims_is_valid(registry, keypair):
    vc = _verifier(registry, keypair).verify(_sign(keypair))
    assert vc.integration is None
    assert vc.company_id is None
    assert vc.subject == "u1"


def test_rt1_verifier_extracts_context_slots(registry, keypair):
    """panel mi-contract · substep 8.1.3
    A signed token carrying the structured form (company_id + context.slots) verifies and the
    slots reach VerifiedClaims — the gate's input. Null and omitted keys are both empty."""
    from app.features.rag_agent.server.token_verifier import ContextSlots

    tok = _sign(
        keypair,
        company_id="c1",
        context={"slots": {"pos": None, "pms": "mews", "accounting": "xero"}},
    )
    vc = _verifier(registry, keypair).verify(tok)
    assert vc.slots == ContextSlots(pos=None, pms="mews", accounting="xero")
    assert vc.company_id == "c1"
    assert vc.integration is None


def test_rt1_context_token_is_company_id_only_no_trio_rule(registry, keypair):
    """panel mi-contract · substep 8.1.3
    The legacy all-three-or-none business rule is scoped to context-ABSENT tokens (the schema's
    if/then, substep 8.1.2): a structured token carrying company_id without company_name or
    integration verifies — it is the decided company-ID-only form."""
    tok = _sign(keypair, company_id="c1", context={"slots": {"pms": "mews"}})
    vc = _verifier(registry, keypair).verify(tok)
    assert vc.company_id == "c1"
    assert vc.company_name is None
    assert vc.slots is not None and vc.slots.pms == "mews"


def test_rt1_malformed_context_is_rejected(registry, keypair):
    """panel mi-contract · substep 8.1.3
    Structural garbage in the context claim — context not an object, slots missing, a fourth
    slot name, or a non-string slot value — collapses to a bare TokenError (401), the same
    no-detail posture as every other malformed token."""
    bad_contexts = [
        "not-an-object",
        {},  # no slots key
        {"slots": "not-an-object"},
        {"slots": {"pms": "mews", "crm": "salesforce"}},  # a fourth slot can't sneak in
        {"slots": {"pms": 42}},  # a non-string slot value
    ]
    for context in bad_contexts:
        tok = _sign(keypair, company_id="c1", context=context)
        with pytest.raises(TokenError):
            _verifier(registry, keypair).verify(tok)


def test_rt1_verifier_extracts_directed_connection(registry, keypair):
    """panel mi-contract · substep 9.3.1
    The directed form (source_system + target_system + business_id, ADR-0020) verifies and the
    triple reaches VerifiedClaims — the gate's routing input. The legacy trio rule does not apply
    (no company_id/company_name/integration are present)."""
    tok = _sign(
        keypair,
        source_system="toast",
        target_system="mews",
        business_id="B-3075",
    )
    vc = _verifier(registry, keypair).verify(tok)
    assert vc.source_system == "toast"
    assert vc.target_system == "mews"
    assert vc.business_id == "B-3075"
    assert vc.slots is None
    assert vc.company_id is None


def test_rt1_verifier_accepts_numeric_business_id(registry, keypair):
    """panel mi-contract · substep 8.5.3 (Base partner token)
    Base signs `business_id` as a JSON integer (e.g. 2108). An integer id is accepted and
    normalized to its decimal string, so the gate and the company-isolation axis see the same
    value a string id would give. A boolean is not an id and stays malformed."""
    tok = _sign(keypair, source_system="toast", target_system="mews", business_id=2108)
    vc = _verifier(registry, keypair).verify(tok)
    assert vc.business_id == "2108"

    tok = _sign(keypair, source_system="toast", target_system="mews", business_id=True)
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)


def test_rt1_malformed_directed_connection_rejected(registry, keypair):
    """panel mi-contract · substep 9.3.1
    A directed token missing its partner system or its business_id, or carrying a non-string
    value, is structurally malformed — a bare TokenError (401), the same no-detail posture as a
    malformed context. (Catalog membership of a WELL-SHAPED value is the gate's 400, not here.)"""
    bad = [
        {"source_system": "toast"},  # no target, no business_id
        {"target_system": "mews"},  # no source
        {"source_system": "toast", "target_system": "mews"},  # no business_id
        {"source_system": "toast", "target_system": 42, "business_id": "B-1"},  # non-string
        {"source_system": "", "target_system": "mews", "business_id": "B-1"},  # empty source
    ]
    for claims in bad:
        tok = _sign(keypair, **claims)
        with pytest.raises(TokenError):
            _verifier(registry, keypair).verify(tok)


def test_missing_sub_rejected(registry, keypair):
    """gap AUTHRT-3: `sub` is a required registered claim (REQUIRED_CLAIMS) — a token without it is
    rejected before it can identify anyone (mirrors test_missing_iat_rejected)."""
    now = int(time.time())
    tok = jwt.encode(
        {"iss": ISS, "aud": "obi", "iat": now, "exp": now + 60},
        keypair,
        algorithm="RS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)


def test_missing_exp_rejected(registry, keypair):
    """gap AUTHRT-3: `exp` is a required registered claim — a token without an expiry is rejected
    (a non-expiring embed token must never be accepted; mirrors test_missing_iat_rejected)."""
    now = int(time.time())
    tok = jwt.encode(
        {"iss": ISS, "aud": "obi", "sub": "u1", "iat": now},
        keypair,
        algorithm="RS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(TokenError):
        _verifier(registry, keypair).verify(tok)


def test_g8_forged_signature_rejected_at_signature_step(registry, keypair):
    """gap G8 (4.2 coverage audit) · PLAN 11.1c verification order, step 4.
    A token whose iss/alg/kid and every claim are VALID but which is signed by a different private
    key than the JWKS-resolved public key must be rejected — and rejected at the signature step
    itself (the cause chain is `InvalidSignatureError`, proving no earlier gate masked the check),
    collapsing to the same bare TokenError as every other failure (no detail on the wire)."""
    forger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    # All claims valid (incl. the all-three business claims), so steps 1-3 and 5-6 would pass:
    # the ONLY defect is the signature. The stub JWKS still resolves `keypair`'s public key.
    tok = _sign(forger, company_id="c1", company_name="Hotel", integration="mews")

    with pytest.raises(TokenError) as excinfo:
        _verifier(registry, keypair).verify(tok)

    assert isinstance(excinfo.value.__cause__, jwt.InvalidSignatureError)
    assert str(excinfo.value) == "invalid token"  # the uniform catch-all message, nothing extra


def _fake_pyjwk_client_class(keypair, *, constructions: list[dict[str, object]]):
    """A stand-in for `jwt.PyJWKClient` that records every construction's url + kwargs and resolves
    every token to the test keypair's public key — patched over `token_verifier.jwt.PyJWKClient` so
    the REAL default factory runs (no `jwks_client_factory` override) while staying network-free."""

    class _FakePyJWKClient:
        def __init__(self, url: str, **kwargs: object) -> None:
            constructions.append({"url": url, **kwargs})

        def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
            return SimpleNamespace(key=keypair.public_key())

    return _FakePyJWKClient


def test_authrt2_jwks_client_is_built_once_per_issuer_across_verifies(
    registry, keypair, monkeypatch
):
    """gap AUTHRT-2 · C4. The JWKS client is cached per `jwks_url`: two `verify()` calls for the
    same issuer construct exactly one client, so the IdP's JWKS endpoint is not rebuilt/re-fetched
    per token (bounding outbound load and letting PyJWKClient's own key cache do its job)."""
    constructions: list[dict[str, object]] = []
    monkeypatch.setattr(
        token_verifier.jwt,
        "PyJWKClient",
        _fake_pyjwk_client_class(keypair, constructions=constructions),
    )

    verifier = TokenVerifier(registry)  # default factory, exercised through the patched client
    verifier.verify(_sign(keypair))
    verifier.verify(_sign(keypair))

    assert len(constructions) == 1  # one build, cached by jwks_url across both verifies
    assert constructions[0]["url"] == "https://app.mews.com/j"


def test_authrt2_default_jwks_factory_passes_a_finite_positive_timeout(
    registry, keypair, monkeypatch
):
    """gap AUTHRT-2 · C4. The REAL default JWKS-client factory (no override) constructs its
    `PyJWKClient` with a finite, positive `timeout`, so a slow or hung IdP JWKS endpoint can never
    stall a chat request indefinitely. Inspects the kwargs the default factory actually passes."""
    constructions: list[dict[str, object]] = []
    monkeypatch.setattr(
        token_verifier.jwt,
        "PyJWKClient",
        _fake_pyjwk_client_class(keypair, constructions=constructions),
    )

    TokenVerifier(registry).verify(_sign(keypair))  # default factory, not a stub override

    assert constructions and "timeout" in constructions[0]
    timeout = constructions[0]["timeout"]
    assert isinstance(timeout, (int, float))
    assert math.isfinite(timeout) and timeout > 0
