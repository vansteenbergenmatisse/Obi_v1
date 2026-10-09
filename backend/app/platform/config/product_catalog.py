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
  7. the reserved names never appear: `classified`, `general`/`obi-general-test`, any
     `obi-*` scope-tag spelling (scope tags live in knowledge_scopes.json only);
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

# Rule 7: names reserved for the scope-tag registry (knowledge_scopes.json), never products.
_RESERVED_EXACT = frozenset({"classified", "general", "obi-general-test"})
_RESERVED_PREFIX = "obi-"


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
