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

from app.features.rag_agent.server.token_verifier import VerifiedClaims
from app.platform.config.platforms import PlatformRegistry

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
            token_subject=claims.subject,
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
        token_subject=claims.subject,
    )
