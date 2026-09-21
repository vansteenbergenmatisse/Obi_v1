"""Platform + integration registry for Obi embed (PLAN 11.1c; validated by substep 1.2.3).

The JWT 'integration' claim carries the platform KEY (e.g. "mews"); this registry maps that key
to the live obi-*-test knowledge scopes and holds the trusted-issuer verification config.

Validated at startup, after the tag map, rules in order, each error naming the offending entry:
every mapped scope exists in knowledge_scopes.json; 'classified' is never mappable; the general
scope is added by the loader, never listed by hand; lifetime_minutes sits within 1..1440; every
signing alg is on the allow-list (RS256, ES256); an empty registry, or one with zero active
platforms, stops startup outside local (allow_empty=False).

Lives at ``knowledge-base/config/platforms.json`` beside ``knowledge_scopes.json`` — one global
place an operator edits directly, readable from either app (mirrors knowledge_scopes.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_GENERAL = "obi-general-test"
_FORBIDDEN = frozenset({"classified"})
_ALLOWED_ALGS = frozenset({"RS256", "ES256"})
_MIN_LIFETIME = 1
_MAX_LIFETIME = 1440

# backend/app/platform/config/platforms.py -> repo root is 4 levels up; the file lives beside
# knowledge_scopes.json under knowledge-base/config/ (relocated in substep 1.2.3).
DEFAULT_PLATFORMS_PATH = (
    Path(__file__).resolve().parents[4] / "knowledge-base" / "config" / "platforms.json"
)


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
        """The entry for an issuer, active or not — inactive platforms still verify a token that
        arrives (PLAN 11.1c). Token verification uses this; access gating uses platform_for."""
        return self._by_issuer.get(iss)

    def platform_for(self, iss: str) -> PlatformEntry | None:
        """The ACTIVE entry for an issuer, or None. An inactive platform is not served here."""
        entry = self._by_issuer.get(iss)
        return entry if entry is not None and entry.active else None

    def scopes_for(self, integration: str) -> list[str] | None:
        scopes = self._scopes.get(integration)
        return list(scopes) if scopes is not None else None

    def allowed_scopes_for(self, integration: str) -> set[str] | None:
        """The integration's scopes as a set, general already included, or None if unmapped."""
        scopes = self._scopes.get(integration)
        return set(scopes) if scopes is not None else None

    def active_platforms(self) -> list[str]:
        """Sorted keys of every active platform — the boot log's registry summary."""
        return sorted(e.key for e in self._by_issuer.values() if e.active)

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
        lifetime = int(raw["lifetime_minutes"])
        if not _MIN_LIFETIME <= lifetime <= _MAX_LIFETIME:
            raise ValueError(
                f"platform {key}: lifetime_minutes {lifetime} outside "
                f"{_MIN_LIFETIME}..{_MAX_LIFETIME}"
            )
        algs = tuple(str(a) for a in raw["algs"])
        for alg in algs:
            if alg not in _ALLOWED_ALGS:
                raise ValueError(
                    f"platform {key}: algorithm '{alg}' not in allow-list (RS256, ES256)"
                )
        entry = PlatformEntry(
            key=key,
            issuer=str(raw["issuer"]),
            jwks_url=str(raw["jwks_url"]),
            domains=tuple(str(d) for d in raw.get("domains", [])),
            lifetime_minutes=lifetime,
            algs=algs,
            active=bool(raw.get("active", False)),
        )
        by_issuer[entry.issuer] = entry

    if not allow_empty and not any(e.active for e in by_issuer.values()):
        raise ValueError("platforms.json has no active platform outside local")

    scopes: dict[str, tuple[str, ...]] = {}
    for integration, slugs in integrations.items():
        resolved: set[str] = set()
        for slug in slugs:
            s = str(slug).strip().lower()
            if s in _FORBIDDEN:
                raise ValueError(f"integration {integration}: '{s}' is never mappable")
            if s == _GENERAL:
                raise ValueError(
                    f"integration {integration}: '{_GENERAL}' is added by the loader, "
                    f"never listed by hand"
                )
            if s not in recognized_scopes:
                raise ValueError(f"integration {integration}: '{s}' not in knowledge_scopes.json")
            resolved.add(s)
        resolved.add(_GENERAL)
        scopes[integration] = tuple(sorted(resolved))

    return PlatformRegistry(_by_issuer=by_issuer, _scopes=scopes)
