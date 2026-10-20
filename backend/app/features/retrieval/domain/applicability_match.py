"""Deterministic applicability matching (panel mi-match, substep 8.2.3) — plan.md §D.4.

One pure function decides whether a chunk's stamped applicability payload (the exact
JSON shape ``applies_to_payload`` writes to ``chunk.applicability``, 8.2.2) matches this
customer's verified context: ``match_applicability(context, payload, catalog)`` →
:class:`MatchResult`. No I/O, no clock, no randomness — 8.3.1 mirrors this predicate in
SQL inside the search function and 8.3.4 surfaces the reasons as per-slot attribution,
so every decision here carries an inspectable reason slug.

The semantics of record (§D.4, panel mi-match):

- **AND within one rule, on the same actual connection.** Every condition of one rule —
  both role sides and every required flow direction — must hold on ONE connection the
  customer actually has. "Both products exist somewhere in the account" never satisfies
  a connection rule.
- **OR between rules.** The first matching rule wins; its index and reason are reported.
- **Launch pairs derive from filled slots only.** POS+PMS filled → the POS–PMS
  connection (both §D.2 directions); PMS+Accounting filled → the PMS–Accounting
  connection. A direct POS–Accounting pair is NEVER derived from three filled slots —
  it needs a real connection record (§D.13/O1), which the launch token cannot carry
  (legacy-three-slot-context-contract §5.2); :class:`CustomerContext.connections` is where such
  records
  land when a future context carries them.
- **Incomplete context asks, never broadens.** A rule blocked only by configuration the
  context does not carry (an empty slot, an unknown host platform, an unverifiable
  variant, a connection record the token cannot express) reports it in
  ``MatchResult.missing`` so the answer can serve the applicable general guidance and
  ask — a KNOWN-but-different configuration reports nothing to ask for.
- **Workflow bindings.** ``same-instance``/``same-property`` hold by construction for
  slot-derived connections (one company token, one property, one product per slot — the
  shared product IS the same slot value). A real connection record carries no
  instance/property data at launch, so when bindings are present only slot-derived
  connections may satisfy a workflow rule (never-broaden; revisited when §D.1's richer
  context record lands).

A chunk with NO record (``applicability`` NULL) keeps label-only behavior and never
reaches this function (§D.11 compatibility default — 8.3.1 encodes that in SQL).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.features.ingestion import ANY
from app.platform.config.product_catalog import ProductCatalog

# The §D.13 launch rule: only these role pairs derive a connection from filled slots.
# {pos, accounting} is deliberately absent — a direct POS–Accounting pair needs a real
# connection record (O1). The connection-type KEYS still come from the catalog.
_DERIVABLE_ROLE_SETS = (frozenset({"pos", "pms"}), frozenset({"pms", "accounting"}))


@dataclass(frozen=True, slots=True)
class ConnectionRecord:
    """One connection the customer actually has.

    ``products`` maps each role the connection joins to a CONCRETE canonical product id
    (sorted (role, id) pairs — never ``any``); ``directions`` lists only the flow
    directions actually enabled (§D.2). ``derived`` marks a launch pair computed from
    filled slots by :func:`derive_connections`; a real record from a future context
    keeps the default ``False``."""

    connection_type: str
    products: tuple[tuple[str, str], ...]
    directions: tuple[str, ...]
    derived: bool = False


@dataclass(frozen=True, slots=True)
class CustomerContext:
    """The verified customer context the matcher sees: the three §D.13 slots (one
    canonical id or None each, exactly the gate's ``AuthContext`` slot fields), the
    host platform key (platforms.json; None when unknown), and any REAL connection
    records — empty at launch, the token cannot express one (legacy-three-slot-context-contract
    §9)."""

    slot_pos: str | None = None
    slot_pms: str | None = None
    slot_accounting: str | None = None
    platform: str | None = None
    connections: tuple[ConnectionRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchResult:
    """The inspectable decision. ``reason`` is the matched rule's slug (``general``,
    ``slot:<role>``, ``platform-interface:<role>``, ``connection:<type>``,
    ``workflow``) or ``no-match``; ``rule_index`` names the OR-rule that matched;
    ``rule_reasons`` carries one slug per evaluated rule (why it matched or failed);
    ``missing`` lists configuration the context lacks (``slot:<role>``, ``platform``,
    ``connection:<type>``, ``variant:<name>``) — the ask, never a broadening."""

    matched: bool
    reason: str
    rule_index: int | None = None
    rule_reasons: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _RuleOutcome:
    """One rule's evaluation: a matched reason OR a failure slug plus the ask."""

    reason: str | None
    fail: str = ""
    missing: tuple[str, ...] = field(default=())


