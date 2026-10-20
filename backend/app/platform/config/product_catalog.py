"""Loads the central product catalog (panel mi-catalog, substep 8.1.1) from its config file.

`knowledge-base/config/product_catalog.json` is THE single canonical registry of software
products — nothing else in the repo may define a product id, role, alias or connection type
(docs/Final_docs/5-integration-context/catalog.md). Like `knowledge_scopes.py`, this is a
content registry an operator edits directly, read at startup and validated fail-fast: the
catalog decides which token slot values exist, so a bad entry stops the backend before it can
mis-scope anyone, each failure naming the offending entry.

The 8 validation rules (catalog.md §3), enforced in order:
  1. every canonical id and alias is a short lowercase slug — no silent lowercasing;
  2. canonical ids unique; aliases unique across the whole file (per-product aliases plus
     legacy_aliases keys) and never colliding with any canonical id;
  3. every role is one of pos | pms | accounting;
  4. every connection_types entry on a product is a key of the top-level connection_types,
     and the product's role appears in that connection type's roles;
  5. every legacy_aliases value is a non-empty list of existing canonical ids, at most one
     per role (an expansion can never put two products in one slot);
  6. launch_allowlist lists only existing canonical ids whose role matches the list they
     sit in;
  6b. enabled_sources (ADR-0023, optional) lists only existing canonical ids (flat/global, not
     role-keyed); absent ⇒ every product enabled, so the enablement gate stays inert;
  7. the reserved names never appear: `classified`, `general`, any `obi-*` spelling
     (reserved for the routing-label axis — e.g. `obi-general` — never a product id);
  8. cross-check against platforms.json: every key of its `integrations` map resolves to a
     canonical id (or alias) in this catalog.

Resolution (catalog.md §4) happens once, before any validation or allowlist check, at the
gate: canonical id first, then per-product alias, then legacy compound expansion; anything
else resolves to nothing — fail closed, 400 before any search, never a fuzzy match.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.platform.config.platforms import DEFAULT_PLATFORMS_PATH

# backend/app/platform/config/product_catalog.py -> repo root is 4 levels up.
DEFAULT_PRODUCT_CATALOG_PATH = (
    Path(__file__).resolve().parents[4] / "knowledge-base" / "config" / "product_catalog.json"
)

# The three §D.13 slot roles — one role per product at launch.
VALID_PRODUCT_ROLES = frozenset({"pos", "pms", "accounting"})

# Rule 1: a short lowercase slug — letters, digits, hyphens.
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Flow directions use underscore tokens (§D.2: pos_to_pms, pms_to_accounting, …).
_DIRECTION_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")

# Rule 7: reserved names, never product ids. `obi-*` (the routing-label namespace, e.g.
# obi-general) is covered by the prefix; `classified`/`general` are reserved exact names.
_RESERVED_EXACT = frozenset({"classified", "general"})
_RESERVED_PREFIX = "obi-"

# Option A routing labels (ADR-0020 D0/D4): the content-routing axis. These are
# Confluence LABELS, not products — the reserved-name rules above gate product ids,
# never these boxes. The four ordered boxes a directed source→target connection sees are
# obi-general, {source.slug}-general, {target.slug}-general, {source.slug}-to-{target.kind}.
GENERAL_LABEL = "obi-general"
_GENERAL_SUFFIX = "-general"
_DIRECTION_SEP = "-to-"


def _normalize_system_name(value: str) -> str:
    """Case-fold and collapse whitespace for the lenient routing resolver (plan Step 1:
    "match on name, slug or alias; ignore case and extra spaces"). Distinct from the strict
    gate resolver ``ProductCatalog.resolve``, which never lowercases or fuzzy-matches."""
    return " ".join(value.split()).casefold()


@dataclass(frozen=True)
class Product:
    """One catalog entry: the canonical id and what the gate needs to know about it."""

    id: str
    label: str
    role: str
    aliases: tuple[str, ...]
    connection_types: tuple[str, ...]


@dataclass(frozen=True)
class ProductCatalog:
    """The validated catalog: product lookups, alias resolution and the launch allowlist."""

    products: dict[str, Product]
    connection_types: dict[str, frozenset[str]]  # type key -> the roles it joins
    legacy_aliases: dict[str, tuple[str, ...]]
    launch_allowlist: dict[str, frozenset[str]]  # role -> allowed canonical ids
    alias_to_id: dict[str, str]
    connection_directions: dict[str, tuple[str, ...]]  # type key -> its §D.2 flow directions
    # ADR-0023 (source-enablement visibility gate, supersedes ADR-0022's target gate): the flat,
    # global set of canonical product ids Obi supports as a directed-connection SOURCE. A source is
    # enabled iff it is in this set; the target is never checked. Materialized
    # from the optional top-level `enabled_sources` list; ABSENT in the file ⇒ every product id
    # (backward-compatible — the gate's enablement check then never fires). Not role-keyed, and
    # independent of `launch_allowlist`. A direct construction (not via the loader) defaults to the
    # empty set — fail closed, never fail open — but the loader always materializes the real set.
    enabled_sources: frozenset[str] = frozenset()

    def resolve(self, value: str) -> tuple[str, ...]:
        """Resolve one incoming value to canonical ids (catalog.md §4).

        Canonical id first, then per-product alias (one-to-one), then legacy compound
        expansion (one-to-many). An unmatched value returns the empty tuple — fail
        closed; the gate turns that into a 400 before any search. Never lowercases,
        never fuzzy-matches.
        """
        if value in self.products:
            return (value,)
        canonical = self.alias_to_id.get(value)
        if canonical is not None:
            return (canonical,)
        expansion = self.legacy_aliases.get(value)
        if expansion is not None:
            return expansion
        return ()

    def resolve_system(self, name: str) -> Product | None:
        """Resolve one directed-connection endpoint to a product (panel mi-route, ADR-0020
        D4/D7). Matches the canonical id, any per-product alias, or the display name,
        ignoring case and surrounding/collapsed whitespace. An unmatched value returns
        ``None`` — a clear miss, never a fuzzy match and never a wildcard.

        This is the routing-side resolver: lenient about case and spacing because a
        partner-supplied system name is less controlled than a token slot value. The strict
        gate resolver ``resolve`` is left unchanged.
        """
        key = _normalize_system_name(name)
        if not key:
            return None
        for product in self.products.values():
            if _normalize_system_name(product.id) == key:
                return product
            if _normalize_system_name(product.label) == key:
                return product
            if any(_normalize_system_name(alias) == key for alias in product.aliases):
                return product
        return None

    def build_labels(self, source: str, target: str) -> list[str]:
        """Turn a directed ``source → target`` connection into exactly the four ordered
        Confluence label boxes (ADR-0020 D4, plan "The routing rule"):
        ``obi-general``, ``{source.slug}-general``, ``{target.slug}-general``,
        ``{source.slug}-to-{target.kind}`` — where the slug is the resolved product's
        canonical id and the kind is the TARGET product's role (pos/pms/accounting).

        An unknown source yields ``[obi-general]`` alone — never a wildcard (ADR-0020 chat-start
        step 5 / panel mi-route). A known source with an unknown target yields the two boxes the
        source alone can fill, ``[obi-general, {source.slug}-general]`` (ADR-0023: a source can
        have hundreds of targets, so the target is assumed supported, never a direction box for a
        target we cannot classify). Direction is primary:
        ``build_labels("toast", "mews")`` ≠ ``build_labels("mews", "toast")``.
        """
        src = self.resolve_system(source)
        tgt = self.resolve_system(target)
        if src is None:
            return [GENERAL_LABEL]
        if tgt is None:
            return [GENERAL_LABEL, f"{src.id}{_GENERAL_SUFFIX}"]
        return [
            GENERAL_LABEL,
            f"{src.id}{_GENERAL_SUFFIX}",
            f"{tgt.id}{_GENERAL_SUFFIX}",
            f"{src.id}{_DIRECTION_SEP}{tgt.role}",
        ]

    def is_valid_label(self, label: str) -> bool:
        """True iff ``label`` is a well-formed routing label (panel mi-route). The three
        valid forms are ``obi-general``; ``{slug}-general``; and
        ``{slug}-to-(pos|pms|accounting)`` — where the slug is a canonical id in this
        catalog. Anything else (``toast-to-pmss``, ``toast-to-hotel``, an unknown slug, a
        bare ``general`` or bare slug) is rejected.
        """
        if label == GENERAL_LABEL:
            return True
        if label.endswith(_GENERAL_SUFFIX):
            return label[: -len(_GENERAL_SUFFIX)] in self.products
        if _DIRECTION_SEP in label:
            slug, _, kind = label.rpartition(_DIRECTION_SEP)
            return slug in self.products and kind in VALID_PRODUCT_ROLES
        return False

    def all_routing_labels(self) -> frozenset[str]:
        """Every well-formed routing label this catalog recognizes (ADR-0021) — the ingestion
        membership set. ``obi-general`` plus, for each product, ``{slug}-general`` and
        ``{slug}-to-{kind}`` for each valid target kind. A published page is in the index iff it
        carries at least one of these and is not ``classified`` (replaces the retired
        knowledge-scope membership set)."""
        labels: set[str] = {GENERAL_LABEL}
        for slug in self.products:
            labels.add(f"{slug}{_GENERAL_SUFFIX}")
            for kind in VALID_PRODUCT_ROLES:
                labels.add(f"{slug}{_DIRECTION_SEP}{kind}")
        return frozenset(labels)


def _require_slug(path: Path, kind: str, name: str) -> None:
    if not _SLUG_RE.match(name):
        raise ValueError(f"{path}: {kind} {name!r} must be a lowercase slug (a-z, 0-9, hyphens)")


def _require_not_reserved(path: Path, kind: str, name: str) -> None:
    if name in _RESERVED_EXACT or name.startswith(_RESERVED_PREFIX):
        raise ValueError(
            f"{path}: {kind} {name!r} is a reserved name — scope tags and the reserved "
            f"classified/general names live in knowledge_scopes.json, never in the catalog"
        )


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """json object hook: a duplicated key anywhere in the file is an error, not a silent
    last-one-wins (rule 2 for canonical ids; the same strictness file-wide)."""
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key {key!r}")
        out[key] = value
    return out


def load_product_catalog(
    path: Path = DEFAULT_PRODUCT_CATALOG_PATH,
    platforms_path: Path = DEFAULT_PLATFORMS_PATH,
) -> ProductCatalog:
    """Validate the catalog file at startup and return the parsed catalog.

    A failing rule raises ``ValueError`` before ``create_app`` finishes (wired through the
    ``Settings`` model validator, the knowledge_scopes pattern), so a malformed catalog
    exits the process non-zero rather than serving one request against wrong products.
    """
    try:
        data = json.loads(path.read_text(), object_pairs_hook=_reject_duplicate_keys)
    except ValueError as exc:  # includes the duplicate-key hook
        raise ValueError(f"{path}: {exc}") from exc

    raw_products: dict[str, dict] = data["products"]
    raw_connection_types: dict[str, dict] = data["connection_types"]
    raw_legacy: dict[str, list[str]] = data.get("legacy_aliases", {})
    raw_allowlist: dict[str, list[str]] = data.get("launch_allowlist", {})
    # Task 5: the enablement list is optional. `None` sentinel distinguishes "absent" (⇒ all
    # products enabled, materialized below) from an explicit "[]" (⇒ nothing enabled).
    raw_enabled_sources: list[str] | None = data.get("enabled_sources")

    # Rules 1 + 7 over every canonical id, alias and legacy key — reject before indexing.
    for product_id, entry in raw_products.items():
        _require_slug(path, "product id", product_id)
        _require_not_reserved(path, "product id", product_id)
        for alias in entry.get("aliases", []):
            _require_slug(path, f"alias of {product_id!r}", str(alias))
            _require_not_reserved(path, f"alias of {product_id!r}", str(alias))
    for legacy_key in raw_legacy:
        _require_slug(path, "legacy alias", legacy_key)
        _require_not_reserved(path, "legacy alias", legacy_key)
    for type_key in raw_connection_types:
        _require_slug(path, "connection type", type_key)
        _require_not_reserved(path, "connection type", type_key)

    # Rule 2: aliases unique across the WHOLE file and never colliding with a canonical id.
    # (Duplicate canonical ids / legacy keys are already a duplicate-key parse error above.)
    alias_to_id: dict[str, str] = {}
    for product_id, entry in raw_products.items():
        for alias in entry.get("aliases", []):
            alias = str(alias)
            if alias in raw_products:
                raise ValueError(
                    f"{path}: alias {alias!r} (of {product_id!r}) collides with a canonical id"
                )
            if alias in alias_to_id:
                raise ValueError(
                    f"{path}: alias {alias!r} is listed more than once "
                    f"({alias_to_id[alias]!r} and {product_id!r})"
                )
            alias_to_id[alias] = product_id
    for legacy_key in raw_legacy:
        if legacy_key in raw_products or legacy_key in alias_to_id:
            raise ValueError(
                f"{path}: legacy alias {legacy_key!r} collides with a canonical id or alias"
            )

    # Rule 3: every role is one of the three slot roles.
    for product_id, entry in raw_products.items():
        role = str(entry["role"])
        if role not in VALID_PRODUCT_ROLES:
            raise ValueError(
                f"{path}: product {product_id!r} has role {role!r}; "
                f"must be one of {sorted(VALID_PRODUCT_ROLES)}"
            )

    connection_types = {
        type_key: frozenset(str(r) for r in entry["roles"])
        for type_key, entry in raw_connection_types.items()
    }

    # Each connection type carries its §D.2 flow directions — the ONE direction
    # vocabulary (the applicability schema validates against it, never a copy).
    connection_directions: dict[str, tuple[str, ...]] = {}
    for type_key, entry in raw_connection_types.items():
        directions = tuple(str(d) for d in entry["directions"])
        if not directions:
            raise ValueError(f"{path}: connection type {type_key!r} defines no directions")
        if len(set(directions)) != len(directions):
            raise ValueError(f"{path}: connection type {type_key!r} repeats a direction")
        for direction in directions:
            if not _DIRECTION_RE.match(direction):
                raise ValueError(
                    f"{path}: connection type {type_key!r} direction {direction!r} must be "
                    f"a lowercase underscore token (a-z, 0-9, underscores)"
                )
        connection_directions[str(type_key)] = directions

    # Rule 4: every connection_types entry exists and joins the product's own role.
    for product_id, entry in raw_products.items():
        role = str(entry["role"])
        for type_key in entry.get("connection_types", []):
            type_key = str(type_key)
            if type_key not in connection_types:
                raise ValueError(
                    f"{path}: product {product_id!r} names unknown connection type {type_key!r}"
                )
            if role not in connection_types[type_key]:
                raise ValueError(
                    f"{path}: product {product_id!r} (role {role!r}) cannot join connection "
                    f"type {type_key!r} (roles {sorted(connection_types[type_key])})"
                )

    # Rule 5: legacy expansions — non-empty, existing ids, at most one per role.
    legacy_aliases: dict[str, tuple[str, ...]] = {}
    for legacy_key, expansion in raw_legacy.items():
        ids = tuple(str(i) for i in expansion)
        if not ids:
            raise ValueError(f"{path}: legacy alias {legacy_key!r} expands to nothing")
        roles_seen: set[str] = set()
        for canonical in ids:
            if canonical not in raw_products:
                raise ValueError(
                    f"{path}: legacy alias {legacy_key!r} names unknown product {canonical!r}"
                )
            role = str(raw_products[canonical]["role"])
            if role in roles_seen:
                raise ValueError(
                    f"{path}: legacy alias {legacy_key!r} puts two {role!r} products in one slot"
                )
            roles_seen.add(role)
        legacy_aliases[legacy_key] = ids

    # Rule 6: the launch allowlist lists only existing ids whose role matches its list.
    launch_allowlist: dict[str, frozenset[str]] = {}
    for role, ids in raw_allowlist.items():
        for canonical in ids:
            canonical = str(canonical)
            if canonical not in raw_products:
                raise ValueError(
                    f"{path}: launch_allowlist[{role!r}] names unknown product {canonical!r}"
                )
            actual = str(raw_products[canonical]["role"])
            if actual != role:
                raise ValueError(
                    f"{path}: launch_allowlist[{role!r}] names {canonical!r} "
                    f"whose role is {actual!r}"
                )
        launch_allowlist[str(role)] = frozenset(str(i) for i in ids)

    # Rule 6b (Task 5): `enabled_sources` lists only existing canonical ids — mirrors the rule-6
    # allowlist loop. ABSENT ⇒ every product is enabled (backward compatible); present ⇒ exactly
    # the listed ids (an empty list enables nothing). A role mismatch is NOT checked: enablement
    # is a flat, global axis, not role-keyed.
    if raw_enabled_sources is None:
        enabled_sources = frozenset(raw_products)
    else:
        for canonical in raw_enabled_sources:
            if str(canonical) not in raw_products:
                raise ValueError(
                    f"{path}: enabled_sources names unknown product {str(canonical)!r}"
                )
        enabled_sources = frozenset(str(i) for i in raw_enabled_sources)

    products = {
        product_id: Product(
            id=product_id,
            label=str(entry["label"]),
            role=str(entry["role"]),
            aliases=tuple(str(a) for a in entry.get("aliases", [])),
            connection_types=tuple(str(t) for t in entry.get("connection_types", [])),
        )
        for product_id, entry in raw_products.items()
    }
    catalog = ProductCatalog(
        products=products,
        connection_types=connection_types,
        legacy_aliases=legacy_aliases,
        launch_allowlist=launch_allowlist,
        alias_to_id=alias_to_id,
        connection_directions=connection_directions,
        enabled_sources=enabled_sources,
    )

    # Rule 8: every platforms.json integration key resolves here — the two files may
    # never disagree on what an integration claim value means.
    integrations: dict[str, list[str]] = json.loads(platforms_path.read_text())["integrations"]
    for integration_key in integrations:
        if not catalog.resolve(integration_key):
            raise ValueError(
                f"{path}: platforms.json integration key {integration_key!r} resolves to no "
                f"catalog id or alias"
            )

    return catalog
