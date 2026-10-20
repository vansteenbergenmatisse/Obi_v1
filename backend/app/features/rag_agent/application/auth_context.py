"""Frozen edge identity for the Obi embed (PLAN 11.1c, ADR-db-level-customer-scope-isolation-backstop).

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
    at all raises `UnknownIntegrationError`.

Substep 8.1.3 (panels mi-gate/mi-contract): the gate accepts the three-slot integration context.
After the active-platform gate, the FIVE slot checks of
docs/Final_docs/5-integration-context/integration-token-decisions.md §4 run in order over the filled slots —
a legacy single-`integration` note is read as ONE filled slot (the product's catalog role picks
the slot), so both token forms go through the same chain:

  1. shape       — every filled value a short lowercase slug; company_id present when a slot is
                   filled                                   -> `InvalidSlotValueError` (400)
  2. membership  — every filled value resolves (canonical id or catalog alias) to a product in
                   knowledge-base/config/product_catalog.json -> `UnknownIntegrationError` (400,
                   before any search — §D.11 / chat.yaml)
  3. role        — the product's catalog role matches the slot it sits in (toast is never a PMS)
                                                             -> `InvalidSlotValueError` (400)
  4. vend rights — the issuing platform may only fill slots with products its
                   `allowed_integrations` resolve to (CIP-A1 generalized: Data Hub vends
                   POS/PMS, Base vends Accounting)           -> `IntegrationNotAllowedError` (401)
  5. allowlist   — a FILLED POS/PMS slot must be on the launch allowlist (Toast as POS, Mews as
                   PMS); the Accounting slot is NEVER gated here (owner decision O4 — inert for
                   eligibility); an EMPTY slot never refuses -> `SlotNotOnAllowlistError` (401)

The one frozen AuthContext (never-bend rule 3) then carries the canonical slot ids
(`slot_pos`/`slot_pms`/`slot_accounting`) and the union of the filled slots' knowledge scopes.
When a token carries BOTH forms, the structured `context` is authoritative and the legacy claim
is ignored (token-claims.json scopes the legacy trio rule to context-less tokens)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from app.platform.config.platforms import PlatformEntry, PlatformRegistry
from app.platform.config.product_catalog import ProductCatalog, load_product_catalog

if TYPE_CHECKING:
    # Imported for typing only: importing server.token_verifier at runtime would pull in
    # server/__init__ -> router -> answer_service (which imports THIS module), a circular import.
    # `from __future__ import annotations` keeps the `claims: VerifiedClaims` hint a string, and
    # build_auth_context only ever touches attributes on the passed object at runtime.
    from app.features.rag_agent.server.token_verifier import VerifiedClaims

# v1: every platform reads the same source; AuthContext carries it for the future source axis, but
# the retriever keeps setting the source GUC from its construction-time default (see the plan).
_DEFAULT_SOURCES = ("confluence:default",)


class AuthContextError(ValueError):
    """Any reason a verified token cannot be turned into a scoped AuthContext. The router catches
    this base and returns a bare 401 (no detail leaked about which gate failed)."""


class InvalidSlotValueError(AuthContextError):
    """Substep 8.1.3: a slot (or legacy integration) value that could never be valid — bad slug
    shape, a missing company_id beside a filled slot, or a product in the wrong slot role. The
    router maps this family to a 400 BEFORE any search (§D.11 / chat.yaml), the posture an
    unknown body scope already has."""


class UnknownIntegrationError(InvalidSlotValueError):
    """Check 2 (membership): the verified value resolves to no product in the catalog (and, pre-
    8.1.3, no integration in the registry map) -> the router returns 400 before any search."""


class InactivePlatformError(AuthContextError):
    """AUTH-1 / CIP-A2: the verified issuer's platform is not active, so it is not served at all
    (even for a general-only token) -> the router returns 401."""


class IntegrationNotAllowedError(AuthContextError):
    """CIP-A1 (check 4, vend rights): the verified issuer is a trusted platform, but is not
    trusted to assert this (otherwise-real) product in this slot -> the router returns 401."""


class SlotNotOnAllowlistError(AuthContextError):
    """Check 5: a FILLED POS/PMS slot holds a real, vendable product outside the launch allowlist
    (Toast as POS, Mews as PMS) — the session is refused (§D.13 item 3). The router returns the
    same bare 401 as every other gate refusal; the frontend's hiding of Obi is UX on top, never
    the boundary."""


class SourceNotEnabledError(AuthContextError):
    """ADR-source-system-decides-widget-eligibility (source-enablement visibility gate, supersedes the ADR-widget-hides-via-visibility-probe target gate): the
    directed SOURCE system is unknown to the catalog or not in its `enabled_sources` — not a source
    Obi supports, so the session is refused and the router returns a 403 (off the 401 renew path)
    that hides Obi. The message NEVER names the product (never-bend rule 10): the error body is a
    fixed string; which source was refused is not leaked to the caller."""


@dataclass(frozen=True, slots=True)
class AuthContext:
    company_id: str | None
    company_name: str | None
    integration: str | None
    allowed_scopes: tuple[str, ...]
    allowed_sources: tuple[str, ...]
    principal: str | None
    token_subject: str | None
    # substep 8.1.3: the validated integration context — one CANONICAL catalog id per filled
    # slot (aliases already resolved), None for empty. A legacy note fills exactly one of these.
    slot_pos: str | None = None
    slot_pms: str | None = None
    slot_accounting: str | None = None
    # substep 9.3.1 (Option A, ADR-directed-source-target-routing-labels): the directed connection this chat is bound to — the
    # resolved CANONICAL catalog ids of the source and target systems, None for the slot/legacy
    # forms. Chat-start (9.2.1) reuses these to build the four routing labels + connection block.
    source_slug: str | None = None
    target_slug: str | None = None
    # substep 8.3.1: the VERIFIED host platform key (the active registry entry for the token's
    # issuer) — platform-interface eligibility needs it; None (tokenless/internal) never matches
    # a platform-interface rule, never broadens.
    platform: str | None = None


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
        allowed_scopes=(),
        allowed_sources=_DEFAULT_SOURCES,
        principal=None,
        token_subject=None,
    )


# The §D.13 slot roles in their fixed order (matches the catalog's VALID_PRODUCT_ROLES).
_SLOT_ROLES = ("pos", "pms", "accounting")
# Check 1 (shape): mirrors the router's body knowledge_scope slug validator (integration-token-decisions §4).
_SLOT_VALUE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


@lru_cache(maxsize=1)
def _default_catalog() -> ProductCatalog:
    """The committed product catalog, loaded once per process. `Settings` already fail-fasts a
    malformed file at boot (`_require_valid_product_catalog`); the cache keeps the gate from
    re-reading the JSON on every /chat request (the AUTHRT-REGISTRY-RELOAD posture)."""
    return load_product_catalog()


def _build_directed_context(
    claims: VerifiedClaims,
    entry: PlatformEntry,
    catalog: ProductCatalog | None,
) -> AuthContext:
    """The directed source → target gate (substep 9.3.1, Option A, ADR-directed-source-target-routing-labels, panels mi-gate/
    mi-contract).

    ADR-source-system-decides-widget-eligibility (owner, 2026-10-20): only the SOURCE system decides eligibility. A source can have
    hundreds of targets, so the target is assumed supported and NEVER checked.
      source · resolves through the SAME lenient catalog resolver chat-start uses
            (`resolve_system`: canonical id, alias, or display name, case/space insensitive). An
            unresolved source is SourceNotEnabledError (403, Obi hidden) — raised before any
            retrieval runs. A known source must be vendable by the issuer (`allowed_integrations`,
            CIP-A1: IntegrationNotAllowedError, 401) and then be in `enabled_sources`
            (SourceNotEnabledError, 403). Precedence: vend 401 before enablement 403.
      target · resolved with the same resolver for routing only. An unknown target is carried as
            `target_slug=None` (never a fabricated system) and routing falls back to the source's
            own labels; no vend, enablement, role or allowlist check applies to it.
    The slot role check and the launch allowlist lapse for the directed form (ADR-directed-source-target-routing-labels D4/D5).

    `business_id` (verified present for this form) becomes `company_id` — the company-isolation
    axis the chat-session key and the audit trail already consume (never a scope axis by itself).
    Scopes stay general-only here; the four routing labels (built from `source_slug`/`target_slug`
    at chat-start) are the content axis, wired into the hard filter in a later stage. The body
    never contributes any of this (never-bend rules 2-3): the gate reads only the verified token."""
    catalog = catalog if catalog is not None else _default_catalog()

    # -- source · membership, vend rights, enablement (ADR-source-system-decides-widget-eligibility: only the source gates) ---------
    source = catalog.resolve_system(claims.source_system or "")
    if source is None:
        raise SourceNotEnabledError("source system is not supported")
    vend_set: set[str] = set()
    for allowed in entry.allowed_integrations:
        vend_set.update(catalog.resolve(allowed))
    if source.id not in vend_set:
        raise IntegrationNotAllowedError(
            f"platform {entry.key} may not assert '{source.id}' as the source system"
        )
    # Rule 10: the message carries NO product id — which source was refused is not leaked.
    if source.id not in catalog.enabled_sources:
        raise SourceNotEnabledError("source system is not supported")

    # -- target · routing input only, never checked (ADR-source-system-decides-widget-eligibility) -----------------------------------
    target = catalog.resolve_system(claims.target_system or "")

    return AuthContext(
        company_id=claims.business_id,
        company_name=None,
        integration=None,
        allowed_scopes=(),
        allowed_sources=_DEFAULT_SOURCES,
        principal=None,  # v1: embedded users have no per-person Confluence ACL
        token_subject=_identity_key(claims),
        source_slug=source.id,
        target_slug=target.id if target is not None else None,
        platform=entry.key,
    )


def build_auth_context(
    claims: VerifiedClaims,
    registry: PlatformRegistry,
    catalog: ProductCatalog | None = None,
) -> AuthContext:
    # AUTH-1 / CIP-A2: gate on the ACTIVE view, not the verify-only by_issuer view. An inactive
    # platform's token verifies (token_verifier.by_issuer) but is not served here at all.
    entry = registry.platform_for(claims.issuer)
    if entry is None:
        raise InactivePlatformError(claims.issuer)

    # Directed-connection form (substep 9.3.1, Option A, ADR-directed-source-target-routing-labels): routes on source → target,
    # not the membership slots. Validated here and short-circuits the slot chain below.
    if claims.source_system is not None or claims.target_system is not None:
        return _build_directed_context(claims, entry, catalog)

    # The raw claimed value per slot role. Structured form: the context is authoritative (a
    # legacy claim riding beside it is ignored). Legacy form: the single integration claim is
    # one filled slot whose role the catalog decides after resolution (check 2).
    structured = claims.slots is not None
    raw_slots: dict[str, str] = {}
    if claims.slots is not None:
        for role in _SLOT_ROLES:
            value = getattr(claims.slots, role)
            if value is not None:
                raw_slots[role] = value

    if not raw_slots and (structured or claims.integration is None):
        # no business values / every slot empty -> general only (an empty slot never refuses),
        # still identified by the token subject; company_id carried for audit only.
        return AuthContext(
            company_id=claims.company_id,
            company_name=claims.company_name,
            integration=None,
            allowed_scopes=(),
            allowed_sources=_DEFAULT_SOURCES,
            principal=None,
            token_subject=_identity_key(claims),
            platform=entry.key,
        )

    catalog = catalog if catalog is not None else _default_catalog()

    # -- check 1 · shape --------------------------------------------------------------------
    raw_values = list(raw_slots.values()) if structured else [str(claims.integration)]
    for value in raw_values:
        if not _SLOT_VALUE_PATTERN.match(value):
            raise InvalidSlotValueError("slot value is not a short lowercase slug")
    if claims.company_id is None:
        raise InvalidSlotValueError("company_id is required when a slot is filled")

    # -- check 2 · membership against the catalog (fail closed: 400 before any search) -------
    # -- check 3 · role agreement (the product's catalog role matches the slot it sits in) ----
    filled: dict[str, str] = {}  # slot role -> canonical catalog id
    if structured:
        for role, value in raw_slots.items():
            canonicals = catalog.resolve(value)
            if not canonicals:
                raise UnknownIntegrationError(value)
            if len(canonicals) != 1:
                raise InvalidSlotValueError(f"{role} slot value expands to more than one product")
            filled[role] = canonicals[0]
        for role, canonical in filled.items():
            if catalog.products[canonical].role != role:
                raise InvalidSlotValueError(f"product '{canonical}' cannot fill the {role} slot")
    else:
        canonicals = catalog.resolve(str(claims.integration))
        if not canonicals:
            raise UnknownIntegrationError(claims.integration)
        # a legacy (possibly compound) value fills the slot matching each product's role;
        # catalog rule 5 guarantees an expansion never puts two products in one role.
        for canonical in canonicals:
            filled[catalog.products[canonical].role] = canonical

    # -- check 4 · vend rights (CIP-A1 generalized) -------------------------------------------
    # The issuing platform may only fill slots with products its allowed_integrations resolve
    # to — Data Hub vends the POS/PMS products it lists, Base (once registered) the Accounting
    # ones. Resolution runs on both sides so a trusted alias spelling never diverges.
    vend_set: set[str] = set()
    for allowed in entry.allowed_integrations:
        vend_set.update(catalog.resolve(allowed))
    for role, canonical in filled.items():
        if canonical not in vend_set:
            raise IntegrationNotAllowedError(
                f"platform {entry.key} may not assert '{canonical}' in the {role} slot"
            )

    # -- check 5 · launch allowlist (POS/PMS only — O4: the Accounting slot is inert) ---------
    for role in ("pos", "pms"):
        canonical = filled.get(role)
        if canonical is not None and canonical not in catalog.launch_allowlist.get(
            role, frozenset()
        ):
            raise SlotNotOnAllowlistError(
                f"{role} slot '{canonical}' is outside the launch allowlist"
            )

    # ADR-routing-labels-sole-content-axis: the knowledge-scope axis is retired. The slot checks above still gate WHICH
    # integration a token may assert (shape/membership/role/vend/allowlist — access, not content),
    # but no knowledge scope is derived; content is routed by the ADR-directed-source-target-routing-labels label axis. No base tag.
    return AuthContext(
        company_id=claims.company_id,
        company_name=claims.company_name,
        integration=None if structured else claims.integration,
        allowed_scopes=(),
        allowed_sources=_DEFAULT_SOURCES,
        principal=None,  # v1: embedded users have no per-person Confluence ACL
        token_subject=_identity_key(claims),
        slot_pos=filled.get("pos"),
        slot_pms=filled.get("pms"),
        slot_accounting=filled.get("accounting"),
        platform=entry.key,
    )
