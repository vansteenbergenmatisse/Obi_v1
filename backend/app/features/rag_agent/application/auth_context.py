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
degrades to general-only (not refused); an unknown integration raises `UnknownIntegrationError`
(the router maps it to 401)."""

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


class UnknownIntegrationError(ValueError):
    """The verified integration claim is not in the platform registry -> the router returns 401."""


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
    return AuthContext(
        company_id=claims.company_id,
        company_name=claims.company_name,
        integration=claims.integration,
        allowed_scopes=tuple(scopes),
        allowed_sources=_DEFAULT_SOURCES,
        principal=None,  # v1: embedded users have no per-person Confluence ACL
        token_subject=_identity_key(claims),
    )
