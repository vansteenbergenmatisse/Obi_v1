"""The "Applies to" schema (panel mi-applies, substep 8.2.1) — plan.md §D.3.

Validates one authored applicability record into a typed, immutable value. The
record is authored as one or more standard "Applies to" tables in the page body
(the decided authoring approach — `docs/Final_docs/5-integration-context/
applies-to-authoring.md`); each table's field/value rows arrive here as one
mapping per rule. Parsing storage-format tables into these mappings is the
sync-side work of substep 8.2.2 — this module owns only the vocabulary and the
validation.

Five levels (§D.3): general · software · platform-interface · connection ·
workflow, plus optional variant requirements (feature, accounting flow,
version). Semantics that never bend here:

- **Explicit any.** The literal value ``any`` is allowed only where documented
  (a connection role side; directions). A MISSING field never becomes a
  wildcard — a missing required field raises with a named reason.
- **Loud, named failures.** Every rejection raises
  :class:`ApplicabilityValidationError` carrying a stable ``reason`` slug and a
  message naming the offending field or value. Unknown field names fail too —
  a silently dropped condition would silently widen the rule.
- **One vocabulary.** Products, roles, connection types and flow directions
  come from the product catalog (`app.platform.config.product_catalog`);
  platforms from the platform registry keys the caller supplies. Nothing here
  defines a second spelling.
- **No record ≠ empty record.** A page with no "Applies to" table keeps
  today's label-only behavior (the documented §D.11 default) and never reaches
  this module. An authored record with zero rules is malformed (loud).

Between rules: OR. Within a rule: AND on the same actual connection (§D.4 —
the matching itself is substep 8.2.3; this module only guarantees a rule can
never be half-stated).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.platform.config.product_catalog import VALID_PRODUCT_ROLES, ProductCatalog

# The explicit wildcard — the only spelling of "any", always authored, never implied.
ANY = "any"

# The five §D.3 levels, in design order.
APPLIES_TO_LEVELS = ("general", "software", "platform-interface", "connection", "workflow")

# §D.3 level 5 / §D.4: workflow connections bind on the shared product's instance
# and property ("the same Mews instance at the same property").
WORKFLOW_BINDINGS = ("same-instance", "same-property")

# §D.3 variant requirements: feature, accounting flow, version.
VARIANT_FIELDS = ("variant-feature", "variant-accounting-flow", "variant-version")

_CONNECTION_KEY_RE = re.compile(r"^connection-(\d+)$")

# Field names each level may carry (beyond the optional variants). Workflow
# role/direction fields are per-connection and matched by pattern.
_LEVEL_FIELDS: dict[str, frozenset[str]] = {
    "general": frozenset(),
    "software": frozenset({"product"}),
    "platform-interface": frozenset({"product", "platform"}),
    "connection": frozenset({"connection", "directions"} | VALID_PRODUCT_ROLES),
    "workflow": frozenset({"binding"}),
}
_WORKFLOW_FIELD_RE = re.compile(
    r"^connection-\d+(?:-(?:directions|" + "|".join(sorted(VALID_PRODUCT_ROLES)) + r"))?$"
)


class ApplicabilityValidationError(ValueError):
    """A named, loud validation failure: ``reason`` is a stable slug, the
    message names the offending field or value. The slug prefixes the printable
    form so the loud-at-sync surface (a failed job's recorded error, 8.2.2)
    carries the documented reason name, greppable as authored."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(f"{reason}: {message}")
        self.reason = reason


@dataclass(frozen=True)
class ConnectionSpec:
    """One required connection: the type, each role side, the flow directions.

    ``products`` maps every role the connection type joins to a canonical
    product id or the explicit ``any`` (sorted by role, as (role, value)
    pairs). ``directions`` is the explicit non-empty subset of the type's
    §D.2 directions (``any`` was expanded at validation)."""

    connection_type: str
    products: tuple[tuple[str, str], ...]
    directions: tuple[str, ...]


@dataclass(frozen=True)
class ApplicabilityRule:
    """One complete validated rule — all conditions AND together (§D.4)."""

    level: str
    product: str | None = None
    platform: str | None = None
    connections: tuple[ConnectionSpec, ...] = ()
    bindings: tuple[str, ...] = ()
    variants: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class AppliesTo:
    """The validated record of a page: one or more rules, OR between them."""

    rules: tuple[ApplicabilityRule, ...]


def _fail(reason: str, message: str) -> ApplicabilityValidationError:
    return ApplicabilityValidationError(reason, message)


def _pop(fields: dict[str, str], name: str) -> str:
    """Take a required field; missing → missing-field:<name>, blank → empty-value."""
    if name not in fields:
        raise _fail(f"missing-field:{name}", f'required field "{name}" is missing')
    return _pop_optional(fields, name)


def _pop_optional(fields: dict[str, str], name: str) -> str:
    value = fields.pop(name).strip()
    if not value:
        raise _fail("empty-value", f'field "{name}" is empty')
    return value


def _resolve_product(value: str, field: str, catalog: ProductCatalog) -> str:
    """One canonical product id for one field — never a guess, never a list."""
    canonical = catalog.resolve(value)
    if len(canonical) == 1:
        return canonical[0]
    if not canonical:
        raise _fail("unknown-product", f'field "{field}": {value!r} is not in the product catalog')
    raise _fail(
        "ambiguous-product",
        f'field "{field}": {value!r} expands to several products '
        f"({', '.join(canonical)}) and cannot fill one field",
    )


def _connection_spec(
    fields: dict[str, str], prefix: str, type_field: str, catalog: ProductCatalog
) -> ConnectionSpec:
    """Validate one connection block: the type, every role side, the directions.

    ``type_field`` names the field carrying the connection type ("connection"
    or "connection-<n>"); ``prefix`` prefixes the role/directions fields (""
    at connection level, "connection-<n>-" inside a workflow)."""
    type_key = _pop(fields, type_field)
    if type_key not in catalog.connection_types:
        raise _fail(
            "unknown-connection-type",
            f'field "{type_field}": {type_key!r} is not a connection type in the catalog',
        )

    products: list[tuple[str, str]] = []
    for role in sorted(catalog.connection_types[type_key]):
        field = f"{prefix}{role}"
        value = _pop(fields, field)
        if value == ANY:
            products.append((role, ANY))
            continue
        product_id = _resolve_product(value, field, catalog)
        actual_role = catalog.products[product_id].role
        if actual_role != role:
            raise _fail(
                "role-mismatch",
                f'field "{field}": {product_id!r} has role {actual_role!r}, not {role!r}',
            )
        products.append((role, product_id))

    directions_field = f"{prefix}directions"
    raw = _pop(fields, directions_field)
    allowed = catalog.connection_directions[type_key]
    if raw == ANY:
        directions = allowed
    else:
        directions = tuple(part.strip() for part in raw.split(",") if part.strip())
        for direction in directions:
            if direction not in allowed:
                raise _fail(
                    "unknown-direction",
                    f'field "{directions_field}": {direction!r} is not a direction of '
                    f"{type_key!r} (allowed: {', '.join(allowed)})",
                )
    return ConnectionSpec(connection_type=type_key, products=tuple(products), directions=directions)


def _workflow_connections(
    fields: dict[str, str], catalog: ProductCatalog
) -> tuple[ConnectionSpec, ...]:
    indices = sorted(
        int(m.group(1)) for key in list(fields) if (m := _CONNECTION_KEY_RE.match(key))
    )
    specs = tuple(
        _connection_spec(fields, f"connection-{n}-", f"connection-{n}", catalog) for n in indices
    )
    if len(specs) < 2:
        raise _fail(
            "too-few-connections",
            f"a workflow needs at least two connections (connection-1, connection-2, …); "
            f"got {len(specs)}",
        )
    # Linked means a CONCRETE shared product appears in more than one
    # connection — the explicit any never counts as the link.
    concrete: dict[str, int] = {}
    for spec in specs:
        for _, value in set(spec.products):
            if value != ANY:
                concrete[value] = concrete.get(value, 0) + 1
    if not any(count >= 2 for count in concrete.values()):
        raise _fail(
            "unlinked-connections",
            "workflow connections share no concrete product — they are not linked",
        )
    return specs


def validate_rule(
    fields: Mapping[str, str],
    catalog: ProductCatalog,
    known_platforms: frozenset[str],
) -> ApplicabilityRule:
    """Validate one authored rule (one "Applies to" table) into a typed rule.

    ``fields`` is the table's field/value rows. ``known_platforms`` is the
    platform vocabulary (the platform registry's keys) for level 3. Raises
    :class:`ApplicabilityValidationError` with a named reason on the first
    violation."""
    remaining = {str(k): str(v) for k, v in fields.items()}

    level = _pop(remaining, "level")
    if level not in APPLIES_TO_LEVELS:
        raise _fail(
            "unknown-level",
            f"level {level!r} is not one of: {', '.join(APPLIES_TO_LEVELS)}",
        )

    # Unknown field names fail FIRST, by name — a typo'd condition must never
    # surface as a confusing missing-field error, let alone be dropped.
    allowed = _LEVEL_FIELDS[level]
    unknown_names = sorted(
        key
        for key in remaining
        if key not in allowed
        and key not in VARIANT_FIELDS
        and not (level == "workflow" and _WORKFLOW_FIELD_RE.match(key))
    )
    if unknown_names:
        raise _fail(
            "unknown-field",
            f"unknown field(s) for level {level!r}: {', '.join(unknown_names)} — a dropped "
            f"condition would silently widen the rule",
        )

    variants: list[tuple[str, str]] = []
    for variant_field in VARIANT_FIELDS:
        if variant_field in remaining:
            value = _pop_optional(remaining, variant_field)
            if value == ANY:
                raise _fail(
                    "any-not-allowed",
                    f'field "{variant_field}": a variant requirement of "any" means no '
                    f"requirement — omit the optional field instead",
                )
            variants.append((variant_field.removeprefix("variant-"), value))

    product: str | None = None
    platform: str | None = None
    connections: tuple[ConnectionSpec, ...] = ()
    bindings: tuple[str, ...] = ()

    if level in ("software", "platform-interface"):
        value = _pop(remaining, "product")
        if value == ANY:
            raise _fail(
                "any-not-allowed",
                'field "product": guidance for any product is authored as level "general", '
                "never as a product wildcard",
            )
        product = _resolve_product(value, "product", catalog)
        if level == "platform-interface":
            platform = _pop(remaining, "platform")
            if platform not in known_platforms:
                raise _fail(
                    "unknown-platform",
                    f'field "platform": {platform!r} is not a known platform '
                    f"(known: {', '.join(sorted(known_platforms))})",
                )
    elif level == "connection":
        connections = (_connection_spec(remaining, "", "connection", catalog),)
    elif level == "workflow":
        raw_bindings = _pop(remaining, "binding")
        bindings = tuple(part.strip() for part in raw_bindings.split(",") if part.strip())
        for binding in bindings:
            if binding not in WORKFLOW_BINDINGS:
                raise _fail(
                    "unknown-binding",
                    f'field "binding": {binding!r} is not one of: {", ".join(WORKFLOW_BINDINGS)}',
                )
        connections = _workflow_connections(remaining, catalog)

    if remaining:
        unknown = ", ".join(sorted(remaining))
        raise _fail(
            "unknown-field",
            f"unknown field(s) for level {level!r}: {unknown} — a dropped condition "
            f"would silently widen the rule",
        )
    return ApplicabilityRule(
        level=level,
        product=product,
        platform=platform,
        connections=connections,
        bindings=bindings,
        variants=tuple(variants),
    )


def validate_applies_to(
    rules: Sequence[Mapping[str, str]],
    catalog: ProductCatalog,
    known_platforms: frozenset[str],
) -> AppliesTo:
    """Validate a whole authored record: one mapping per rule, OR between rules.

    An empty sequence is malformed ("empty-record") — the label-only default
    belongs to pages with NO record, never to a botched one."""
    if not rules:
        raise _fail(
            "empty-record",
            'an "Applies to" record with zero rules is malformed — remove the record to '
            "keep label-only behavior, or author at least one rule",
        )
    return AppliesTo(
        rules=tuple(validate_rule(fields, catalog, known_platforms) for fields in rules)
    )


def applies_to_payload(record: AppliesTo) -> list[dict[str, object]]:
    """Serialize a validated record to the JSON shape stamped on chunks (8.2.2).

    One dict per rule, OR between them; fields a level does not carry are omitted
    (never a null pretending to be a wildcard). Deterministic: connection products
    are already role-sorted by validation, so equal records serialize equal — the
    restamp route compares this payload against the stored JSONB to detect a
    metadata edit."""
    payload: list[dict[str, object]] = []
    for rule in record.rules:
        out: dict[str, object] = {"level": rule.level}
        if rule.product is not None:
            out["product"] = rule.product
        if rule.platform is not None:
            out["platform"] = rule.platform
        if rule.connections:
            out["connections"] = [
                {
                    "type": spec.connection_type,
                    "products": dict(spec.products),
                    "directions": list(spec.directions),
                }
                for spec in rule.connections
            ]
        if rule.bindings:
            out["bindings"] = list(rule.bindings)
        if rule.variants:
            out["variants"] = dict(rule.variants)
        payload.append(out)
    return payload
