"""Platform + integration registry for Obi embed (Phase 11.1c, ADR-0014).

The JWT 'integration' claim carries the platform KEY (e.g. "mews"); this registry
maps that key to the live obi-*-test knowledge scopes and holds the trusted-issuer
verification config. Validated at startup: every mapped scope must exist in
config/knowledge_scopes.json; 'classified' is never mappable; empty platforms stops
startup outside local (allow_empty=False).

Lives at the repo-root ``config/`` beside ``knowledge_scopes.json`` — one global place
an operator edits directly, readable from either app (mirrors knowledge_scopes.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_GENERAL = "obi-general-test"
_FORBIDDEN = frozenset({"classified"})

# backend/app/platform/config/platforms.py -> repo root is 4 levels up.
DEFAULT_PLATFORMS_PATH = Path(__file__).resolve().parents[4] / "config" / "platforms.json"


@dataclass(frozen=True, slots=True)
class PlatformEntry:
    key: str
    issuer: str
    jwks_url: str
    domains: tuple[str, ...]
    lifetime_minutes: int
    algs: tuple[str, ...]
    active: bool


@dataclass(frozen=True, slots=True)
class PlatformRegistry:
    _by_issuer: dict[str, PlatformEntry]
    _scopes: dict[str, tuple[str, ...]]

    def by_issuer(self, iss: str) -> PlatformEntry | None:
        return self._by_issuer.get(iss)

    def scopes_for(self, integration: str) -> list[str] | None:
        scopes = self._scopes.get(integration)
        return list(scopes) if scopes is not None else None

    def active_domains(self) -> list[str]:
        out: list[str] = []
        for e in self._by_issuer.values():
            if e.active:
                out.extend(e.domains)
        return sorted(set(out))


def load_platform_registry(
    platforms_path: Path,
    recognized_scopes: frozenset[str],
    *,
    allow_empty: bool,
) -> PlatformRegistry:
    data = json.loads(platforms_path.read_text())
    platforms = data.get("platforms", {})
    integrations = data.get("integrations", {})

    if not platforms and not allow_empty:
        raise ValueError("platforms.json has no platforms outside local")

    by_issuer: dict[str, PlatformEntry] = {}
    for key, raw in platforms.items():
        entry = PlatformEntry(
            key=key,
            issuer=str(raw["issuer"]),
            jwks_url=str(raw["jwks_url"]),
            domains=tuple(str(d) for d in raw.get("domains", [])),
            lifetime_minutes=int(raw["lifetime_minutes"]),
            algs=tuple(str(a) for a in raw["algs"]),
            active=bool(raw.get("active", False)),
        )
        if "HS256" in entry.algs:
            raise ValueError(f"platform {key}: HS256 is forbidden")
        by_issuer[entry.issuer] = entry

    scopes: dict[str, tuple[str, ...]] = {}
    for integration, slugs in integrations.items():
        resolved: set[str] = set()
        for slug in slugs:
            s = str(slug).strip().lower()
            if s in _FORBIDDEN:
                raise ValueError(f"integration {integration}: '{s}' is never mappable")
            if s not in recognized_scopes:
                raise ValueError(f"integration {integration}: '{s}' not in knowledge_scopes.json")
            resolved.add(s)
        resolved.add(_GENERAL)
        scopes[integration] = tuple(sorted(resolved))

    return PlatformRegistry(_by_issuer=by_issuer, _scopes=scopes)
