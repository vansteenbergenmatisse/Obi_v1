"""Platform + integration registry for Obi embed (PLAN 11.1c; validated by substep 1.2.3).

The JWT 'integration' claim carries the platform KEY (e.g. "mews"); this registry maps that key
to the live obi-*-test knowledge scopes and holds the trusted-issuer verification config.

Validated at startup, after the tag map, rules in order, each error naming the offending entry:
every mapped scope exists in knowledge_scopes.json; 'classified' is never mappable; the general
scope is added by the loader, never listed by hand; lifetime_minutes sits within 1..1440; every
signing alg is on the allow-list (RS256, ES256); every platform's allowed_integrations value is a
real integration (a key of the integrations map — gap CIP-A1); an empty registry, or one with zero
active platforms, stops startup outside local (allow_empty=False). Outside offline (offline=False)
an ACTIVE platform must further be a real production trusted issuer — an https issuer/jwks on a real
host, never a TODO/PLACEHOLDER string, a .local host, or ANY loopback address (localhost/
*.localhost, the whole 127.0.0.0/8 block, 0.0.0.0 or IPv6 ::1 — the same set the frontend csp.ts
strips, gap BIT-A-R1), and no loopback CSP domain (gap CFG-02/AUTHRT-1 + CFG-04); offline/local
keeps loading platforms.local.json's test-* issuers and localhost domains unchanged.

Lives at ``knowledge-base/config/platforms.json`` beside ``knowledge_scopes.json`` — one global
place an operator edits directly, readable from either app (mirrors knowledge_scopes.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

_GENERAL = "obi-general-test"
_FORBIDDEN = frozenset({"classified"})
_ALLOWED_ALGS = frozenset({"RS256", "ES256"})
_MIN_LIFETIME = 1
_MAX_LIFETIME = 1440

# gap CFG-02/AUTHRT-1 + CFG-04: outside offline/local, an ACTIVE platform is a fully-trusted JWT
# issuer whose domains seed the embed frame's CSP, so it must be a real, https, non-localhost third
# party — never a test/placeholder issuer. These are the markers of a not-yet-real entry.
_PLACEHOLDER_MARKERS = ("TODO", "PLACEHOLDER")

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
    # gap CIP-A1: the integration CLAIM VALUES this platform is trusted to assert. A self-serving
    # platform lists only its own integration (e.g. mews -> ["mews"]); a hub (datahub) lists the
    # product integrations it may vend. build_auth_context rejects a verified token whose
    # `integration` is not in the issuing platform's list, so a trusted issuer can no longer assert
    # any integration and reach another tenant's scopes. Empty () => the platform may assert no
    # integration (general-only tokens only). Every listed value is validated at load to exist in
    # the global `integrations` map (loader below), naming the offender.
    allowed_integrations: tuple[str, ...] = ()


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


def _url_host(value: str) -> str:
    """Lowercased host of a URL, or "" when it has no parseable host (e.g. a placeholder
    string like "TODO until 4.x")."""
    return (urlsplit(value).hostname or "").lower()


def _domain_host(domain: str) -> str:
    """Lowercased host of a bare ``host[:port]`` CSP domain entry (these are stored without a
    scheme, e.g. "localhost:3000" / "app.mews.com" / "[::1]:3000"). Mirrors the frontend's
    ``isLocalhostDomain`` port/bracket handling (``frontend/src/features/embed/csp.ts``) so an IPv6
    literal is not mangled: bracketed IPv6 (``[::1]:3000``) yields the text inside the brackets; a
    bare IPv6 literal (more than one ``:``) is left whole; a plain ``host[:port]`` drops one
    trailing ``:port``."""
    host = domain.strip().lower()
    if not host:
        return host
    if host.startswith("["):
        close = host.find("]")
        return host[1:] if close == -1 else host[1:close]
    if host.count(":") > 1:
        return host
    return host.split(":", 1)[0]


def _is_ipv4_loopback_host(host: str) -> bool:
    """A ``127.0.0.0/8`` IPv4 loopback literal — ``127.`` followed by three numeric octets, each
    0–255. Deliberately a strict numeric-IPv4 check so a hostname that merely starts with ``127.``
    (e.g. ``127.example.com``) is NOT treated as loopback (gap BIT-A-R1). Mirrors csp.ts
    ``isIpv4LoopbackHost``."""
    octets = host.split(".")
    if len(octets) != 4:
        return False
    if not all(o.isdigit() and len(o) <= 3 and int(o) <= 255 for o in octets):
        return False
    return octets[0] == "127"


def _is_loopback_host(host: str) -> bool:
    """True when a bare host resolves to the local loopback — the FULL set the frontend's
    ``isLocalhostDomain`` (``frontend/src/features/embed/csp.ts``) treats as localhost, kept in
    step with it (gap BIT-A-R1) so none of it can become a trusted issuer host or embedder origin
    outside local/dev:

    - ``localhost`` and any ``*.localhost``;
    - the whole ``127.0.0.0/8`` block (``127.x.x.x`` with valid octets), not just ``127.0.0.1``;
    - the ``0.0.0.0`` wildcard-bind address;
    - IPv6 loopback ``::1``, whether bare (``::1``) or arriving bracketed (``[::1]``).

    A real hostname like ``127.example.com`` is NOT over-matched (see ``_is_ipv4_loopback_host``).
    """
    h = host.strip().lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    if h == "localhost" or h.endswith(".localhost"):
        return True
    if h == "0.0.0.0":  # noqa: S104 — matching the bind-all address, not binding to it
        return True
    if h == "::1":
        return True
    return _is_ipv4_loopback_host(h)


def _reject_untrusted_active_platform(entry: PlatformEntry) -> None:
    """gap CFG-02/AUTHRT-1 + CFG-04 (loopback set widened for gap BIT-A-R1) — refuse an ACTIVE
    platform that is not a real production trusted issuer, naming the offending entry. Applied by
    ``load_platform_registry`` only when ``offline`` is False; local/test/ci keep loading
    ``platforms.local.json`` with its ``test-*`` issuers and localhost domains unchanged
    (``dev``/``development`` are NOT offline — see ``settings.py`` ``_OFFLINE_ENVS``). An active
    entry's issuer/jwks must be an https URL on a real host — not a ``TODO``/``PLACEHOLDER`` string,
    not a ``.local`` host, and not any loopback address (``localhost``/``*.localhost``, the whole
    ``127.0.0.0/8`` block, ``0.0.0.0``, or IPv6 ``::1``) — and none of its CSP domains may be a
    loopback address. The loopback set is the SAME one the frontend's ``isLocalhostDomain`` strips
    (``frontend/src/features/embed/csp.ts``); see ``_is_loopback_host``."""
    key = entry.key
    for label, value in (("issuer", entry.issuer), ("jwks_url", entry.jwks_url)):
        upper = value.upper()
        for marker in _PLACEHOLDER_MARKERS:
            if marker in upper:
                raise ValueError(
                    f"platform {key}: active {label} '{value}' is a placeholder "
                    f"({marker}); not a real trusted issuer outside local"
                )
        if not value.startswith("https://"):
            raise ValueError(
                f"platform {key}: active {label} '{value}' is not https; refused outside local"
            )
        host = _url_host(value)
        if _is_loopback_host(host):
            raise ValueError(
                f"platform {key}: active {label} host '{host}' is a localhost/loopback address; "
                f"refused outside local"
            )
        if host.endswith(".local"):
            raise ValueError(
                f"platform {key}: active {label} host '{host}' ends in .local; "
                f"refused outside local"
            )
    for domain in entry.domains:
        if _is_loopback_host(_domain_host(domain)):
            raise ValueError(
                f"platform {key}: active CSP domain '{domain}' is a localhost/loopback address; "
                f"refused outside local"
            )


def load_platform_registry(
    platforms_path: Path,
    recognized_scopes: frozenset[str],
    *,
    allow_empty: bool,
    offline: bool = True,
) -> PlatformRegistry:
    """Load and validate the registry. ``allow_empty`` tolerates an empty / all-inactive registry
    (local). ``offline`` (the ``ENV``-derived offline/local signal, see ``Settings.is_offline_env``)
    tolerates test/placeholder/localhost/non-https ACTIVE issuers and localhost CSP domains; when
    False (a real deployment) each active entry must be a real https trusted issuer — gap
    CFG-02/AUTHRT-1 + CFG-04.

    ``offline`` defaults True (permissive) because the ONLY production caller is
    ``Settings.platform_registry``, which always passes the real, ENV-derived signal explicitly
    (offline=False in a real deployment) — that is where the production trust boundary is enforced.
    The default preserves the historical direct-load contract that local test fixtures rely on; a
    caller wanting production-strict checking must opt in with ``offline=False``."""
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
        # gap CIP-A1: every integration this platform is trusted to assert must be a real
        # integration (a key of the global integrations map), or startup stops naming the offender.
        allowed_integrations = tuple(str(v) for v in raw.get("allowed_integrations", []))
        for value in allowed_integrations:
            if value not in integrations:
                raise ValueError(
                    f"platform {key}: allowed_integration '{value}' not in integrations map"
                )
        entry = PlatformEntry(
            key=key,
            issuer=str(raw["issuer"]),
            jwks_url=str(raw["jwks_url"]),
            domains=tuple(str(d) for d in raw.get("domains", [])),
            lifetime_minutes=lifetime,
            algs=algs,
            active=bool(raw.get("active", False)),
            allowed_integrations=allowed_integrations,
        )
        by_issuer[entry.issuer] = entry

    if not allow_empty and not any(e.active for e in by_issuer.values()):
        raise ValueError("platforms.json has no active platform outside local")

    if not offline:
        for entry in by_issuer.values():
            if entry.active:
                _reject_untrusted_active_platform(entry)

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