def _slot(context: CustomerContext, role: str) -> str | None:
    return {
        "pos": context.slot_pos,
        "pms": context.slot_pms,
        "accounting": context.slot_accounting,
    }.get(role)


def derive_connections(
    context: CustomerContext, catalog: ProductCatalog
) -> tuple[ConnectionRecord, ...]:
    """The launch pairs: one derived connection per derivable catalog type whose every
    role slot is filled with a product that supports that connection family. All of the
    type's §D.2 directions are enabled (legacy-three-slot-context-contract §5.2: "both
    directions")."""
    out: list[ConnectionRecord] = []
    for type_key in sorted(catalog.connection_types):
        roles = catalog.connection_types[type_key]
        if roles not in _DERIVABLE_ROLE_SETS:
            continue
        products = tuple(sorted((role, _slot(context, role)) for role in roles))
        if any(value is None for _, value in products):
            continue
        if any(
            type_key not in catalog.products[value].connection_types
            for _, value in products
            if value is not None
        ):
            continue
        out.append(
            ConnectionRecord(
                connection_type=type_key,
                products=tuple((role, value) for role, value in products if value is not None),
                directions=catalog.connection_directions[type_key],
                derived=True,
            )
        )
    return tuple(out)


@dataclass(frozen=True, slots=True)
class EligibilityParams:
    """The matcher-derived values the 8.3.1 SQL predicate binds (panel mi-filter).

    ``products`` holds the FILLED slot values whose catalog role matches the slot they sit
    in (exactly what :func:`_eval_product` would accept — a product in the wrong slot never
    counts); ``platform`` is the verified host platform key or None (an unknown platform
    never matches a platform-interface rule, never broadens); ``connections`` is
    :func:`derive_connections` plus any real records — the pairs the company actually has."""

    products: tuple[str, ...]
    platform: str | None
    connections: tuple[ConnectionRecord, ...]


def eligibility_params(context: CustomerContext, catalog: ProductCatalog) -> EligibilityParams:
    """Derive the one search's eligibility bind values from the verified context.

    Pure and deterministic like the matcher it mirrors: same slot-role check as
    ``_eval_product``, same connection derivation as ``match_applicability`` (derived launch
    pairs first, then real records). 8.3.1's SQL consumes these so the database decides
    eligibility with the exact §D.4 vocabulary — one semantics, two executors."""
    products: list[str] = []
    for role in ("pos", "pms", "accounting"):
        value = _slot(context, role)
        if value is None:
            continue
        entry = catalog.products.get(value)
        if entry is not None and entry.role == role:
            products.append(value)
    return EligibilityParams(
        products=tuple(products),
        platform=context.platform,
        connections=derive_connections(context, catalog) + tuple(context.connections),
    )


def _satisfies(spec: Mapping[str, object], conn: ConnectionRecord) -> bool:
    """AND on the same actual connection: the type, every role side (an explicit
    ``any`` binds to the connection's concrete product), every required direction."""
    if spec.get("type") != conn.connection_type:
        return False
    have = dict(conn.products)
    products = spec.get("products")
    if not isinstance(products, Mapping):
        return False
    for role, want in products.items():
        actual = have.get(str(role))
        if actual is None or (want != ANY and want != actual):
            return False
    directions = spec.get("directions")
    if not isinstance(directions, Sequence) or isinstance(directions, str):
        return False
    return all(direction in conn.directions for direction in directions)


