"""Task A3 (PLAN 11.1c): JWT verifier — alg allow-list, JWKS-by-kid, claim checks.

A throwaway RS256 keypair is minted per test; the JWKS client is stubbed via the factory so
no network I/O happens. Every failure mode collapses to a bare TokenError (the router maps
that to a 401 with no detail leaked)."""

from __future__ import annotations

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

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
                "integrations": {"mews": ["obi-mews-test", "obi-general-test"]},
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
