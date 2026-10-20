"""JWT edge-binding verifier (PLAN 11.1c, ADR-db-level-customer-scope-isolation-backstop) for the
Obi embed.

A platform's own server signs a short-lived JWT at button-click; this verifier is the trust
boundary that turns that token into a `VerifiedClaims` the AuthContext builder uses for identity
and the directed source/target connection (ADR-source-system-decides-widget-eligibility). Nothing
the caller sends in the body decides access. The knowledge-scope axis and its DB backstop are
retired (ADR-routing-labels-sole-content-axis).

Fixed verification order (any failure -> a bare `TokenError`; the router maps that to a 401 with
no detail leaked — an attacker learns nothing about *why* a token was rejected):
  1. read `iss` without verifying the signature, to find the registry entry (unknown -> reject);
  2. reject a header `alg` not on that platform's allow-list — and never HS256 (blocks the classic
     RS256->HS256 downgrade where the RSA public key is used as an HMAC secret) BEFORE any key work;
  3. resolve the signing key by `kid` via a cached `PyJWKClient` (refreshes on an unknown kid);
  4. verify signature + registered claims (`exp`/`iat`/`iss`/`aud`/`sub` all required, `aud=obi`);
  5. bound the token lifetime by the platform's configured max (a long-lived token is rejected
     even if the issuer's own clock said it was valid);
  6. enforce the business-claims rule: with no `context` claim (the legacy form),
     `company_id`/`company_name`/`integration` all-three-or-none; with `context` present (the
     structured form, substep 8.1.3) the trio rule does not apply — the context is structurally
     validated (`_parse_context_slots`) and its slots ride `VerifiedClaims.slots` verbatim for
     the gate's five checks.

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


_SLOT_NAMES = ("pos", "pms", "accounting")


def _parse_context_slots(context: object) -> ContextSlots:
    """Structural validation of the `context` claim (substep 8.1.3): an object with a `slots`
    object whose keys are only pos/pms/accounting and whose values are strings or null. Anything
    else is a malformed token -> bare TokenError (401), the same no-detail posture as every
    other structural failure. Slot VALUES are not judged here — shape/membership/role/vend/
    allowlist are the gate's five checks, which fail with their own statuses (400 for an
    unknown value, before any search)."""
    if not isinstance(context, dict):
        raise TokenError("malformed context")
    slots = context.get("slots")
    if not isinstance(slots, dict):
        raise TokenError("malformed context")
    if any(key not in _SLOT_NAMES for key in slots):
        raise TokenError("malformed context")  # a fourth slot name never sneaks in
    values: dict[str, str | None] = {}
    for name in _SLOT_NAMES:
        value = slots.get(name)
        if value is not None and not isinstance(value, str):
            raise TokenError("malformed context")
        values[name] = value
    return ContextSlots(**values)


@dataclass(frozen=True, slots=True)
class ContextSlots:
    """The structured integration context's three slots (panel mi-contract, substep 8.1.3):
    one raw claimed value per §D.13 slot role, or None for empty. Values are carried VERBATIM
    from the verified `context.slots` claim — alias resolution, catalog membership, role
    agreement, vend rights and the launch allowlist are the GATE's five checks
    (`build_auth_context`), not the verifier's."""

    pos: str | None = None
    pms: str | None = None
    accounting: str | None = None


def _parse_directed(payload: dict) -> tuple[str, str, str]:
    """Structural validation of the directed-connection form (substep 9.3.1,
    ADR-directed-source-target-routing-labels): a token
    carrying `source_system` + `target_system` + `business_id`, all three non-empty strings.
    A partner system missing its counterpart, or a missing/empty/non-string business_id (an integer
    id is accepted and normalized to its decimal string — Base signs it as a number), is a
    malformed token -> bare TokenError (401), the same no-detail posture as a malformed context.
    The VALUES are not judged here — catalog membership of a well-shaped source/target is the
    gate's check (`build_auth_context`), which fails an unknown system with a 400 before search."""
    source = payload.get("source_system")
    target = payload.get("target_system")
    business = payload.get("business_id")
    # Base signs business_id as a JSON integer; normalize it to its decimal string so every
    # downstream consumer sees one shape. bool is an int subclass and is never an id.
    if isinstance(business, int) and not isinstance(business, bool):
        business = str(business)
    for value in (source, target, business):
        if not isinstance(value, str) or not value:
            raise TokenError("malformed directed connection")
    return source, target, business  # type: ignore[return-value]  # narrowed by the loop above


@dataclass(frozen=True, slots=True)
class VerifiedClaims:
    issuer: str
    subject: str
    company_id: str | None
    company_name: str | None
    integration: str | None
    # substep 8.1.3: the structured form's slots; None when the token carries no `context`
    # claim (the legacy form — `integration` above is then read as one filled slot by the gate).
    slots: ContextSlots | None = None
    # substep 9.3.1 (Option A, ADR-directed-source-target-routing-labels): the directed source →
    # target connection form. Present
    # (all three non-None) only when the token carries `source_system`; None otherwise. These
    # drive routing when present — `slots`/`integration` stay accepted but no longer route.
    source_system: str | None = None
    target_system: str | None = None
    business_id: str | None = None


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

            # 6. business values. Three forms (token-claims.json, substeps 8.1.2 / 9.3.1):
            # - directed (ADR-directed-source-target-routing-labels):
            # `source_system`+`target_system`+`business_id` — the
            #      routing form; the legacy trio rule does NOT apply;
            #    - structured: a `context` claim with the three slots — company-ID-only, the
            #      legacy trio rule does NOT apply (the schema's context/source_system conditional);
            #    - legacy: neither — company_id/company_name/integration all three or none.
            slots: ContextSlots | None = None
            source_system: str | None = None
            target_system: str | None = None
            business_id: str | None = None
            if "source_system" in payload or "target_system" in payload:
                source_system, target_system, business_id = _parse_directed(payload)
            elif "context" in payload:
                slots = _parse_context_slots(payload["context"])
            else:
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
                slots=slots,
                source_system=source_system,
                target_system=target_system,
                business_id=business_id,
            )
        except TokenError:
            raise
        except Exception as exc:  # any jwt/crypto error collapses to a bare TokenError
            raise TokenError("invalid token") from exc
