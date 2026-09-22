"""Frozen edge identity for the Obi embed (PLAN 11.1c, ADR-0014).

`build_auth_context` turns a verified JWT (`VerifiedClaims`, see server/token_verifier.py) into
the single immutable `AuthContext` that drives EVERY reader transaction on the answer path — its
`allowed_scopes` feed `apply_knowledge_scope` (the scope-GUC + app predicate), sitting on top of
the 11.1a DB backstop. The verified `integration` claim is what maps to scopes; the caller can no
longer self-report `knowledge_scope`.

v1 scope decisions (spec §6): integration-level content scoping only. `principal` is always `None`
for embedded users (open Confluence pages only, no per-person page ACL). `company_id`/`company_name`
are carried for audit/future use but are NEVER a scope axis — two users of the same integration in
different companies see the same knowledge scopes (done-when 3a). A token with no business values
from an ACTIVE platform degrades to general-only (not refused); every failure below raises an
`AuthContextError` the router maps to a bare 401.

Two authorization gates run here, at the trust boundary (not in the verifier, which intentionally
verifies-without-serving — PLAN 11.1c):
  - AUTH-1 / CIP-A2: the issuing platform must be ACTIVE. Verification (token_verifier.by_issuer)
    admits an inactive platform's validly-signed token; this gate consults the registry's ACTIVE
    view (`platform_for`) and denies it — an inactive platform is not served at all
    (`InactivePlatformError`).
  - CIP-A1: the verified `integration` claim must be one the issuing platform is trusted to assert
    (`PlatformEntry.allowed_integrations`). A self-serving platform (mews/toast/opera-cloud) may
    assert only its own integration; a hub (datahub) may vend the product integrations it lists.
    Otherwise `IntegrationNotAllowedError` — so a trusted issuer can no longer claim any
    integration and reach another tenant's scopes. An integration that is not a real integration
    at all raises `UnknownIntegrationError`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.platform.config.platforms import PlatformRegistry

if TYPE_CHECKING:
    # Imported for typing only: importing server.token_verifier at runtime would pull in
    # server/__init__ -> router -> answer_service (which imports THIS module), a circular import.
    # `from __future__ import annotations` keeps the `claims: VerifiedClaims` hint a string, and
    # build_auth_context only ever touches attributes on the passed object at runtime.
    from app.features.rag_agent.server.token_verifier import VerifiedClaims

_GENERAL = "obi-general-test"
# v1: every platform reads the same source; AuthContext carries it for the future source axis, but
# the retriever keeps setting the source GUC from its construction-time default (see the plan).
_DEFAULT_SOURCES = ("confluence:default",)


class AuthContextError(ValueError):
    """Any reason a verified token cannot be turned into a scoped AuthContext. The router catches
    this base and returns a bare 401 (no detail leaked about which gate failed)."""


class UnknownIntegrationError(AuthContextError):
    """The verified integration claim is not a real integration (not in the registry's integration
    map) -> the router returns 401."""


class InactivePlatformError(AuthContextError):
    """AUTH-1 / CIP-A2: the verified issuer's platform is not active, so it is not served at all
    (even for a general-only token) -> the router returns 401."""


class IntegrationNotAllowedError(AuthContextError):
    """CIP-A1: the verified issuer is a trusted platform, but is not trusted to assert this
    (otherwise-real) integration -> the router returns 401."""


@dataclass(frozen=True, slots=True)
class AuthContext:
    company_id: str | None
    company_name: str | None
    integration: str | None
    allowed_scopes: tuple[str, ...]
    allowed_sources: tuple[str, ...]
    principal: str | None
    token_subject: str | None


def _identity_key(claims: VerifiedClaims) -> str:
    """Gap CIP-4: namespace the token subject by its (already-verified) issuer so two different
    trusted issuers that both mint a token with the same `sub` never collide across the four
    identity-keyed mechanisms that consume `token_subject` — the rate-limit bucket
    (`router._rate_limit_key`), the idempotency key (`router._idempotency_cache_key`), the
    answer-cache key (`answer_cache._cache_key`) and the audit subject fingerprint
    (`answer_service`). The NUL separator is unambiguous: it cannot appear in a JWT `iss`/`sub`
    JSON string value, so no `sub` can forge a different (issuer, subject) split of the key."""
    return f"{claims.issuer}\x00{claims.subject}"


def general_only_context() -> AuthContext:
    """The tokenless / internal / eval path: general-only, no identity, no principal."""
    return AuthContext(
        company_id=None,
        company_name=None,
        integration=None,
        allowed_scopes=(_GENERAL,),
        allowed_sources=_DEFAULT_SOURCES,
        principal=None,
        token_subject=None,
    )


def build_auth_context(claims: VerifiedClaims, registry: PlatformRegistry) -> AuthContext:
    # AUTH-1 / CIP-A2: gate on the ACTIVE view, not the verify-only by_issuer view. An inactive
    # platform's token verifies (token_verifier.by_issuer) but is not served here at all.
    entry = registry.platform_for(claims.issuer)
    if entry is None:
        raise InactivePlatformError(claims.issuer)
    if claims.integration is None:
        # no business values -> general only, still identified by the token subject
        return AuthContext(
            company_id=None,
            company_name=None,
            integration=None,
            allowed_scopes=(_GENERAL,),
            allowed_sources=_DEFAULT_SOURCES,
            principal=None,
            token_subject=_identity_key(claims),
        )
    scopes = registry.scopes_for(claims.integration)
    if scopes is None:
        raise UnknownIntegrationError(claims.integration)
    # CIP-A1: bind the integration claim to the issuing platform's allow-list — a trusted issuer
    # may only assert an integration it is trusted to vend, never another tenant's.
    if claims.integration not in entry.allowed_integrations:
        raise IntegrationNotAllowedError(
            f"platform {entry.key} may not assert integration '{claims.integration}'"
        )
    return AuthContext(
        company_id=claims.company_id,
        company_name=claims.company_name,
        integration=claims.integration,
        allowed_scopes=tuple(scopes),
        allowed_sources=_DEFAULT_SOURCES,
        principal=None,  # v1: embedded users have no per-person Confluence ACL
        token_subject=_identity_key(claims),
    )
