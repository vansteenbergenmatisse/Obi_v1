"""Task A3 (PLAN 11.1c): JWT verifier — alg allow-list, JWKS-by-kid, claim checks.

A throwaway RS256 keypair is minted per test; the JWKS client is stubbed via the factory so
no network I/O happens. Every failure mode collapses to a bare TokenError (the router maps
that to a 401 with no detail leaked)."""

from __future__ import annotations

import json
import math
import time
from types import SimpleNamespace

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
                "integrations": {"mews": ["obi-mews-test"]},
            }
        )
    )
    return load_platform_registry(
        p, frozenset({"obi-general-test", "obi-mews-test"}), allow_empty=False
    )


def _verifier(registry, key):
    class _StubJWK:
        def get_signing_key_from_jwt(self, token):
            class _K:
                pass

            k = _K()
            k.key = key.public_key()
            return k

    return TokenVerifier(registry, jwks_client_factory=lambda url: _StubJWK())


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
