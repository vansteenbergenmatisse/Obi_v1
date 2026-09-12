"""JWT edge-binding verifier (PLAN 11.1c, ADR-0014) for the Obi embed.

A platform's own server signs a short-lived JWT at button-click; this verifier is the trust
boundary that turns that token into a `VerifiedClaims` the AuthContext builder can use to drive
retrieval scope. It replaces the caller-self-reported `knowledge_scope` on the `/chat` surface,
closing the last trusted-from-caller gap on the scope axis (the 11.1a DB backstop is the net
beneath it).

Fixed verification order (any failure -> a bare `TokenError`; the router maps that to a 401 with
no detail leaked — an attacker learns nothing about *why* a token was rejected):
  1. read `iss` without verifying the signature, to find the registry entry (unknown -> reject);
  2. reject a header `alg` not on that platform's allow-list — and never HS256 (blocks the classic
     RS256->HS256 downgrade where the RSA public key is used as an HMAC secret) BEFORE any key work;
  3. resolve the signing key by `kid` via a cached `PyJWKClient` (refreshes on an unknown kid);
  4. verify signature + registered claims (`exp`/`iat`/`iss`/`aud`/`sub` all required, `aud=obi`);
  5. bound the token lifetime by the platform's configured max (a long-lived token is rejected
     even if the issuer's own clock said it was valid);
  6. enforce the business-claims rule: `company_id`/`company_name`/`integration` all-three-or-none.

securing-http-and-llm-endpoints (this is the C1 auth mechanism strengthening the `/chat` LLM-CALL
surface): C1 covered here (alg allow-list, JWKS-by-kid, iss/aud/exp/iat required, lifetime bound);
C4 covered — the JWKS fetch is the one outbound call, given a finite timeout and a per-issuer cache
so a slow/unavailable IdP JWKS endpoint cannot hang a request or be hammered. The raw token is
never logged and never persisted (only a hash of `sub`, written in the trace — see B2)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import jwt

from app.platform.config.platforms import PlatformEntry, PlatformRegistry

_LEEWAY_SECONDS = 60
_AUD = "obi"
# The registered claims a valid token MUST carry. Kept as a module constant (not an inline literal)
# so the contract drift test (test_token_claims_contract.py) can assert the JSON Schema's `required`
# list matches this security-authoritative set exactly.
REQUIRED_CLAIMS: tuple[str, ...] = ("exp", "iat", "iss", "aud", "sub")
# C4: finite timeout on the outbound JWKS fetch so a slow/hung IdP cannot stall a chat request.
_JWKS_TIMEOUT_SECONDS = 5


class TokenError(Exception):
    """Any JWT verification failure. The router maps this to a bare 401, no detail leaked."""


@dataclass(frozen=True, slots=True)
class VerifiedClaims:
    issuer: str
    subject: str
    company_id: str | None
    company_name: str | None
    integration: str | None


class TokenVerifier:
    def __init__(
        self,
        registry: PlatformRegistry,
        *,
        jwks_client_factory: Callable[[str], jwt.PyJWKClient] | None = None,
    ) -> None:
        self._registry = registry
        self._factory = jwks_client_factory or (
            lambda url: jwt.PyJWKClient(url, cache_keys=True, timeout=_JWKS_TIMEOUT_SECONDS)
        )
        self._clients: dict[str, jwt.PyJWKClient] = {}

    def _client(self, entry: PlatformEntry) -> jwt.PyJWKClient:
        client = self._clients.get(entry.jwks_url)
        if client is None:
            client = self._factory(entry.jwks_url)
            self._clients[entry.jwks_url] = client
        return client

    def verify(self, token: str) -> VerifiedClaims:
        try:
            # 1. read iss WITHOUT verifying the signature to find the platform entry
            unverified = jwt.decode(token, options={"verify_signature": False})
            iss = str(unverified.get("iss", ""))
            entry = self._registry.by_issuer(iss)
            if entry is None:
                raise TokenError("unknown issuer")

            # 2. reject a header alg not on the platform allow-list (and never HS256)
            header = jwt.get_unverified_header(token)
            alg = str(header.get("alg", ""))
            if alg not in entry.algs or alg.startswith("HS"):
                raise TokenError("disallowed alg")

            # 3. resolve the signing key by kid (PyJWKClient caches; refreshes on an unknown kid)
            signing_key = self._client(entry).get_signing_key_from_jwt(token).key

            # 4. verify signature + registered claims
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=list(entry.algs),
                audience=_AUD,
                issuer=iss,
                leeway=_LEEWAY_SECONDS,
                options={"require": list(REQUIRED_CLAIMS)},
            )

            # 5. bound the lifetime by the platform max
            if int(payload["exp"]) - int(payload["iat"]) > entry.lifetime_minutes * 60:
                raise TokenError("lifetime exceeds platform max")

            # 6. business values: all three or none
            biz = (
                payload.get("company_id"),
                payload.get("company_name"),
                payload.get("integration"),
            )
            if any(v is not None for v in biz) and not all(v is not None for v in biz):
                raise TokenError("partial business claims")

            return VerifiedClaims(
                issuer=iss,
                subject=str(payload["sub"]),
                company_id=payload.get("company_id"),
                company_name=payload.get("company_name"),
                integration=payload.get("integration"),
            )
        except TokenError:
            raise
        except Exception as exc:  # any jwt/crypto error collapses to a bare TokenError
            raise TokenError("invalid token") from exc