def _spec_failure(
    spec: Mapping[str, object],
    context: CustomerContext,
    connections: Sequence[ConnectionRecord],
    catalog: ProductCatalog,
) -> _RuleOutcome:
    """Why no connection satisfied ``spec`` — distinguishing a KNOWN different
    configuration (no ask) from configuration the context lacks (the ask)."""
    type_key = str(spec.get("type"))
    if any(conn.connection_type == type_key for conn in connections):
        return _RuleOutcome(None, f"no-matching-connection:{type_key}")
    roles = catalog.connection_types.get(type_key, frozenset())
    empty = tuple(sorted(role for role in roles if _slot(context, role) is None))
    if empty:
        return _RuleOutcome(
            None,
            "slot-empty:" + ",".join(empty),
            tuple(f"slot:{role}" for role in empty),
        )
    return _RuleOutcome(None, f"needs-real-connection:{type_key}", (f"connection:{type_key}",))


def _eval_product(context: CustomerContext, product: str, catalog: ProductCatalog) -> _RuleOutcome:
    entry = catalog.products.get(product)
    if entry is None:
        return _RuleOutcome(None, f"unknown-product:{product}")
    have = _slot(context, entry.role)
    if have == product:
        return _RuleOutcome(f"slot:{entry.role}")
    if have is None:
        return _RuleOutcome(None, f"slot-empty:{entry.role}", (f"slot:{entry.role}",))
    return _RuleOutcome(None, "product-not-in-context")


def _distinct_assignment(
    specs: Sequence[Mapping[str, object]],
    connections: Sequence[ConnectionRecord],
    used: frozenset[int],
) -> bool:
    """Each workflow spec on its own actual connection (AND within the rule)."""
    if not specs:
        return True
    head, *tail = specs
    for index, conn in enumerate(connections):
        if index in used:
            continue
        if _satisfies(head, conn) and _distinct_assignment(tail, connections, used | {index}):
            return True
    return False


def _eval_rule(
    context: CustomerContext,
    rule: Mapping[str, object],
    connections: tuple[ConnectionRecord, ...],
    catalog: ProductCatalog,
) -> _RuleOutcome:
    level = rule.get("level")
    if level == "general":
        outcome = _RuleOutcome("general")
    elif level == "software":
        outcome = _eval_product(context, str(rule.get("product")), catalog)
    elif level == "platform-interface":
        outcome = _eval_product(context, str(rule.get("product")), catalog)
        if outcome.reason is not None:
            role = outcome.reason.removeprefix("slot:")
            if context.platform is None:
                outcome = _RuleOutcome(None, "platform-unknown", ("platform",))
            elif context.platform != rule.get("platform"):
                outcome = _RuleOutcome(None, "platform-mismatch")
            else:
                outcome = _RuleOutcome(f"platform-interface:{role}")
    elif level == "connection":
        specs = rule.get("connections")
        if not isinstance(specs, Sequence) or not specs:
            return _RuleOutcome(None, "malformed-rule")
        spec = specs[0]
        if not isinstance(spec, Mapping):
            return _RuleOutcome(None, "malformed-rule")
        if any(_satisfies(spec, conn) for conn in connections):
            outcome = _RuleOutcome(f"connection:{spec.get('type')}")
        else:
            outcome = _spec_failure(spec, context, connections, catalog)
    elif level == "workflow":
        specs_raw = rule.get("connections")
        if not isinstance(specs_raw, Sequence) or len(specs_raw) < 2:
            return _RuleOutcome(None, "malformed-rule")
        specs = [spec for spec in specs_raw if isinstance(spec, Mapping)]
        if len(specs) != len(specs_raw):
            return _RuleOutcome(None, "malformed-rule")
        # Bindings hold by construction only for slot-derived connections (module
        # docstring); with bindings present, real records cannot satisfy the rule.
        candidates = (
            tuple(conn for conn in connections if conn.derived)
            if rule.get("bindings")
            else connections
        )
        if _distinct_assignment(specs, candidates, frozenset()):
            outcome = _RuleOutcome("workflow")
        else:
            for spec in specs:
                if not any(_satisfies(spec, conn) for conn in candidates):
                    outcome = _spec_failure(spec, context, candidates, catalog)
                    break
            else:
                outcome = _RuleOutcome(None, "no-distinct-connections")
    else:
        return _RuleOutcome(None, f"unknown-level:{level}")

    if outcome.reason is None:
        return outcome
    variants = rule.get("variants")
    if isinstance(variants, Mapping) and variants:
        names = sorted(str(name) for name in variants)
        # The launch context carries no variant facts (feature / accounting flow /
        # version) — an unverifiable requirement asks, it never assumes (§D.4).
        return _RuleOutcome(
            None,
            "variant-unknown:" + ",".join(names),
            tuple(f"variant:{name}" for name in names),
        )
    return outcome


