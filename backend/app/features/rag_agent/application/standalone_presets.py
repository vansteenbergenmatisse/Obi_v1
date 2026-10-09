"""Backend-validated standalone test presets (panel mi-presets, substep 8.4.1).

The standalone/test environment (plan.md §D.8) picks a pretend customer setup from a fixed list
and Obi treats it exactly like a real one — SAME contract, knowledge base, metadata rules,
pipeline, reranker and prompt as Base and Data Hub. A preset expresses ONLY a verified-context
shape (a company_id plus the three §D.13 slots); it is NOT a parallel code path and never widens
access (never-bend rules 2–3 — a preset is an input to the one authorization context, never a way
around the gate).

"Backend-validated" means exactly this: `validate_preset` runs a preset's context through the ONE
real gate, `build_auth_context` (substep 8.1.3). A preset that would be refused — a bad slug, a
product in the wrong slot role, or a filled POS/PMS slot outside the launch allowlist — raises the
same `AuthContextError` subclass a real note would, so a preset can never express a context the
backend would refuse. The gate's five slot checks are reused wholesale; nothing is duplicated.

The standalone environment is the test harness itself, so by definition it may simulate any
configured customer: `standalone_registry` builds a single active vend authority covering every
catalog product (gate check 4, vend rights, then trivially passes for catalog products). The other
four checks — shape, membership, role agreement, and the launch allowlist — do the real
validating and run verbatim through `build_auth_context`.

The preset LIST lives in `knowledge-base/config/standalone_presets.json` (a data concern, beside
`platforms.json` and `product_catalog.json`); this module reads it, and the frontend selector reads
the same file — one source, exactly the platforms.json pattern. Threading the simulated context
into the outgoing request/token is a later substep (8.4.2); here the presets are only the
backend-validated artifact and the selector's source."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.features.rag_agent.application.auth_context import AuthContext, build_auth_context
from app.features.rag_agent.server.token_verifier import ContextSlots, VerifiedClaims
from app.platform.config.platforms import PlatformEntry, PlatformRegistry
from app.platform.config.product_catalog import ProductCatalog, load_product_catalog

# The standalone environment's internal issuer key. NOT a real trusted issuer and never a verified
# signature: the presets flow through `build_auth_context` (which only looks the issuer up in the
# registry), never through token verification. Deliberately not a URL/secret.
STANDALONE_ISSUER = "obi-standalone"

# backend/app/features/rag_agent/application -> repo root is 5 levels up; the file lives beside
# platforms.json / product_catalog.json under knowledge-base/config/.
DEFAULT_PRESETS_PATH = (
    Path(__file__).resolve().parents[5] / "knowledge-base" / "config" / "standalone_presets.json"
)


@dataclass(frozen=True, slots=True)
class PresetSlots:
    """The three §D.13 slots a preset fills — one canonical catalog id each, or None for empty."""

    pos: str | None
    pms: str | None
    accounting: str | None


@dataclass(frozen=True, slots=True)
class StandalonePreset:
    """One pretend customer setup in the standalone/test environment (§D.8). `flow_type` is a
    display label (a §D.2 flow direction, or `three_system` for the three-system workflow); the
    gate-meaningful content is `company_id` + `slots`."""

    id: str
    label: str
    flow_type: str
    company_id: str
    slots: PresetSlots


def _parse_preset(raw: dict) -> StandalonePreset:
    slots = raw["slots"]
    return StandalonePreset(
        id=str(raw["id"]),
        label=str(raw["label"]),
        flow_type=str(raw["flow_type"]),
        company_id=str(raw["company_id"]),
        slots=PresetSlots(
            pos=slots.get("pos"),
            pms=slots.get("pms"),
            accounting=slots.get("accounting"),
        ),
    )


@lru_cache(maxsize=1)
def load_standalone_presets(path: Path = DEFAULT_PRESETS_PATH) -> tuple[StandalonePreset, ...]:
    """The committed standalone preset list, read once per process. The gate re-validates each
    preset in `validate_preset`; this reader only maps JSON to the frozen dataclasses."""
    data = json.loads(path.read_text())
    return tuple(_parse_preset(raw) for raw in data["presets"])


def standalone_registry(
    *,
    base_registry: PlatformRegistry | None = None,
    catalog: ProductCatalog | None = None,
) -> PlatformRegistry:
    """The standalone environment's one active platform — the test harness, which may simulate any
    configured customer, so it vends every catalog product (gate check 4). `base_registry`, when
    supplied, lends its real integration→scope map so a validated preset's `allowed_scopes` match
    production; absent, scope assembly simply yields general-only (validation only needs the gate
    not to refuse — scope assembly never raises)."""
    catalog = catalog if catalog is not None else load_product_catalog()
    scopes: dict[str, tuple[str, ...]] = {}
    if base_registry is not None:
        for product_id in catalog.products:
            mapped = base_registry.scopes_for(product_id)
            if mapped is not None:
                scopes[product_id] = tuple(mapped)
    entry = PlatformEntry(
        key="obi-standalone",
        issuer=STANDALONE_ISSUER,
        jwks_url=STANDALONE_ISSUER,
        domains=(),
        lifetime_minutes=60,
        algs=("RS256",),
        active=True,
        allowed_integrations=tuple(sorted(catalog.products)),
    )
    return PlatformRegistry(_by_issuer={STANDALONE_ISSUER: entry}, _scopes=scopes)


def validate_preset(
    preset: StandalonePreset,
    registry: PlatformRegistry,
    *,
    catalog: ProductCatalog | None = None,
) -> AuthContext:
    """Run the preset's context through the ONE real gate. Returns the frozen `AuthContext` a real
    note would produce, or raises the same `AuthContextError` subclass the backend would raise for
    a note the gate refuses — so a preset can never express a context the backend would refuse."""
    claims = VerifiedClaims(
        issuer=STANDALONE_ISSUER,
        subject=f"standalone-preset:{preset.id}",
        company_id=preset.company_id,
        company_name=None,
        integration=None,
        slots=ContextSlots(
            pos=preset.slots.pos,
            pms=preset.slots.pms,
            accounting=preset.slots.accounting,
        ),
    )
    return build_auth_context(claims, registry, catalog)