def match_applicability(
    context: CustomerContext,
    payload: Sequence[Mapping[str, object]],
    catalog: ProductCatalog,
) -> MatchResult:
    """Decide whether one stamped applicability payload matches this customer.

    ``payload`` is the list ``applies_to_payload`` stamped (one dict per rule, OR
    between rules). Returns the first matching rule's reason, or a no-match carrying
    every per-rule failure slug and the deduplicated ask (``missing``)."""
    connections = derive_connections(context, catalog) + tuple(context.connections)
    rule_reasons: list[str] = []
    missing: list[str] = []
    for index, rule in enumerate(payload):
        outcome = _eval_rule(context, rule, connections, catalog)
        if outcome.reason is not None:
            rule_reasons.append(outcome.reason)
            return MatchResult(
                matched=True,
                reason=outcome.reason,
                rule_index=index,
                rule_reasons=tuple(rule_reasons),
            )
        rule_reasons.append(outcome.fail)
        for item in outcome.missing:
            if item not in missing:
                missing.append(item)
    return MatchResult(
        matched=False,
        reason="no-match",
        rule_reasons=tuple(rule_reasons),
        missing=tuple(missing),
    )


# The Citation contract's attribution vocabulary (§D.13 keuze 3, panel mi-attrib / 8.1.2): the
# only values that may ever reach the widget. Defined here (retrieval produces it; retrieval must
# not import rag_agent, which would cycle) with the SAME values as `rag_agent.schemas`'s
# `CitationAttribution`, whose Literal re-validates on Citation construction (one more fail-closed
# gate). These are the customer's OWN context categories — never a product id, company id, scope,
# or platform — so attribution can leak nothing (rule 10).
AttributionValue = Literal["general", "pos", "pms", "accounting", "pair"]

_SLOT_ATTRIBUTION: dict[str, AttributionValue] = {
    "pos": "pos",
    "pms": "pms",
    "accounting": "accounting",
}


def attribution_for_reason(reason: str | None) -> AttributionValue | None:
    """Collapse the matcher's single reason slug to the Citation attribution enum (panel
    mi-attrib, substep 8.3.4) — ``general | pos | pms | accounting | pair``, or ``None``.

    This maps the reason :func:`match_applicability` ALREADY selected (OR between rules, first
    match wins) — it never re-evaluates matching. Precedence of record: a connection/workflow
    reason collapses to ``pair`` (the connection the customer actually has, not either member
    slot), so a pair is attributed as a pair, never as one of the slots that compose it
    (pair > slot). A slot or platform-interface reason maps to its named slot; ``general`` to
    ``general``. A no-match, a per-rule failure slug, an unknown slug, the empty string, or
    ``None`` (a label-only chunk, or the no-context / eval path) all yield ``None`` — no
    attribution is shown, byte-compatible with the pre-8.3.4 wire. The output is only ever one
    of the five fixed values, so it can carry nothing beyond the customer's own context."""
    if not reason:
        return None
    if reason == "general":
        return "general"
    if reason == "workflow" or reason.startswith("connection:"):
        return "pair"
    if reason.startswith("slot:") or reason.startswith("platform-interface:"):
        return _SLOT_ATTRIBUTION.get(reason.split(":", 1)[1])
    return None
