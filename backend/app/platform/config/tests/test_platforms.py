"""Unit tests for the Obi platform + integration registry loader (substep 1.2.3, panel cm-config).

One test per validation rule, each proving the loader raises and names the offending entry, plus
the three the substep names by hand: the real relocated file loads; allowed_scopes_for adds the
general scope; an inactive platform is not served by platform_for. Bad cases are temp JSON files;
the real-file test reads knowledge-base/config/platforms.json through DEFAULT_PLATFORMS_PATH.
"""

import json
from pathlib import Path

import pytest

from app.platform.config.knowledge_scopes import load_recognized_knowledge_scopes
from app.platform.config.platforms import (
    DEFAULT_PLATFORMS_PATH,
    _is_ipv4_loopback_host,
    _is_loopback_host,
    load_platform_registry,
)

RECOGNIZED = frozenset(
    {"obi-general-test", "obi-mews-test", "obi-toast-test", "obi-operacloud-test"}
)


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "platforms.json"
    p.write_text(json.dumps(data))
    return p


def _platform(*, active: bool = True, **over) -> dict:
    entry = {
        "issuer": "https://ex.test",
        "jwks_url": "https://ex.test/j",
        "domains": ["ex.test"],
        "lifetime_minutes": 60,
        "algs": ["RS256"],
        "active": active,
    }
    entry.update(over)
    return entry


def _data(*, platforms: dict | None = None, integrations: dict | None = None) -> dict:
    return {
        "platforms": {"mews": _platform()} if platforms is None else platforms,
        "integrations": {"mews": ["obi-mews-test"]} if integrations is None else integrations,
    }


# --- one test per rule (six) -------------------------------------------------


def test_platforms_unknown_tag_in_integration_stops_startup(tmp_path):
    """panel cm-config · substep 1.2.3
    A scope not in knowledge_scopes.json stops startup, naming the integration."""
    p = _write(tmp_path, _data(integrations={"mews": ["obi-not-a-real-scope"]}))
    with pytest.raises(ValueError, match="mews") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False)
    assert "not in knowledge_scopes" in str(exc.value)


def test_platforms_classified_never_mappable(tmp_path):
    """panel cm-config · substep 1.2.3
    'classified' anywhere in the integration map stops startup, naming the integration."""
    p = _write(tmp_path, _data(integrations={"mews": ["classified"]}))
    with pytest.raises(ValueError, match="classified") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False)
    assert "mews" in str(exc.value)


def test_platforms_general_never_listed_by_hand(tmp_path):
    """panel cm-config · substep 1.2.3
    Hand-listing the general scope stops startup — the loader adds it, it is never written in."""
    p = _write(tmp_path, _data(integrations={"mews": ["obi-mews-test", "obi-general-test"]}))
    with pytest.raises(ValueError, match="by hand") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False)
    assert "mews" in str(exc.value)


def test_platforms_lifetime_minutes_out_of_range_stops_startup(tmp_path):
    """panel cm-config · substep 1.2.3
    lifetime_minutes must sit within 1..1440 inclusive, else startup stops naming the platform."""
    for bad in (0, 1441):
        p = _write(tmp_path, _data(platforms={"mews": _platform(lifetime_minutes=bad)}))
        with pytest.raises(ValueError, match="lifetime_minutes") as exc:
            load_platform_registry(p, RECOGNIZED, allow_empty=False)
        assert "mews" in str(exc.value)


def test_platforms_alg_outside_allowlist_stops_startup(tmp_path):
    """panel cm-config · substep 1.2.3
    Any signing alg outside the allow-list (RS256, ES256) stops startup, naming the platform."""
    p = _write(tmp_path, _data(platforms={"mews": _platform(algs=["HS256"])}))
    with pytest.raises(ValueError, match="allow-list") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False)
    assert "mews" in str(exc.value)


def test_platforms_no_active_platform_outside_local_stops_startup(tmp_path):
    """panel cm-config · substep 1.2.3
    Outside local, a registry with entries but zero active stops startup; local tolerates it."""
    data = _data(platforms={"mews": _platform(active=False)})
    p = _write(tmp_path, data)
    with pytest.raises(ValueError, match="no active platform"):
        load_platform_registry(p, RECOGNIZED, allow_empty=False)
    # local (allow_empty=True): the same file loads without raising.
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=True)
    assert reg.active_domains() == []


# --- the three the substep names by hand -------------------------------------


def test_platforms_real_file_loads(tmp_path):
    """panel cm-config · substep 1.2.3
    The real knowledge-base/config/platforms.json loads under the real scopes in strict mode.

    Updated for gap CFG-02: this now passes offline=True. The committed file's only active
    platform (datahub) still carries TODO placeholder issuer/jwks, which the CFG-02 trust guard
    refuses outside offline (proven by test_platforms_active_placeholder_issuer_refused_outside_
    offline). Loading the real file therefore only succeeds in an offline/local env until datahub
    gets a real https issuer — which is exactly the guard doing its job, not a weakening."""
    reg = load_platform_registry(
        DEFAULT_PLATFORMS_PATH,
        load_recognized_knowledge_scopes(),
        allow_empty=False,
        offline=True,
    )
    # did not raise -> at least one active platform is present (datahub).
    assert reg.allowed_scopes_for("mews") == {"obi-mews-test", "obi-general-test"}


def test_platforms_allowed_scopes_adds_general(tmp_path):
    """panel cm-config · substep 1.2.3
    allowed_scopes_for returns the integration's tag plus the always-present general scope."""
    p = _write(tmp_path, _data(integrations={"mews": ["obi-mews-test"]}))
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False)
    assert reg.allowed_scopes_for("mews") == {"obi-mews-test", "obi-general-test"}


def test_platforms_inactive_not_served(tmp_path):
    """panel cm-config · substep 1.2.3
    platform_for returns None for an inactive platform, though it stays in the issuer index."""
    platforms = {
        "mews": _platform(issuer="https://app.mews.com"),
        "toast": _platform(issuer="https://pos.toasttab.com", active=False),
    }
    p = _write(tmp_path, _data(platforms=platforms, integrations={"mews": ["obi-mews-test"]}))
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False)
    assert reg.platform_for("https://pos.toasttab.com") is None
    assert reg.platform_for("https://app.mews.com") is not None
    # still indexed for token verification (inactive-still-verify, PLAN 11.1c).
    assert reg.by_issuer("https://pos.toasttab.com") is not None


# --- kept: existing-API coverage still used by the token verifier / auth context ---


def test_platforms_maps_platform_key_to_live_slugs(tmp_path):
    """panel cm-config · substep 1.2.3
    by_issuer / scopes_for / active_domains resolve a live platform key to its slugs."""
    p = _write(
        tmp_path,
        _data(
            platforms={"mews": _platform(issuer="https://app.mews.com", domains=["app.mews.com"])},
            integrations={"mews": ["obi-mews-test"]},
        ),
    )
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False)
    entry = reg.by_issuer("https://app.mews.com")
    assert entry is not None
    assert entry.key == "mews"
    assert reg.scopes_for("mews") == ["obi-general-test", "obi-mews-test"]
    assert reg.scopes_for("unknown") is None
    assert reg.active_domains() == ["app.mews.com"]


def test_platforms_empty_registry_stops_startup_when_not_allowed(tmp_path):
    """panel cm-config · substep 1.2.3
    An empty platforms map stops startup outside local."""
    p = _write(tmp_path, {"platforms": {}, "integrations": {}})
    with pytest.raises(ValueError, match="no platforms"):
        load_platform_registry(p, RECOGNIZED, allow_empty=False)


def test_platforms_empty_registry_allowed_locally(tmp_path):
    """panel cm-config · substep 1.2.3
    Local (allow_empty=True) tolerates an empty registry."""
    p = _write(tmp_path, {"platforms": {}, "integrations": {}})
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=True)
    assert reg.active_domains() == []


# --- gap CFG-02 / AUTHRT-1: an untrusted ACTIVE platform is refused OUTSIDE offline --------------
# An active entry is a fully-trusted JWT issuer whose domains seed the embed frame CSP. Outside
# offline it must be a real, https, non-localhost third party — never a test/placeholder issuer.
# Every case below is gated on offline=False; the two regression tests prove offline=True (the
# local embed test flow) is untouched.


def test_platforms_active_localhost_issuer_refused_outside_offline(tmp_path):
    """gap CFG-02/AUTHRT-1 · an ACTIVE platform whose issuer host is localhost is a fake trusted
    issuer in production — refused when offline=False, naming the entry; allowed when offline."""
    plat = {"acme": _platform(issuer="https://localhost", jwks_url="https://ex.test/j")}
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert "localhost" in str(exc.value)
    # offline (the local embed test flow) tolerates it.
    load_platform_registry(p, RECOGNIZED, allow_empty=True, offline=True)


def test_platforms_active_dotlocal_jwks_refused_outside_offline(tmp_path):
    """gap CFG-02 · an ACTIVE platform whose jwks host ends .local is refused outside offline."""
    plat = {"acme": _platform(issuer="https://ex.test", jwks_url="https://acme.local/j")}
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert ".local" in str(exc.value)


def test_platforms_active_placeholder_issuer_refused_outside_offline(tmp_path):
    """gap CFG-02 · an ACTIVE platform with a TODO/PLACEHOLDER issuer (the committed datahub
    shape) is refused outside offline, naming the entry."""
    plat = {"datahub": _platform(issuer="TODO until 4.x", jwks_url="TODO until 4.x", domains=[])}
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="datahub") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert "placeholder" in str(exc.value).lower()


def test_platforms_active_non_https_issuer_refused_outside_offline(tmp_path):
    """gap CFG-02 · an ACTIVE platform with a non-https issuer is refused outside offline."""
    plat = {
        "acme": _platform(issuer="http://acme.example.com", jwks_url="https://acme.example.com/j")
    }
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert "https" in str(exc.value)


def test_platforms_active_localhost_domain_refused_outside_offline(tmp_path):
    """gap CFG-04 · a localhost CSP domain on an ACTIVE entry must never reach the production
    frame-ancestors — refused at load when offline=False, naming the entry."""
    plat = {
        "acme": _platform(
            issuer="https://acme.example.com",
            jwks_url="https://acme.example.com/j",
            domains=["app.acme.example.com", "localhost:3000"],
        )
    }
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert "localhost" in str(exc.value)


def test_platforms_inactive_untrusted_entry_allowed_outside_offline(tmp_path):
    """gap CFG-02 · the guard only touches ACTIVE entries — an INACTIVE placeholder/localhost
    entry (the committed mews/toast/opera-cloud shape) still loads outside offline."""
    plat = {
        "acme": _platform(issuer="https://acme.example.com", jwks_url="https://acme.example.com/j"),
        "ph": _platform(issuer="PLACEHOLDER", jwks_url="PLACEHOLDER", domains=[], active=False),
    }
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert reg.by_issuer("PLACEHOLDER") is not None
    assert reg.platform_for("PLACEHOLDER") is None


def test_platforms_local_override_file_refused_outside_offline():
    """gap CFG-02 · the committed platforms.local.json (test-* issuers, localhost jwks/domains)
    must NOT load as a production registry — refused when offline=False."""
    local_file = DEFAULT_PLATFORMS_PATH.parent / "platforms.local.json"
    with pytest.raises(ValueError):
        load_platform_registry(local_file, RECOGNIZED, allow_empty=False, offline=False)


def test_platforms_local_override_file_still_loads_when_offline():
    """gap CFG-02 regression · platforms.local.json STILL loads under offline=True — the local
    embed test flow (test-* issuers, localhost domains) must keep working unchanged."""
    local_file = DEFAULT_PLATFORMS_PATH.parent / "platforms.local.json"
    reg = load_platform_registry(local_file, RECOGNIZED, allow_empty=True, offline=True)
    assert "localhost:3000" in reg.active_domains()


# --- gap BIT-A-R1: the loopback guard matches the FULL frontend set -------------------------------
# The frontend's isLocalhostDomain (frontend/src/features/embed/csp.ts) was widened to the whole
# loopback set — ::1, 0.0.0.0, the whole 127.0.0.0/8 block and *.localhost — but this backend guard
# still used an exact {"localhost","127.0.0.1"} match, so a production ACTIVE platform on one of the
# MISSED loopback forms slipped through. Each host below is such a form and must be refused outside
# offline; a real host and a 127-lookalike hostname must NOT be over-matched.

_LOOPBACK_URL_HOSTS = [
    "https://[::1]/",  # IPv6 loopback, bracketed URL form -> urlsplit host "::1"
    "https://127.0.0.2",  # inside 127.0.0.0/8, not the bare .0.1
    "https://127.255.255.255",  # top of the 127.0.0.0/8 block
    "https://0.0.0.0",  # wildcard-bind address
    "https://foo.localhost",  # *.localhost
]


@pytest.mark.parametrize("issuer", _LOOPBACK_URL_HOSTS)
def test_platforms_active_loopback_issuer_refused_outside_offline(tmp_path, issuer):
    """gap BIT-A-R1 · an ACTIVE platform whose ISSUER host is any loopback form the exact-match set
    missed (::1, 127.0.0.2, 127.255.255.255, 0.0.0.0, *.localhost) is refused outside offline,
    naming the entry — matching the widened frontend csp.ts set."""
    plat = {"acme": _platform(issuer=issuer, jwks_url="https://ex.test/j", domains=[])}
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert "loopback" in str(exc.value).lower()
    # offline (the local embed test flow) tolerates it, unchanged.
    load_platform_registry(p, RECOGNIZED, allow_empty=True, offline=True)


@pytest.mark.parametrize("jwks", _LOOPBACK_URL_HOSTS)
def test_platforms_active_loopback_jwks_refused_outside_offline(tmp_path, jwks):
    """gap BIT-A-R1 · the same widened set applies to the JWKS host, not only the issuer."""
    plat = {"acme": _platform(issuer="https://ex.test", jwks_url=jwks, domains=[])}
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    msg = str(exc.value)
    assert "loopback" in msg.lower()
    assert "jwks_url" in msg


@pytest.mark.parametrize(
    "domain",
    ["127.0.0.2", "127.255.255.255", "0.0.0.0", "[::1]:3000", "foo.localhost", "localhost:3000"],
)
def test_platforms_active_loopback_csp_domain_refused_outside_offline(tmp_path, domain):
    """gap BIT-A-R1 · a CSP domain on any widened loopback form (incl. bracketed IPv6 with a port
    and the 127.0.0.0/8 block) must never reach production frame-ancestors — refused outside
    offline, naming the entry."""
    plat = {
        "acme": _platform(
            issuer="https://acme.example.com",
            jwks_url="https://acme.example.com/j",
            domains=["app.acme.example.com", domain],
        )
    }
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert "loopback" in str(exc.value).lower()


@pytest.mark.parametrize("host", ["app.mews.com", "127.example.com"])
def test_platforms_active_real_and_lookalike_host_not_refused_outside_offline(tmp_path, host):
    """gap BIT-A-R1 · a real production host (app.mews.com) and a hostname that merely STARTS with
    "127." (127.example.com — not a numeric 127.0.0.0/8 literal) load fine outside offline as both
    issuer/jwks host and CSP domain; the strict numeric check must not over-match them."""
    plat = {
        "acme": _platform(issuer=f"https://{host}", jwks_url=f"https://{host}/j", domains=[host])
    }
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert reg.by_issuer(f"https://{host}") is not None


# --- gap CFG-DOMLOCAL-1 + BIT-LOOPBACK-EDGE-1: .local CSP-domain parity + loopback aliases --------
# CFG-DOMLOCAL-1: the issuer/jwks loop rejected a .local host but the CSP-domain loop rejected only
# a loopback host, so an ACTIVE platform with a real https issuer but an app.acme.local CSP domain
# passed the production guard and .local reached frame-ancestors + the postMessage allow-list.
# BIT-LOOPBACK-EDGE-1: the loopback matcher matched only literal localhost/*.localhost/dotted-quad
# 127.0.0.0/8/0.0.0.0/::1 and missed well-known loopback aliases — the trailing-dot FQDN form
# (localhost., 127.0.0.1.), the fully-expanded IPv6 loopback (0:0:0:0:0:0:0:1) and the IPv4-mapped
# IPv6 form (::ffff:127.0.0.1 / ::ffff:7f00:1). Both sides are widened together (csp.ts twins).


def _issuer_url(host: str) -> str:
    """A URL whose urlsplit host is exactly ``host`` — IPv6 literals get bracketed."""
    return f"https://[{host}]/" if ":" in host else f"https://{host}/"


_ALIAS_LOOPBACK_HOSTS = [
    "localhost.",  # trailing-dot FQDN form
    "127.0.0.1.",  # trailing-dot IPv4 loopback
    "0:0:0:0:0:0:0:1",  # fully-expanded IPv6 loopback
    "::ffff:127.0.0.1",  # IPv4-mapped IPv6 loopback (dotted)
    "::ffff:7f00:1",  # IPv4-mapped IPv6 loopback (hex)
    "::ffff:127.255.255.255",  # top of the mapped 127.0.0.0/8 block
]


@pytest.mark.parametrize("host", _ALIAS_LOOPBACK_HOSTS)
def test_platforms_active_loopback_alias_issuer_refused_outside_offline(tmp_path, host):
    """gap BIT-LOOPBACK-EDGE-1 · a loopback ALIAS (trailing-dot FQDN, fully-expanded IPv6, or
    IPv4-mapped IPv6) on the ISSUER host is refused outside offline, naming the entry; offline
    (the local embed test flow) still tolerates it."""
    plat = {"acme": _platform(issuer=_issuer_url(host), jwks_url="https://ex.test/j", domains=[])}
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert "loopback" in str(exc.value).lower()
    load_platform_registry(p, RECOGNIZED, allow_empty=True, offline=True)


@pytest.mark.parametrize("host", _ALIAS_LOOPBACK_HOSTS)
def test_platforms_active_loopback_alias_jwks_refused_outside_offline(tmp_path, host):
    """gap BIT-LOOPBACK-EDGE-1 · the same alias set applies to the JWKS host too."""
    plat = {"acme": _platform(issuer="https://ex.test", jwks_url=_issuer_url(host), domains=[])}
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    msg = str(exc.value)
    assert "loopback" in msg.lower()
    assert "jwks_url" in msg


@pytest.mark.parametrize(
    "domain",
    [
        "localhost.",
        "127.0.0.1.",
        "0:0:0:0:0:0:0:1",
        "[0:0:0:0:0:0:0:1]:3000",
        "::ffff:127.0.0.1",
        "[::ffff:127.0.0.1]:3000",
        "::ffff:7f00:1",
    ],
)
def test_platforms_active_loopback_alias_csp_domain_refused_outside_offline(tmp_path, domain):
    """gap BIT-LOOPBACK-EDGE-1 · a CSP domain on any loopback alias form (incl. bracketed IPv6 with
    a port) must never reach production frame-ancestors — refused outside offline, naming the
    entry."""
    plat = {
        "acme": _platform(
            issuer="https://acme.example.com",
            jwks_url="https://acme.example.com/j",
            domains=["app.acme.example.com", domain],
        )
    }
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert "loopback" in str(exc.value).lower()


@pytest.mark.parametrize("domain", ["app.acme.local", "acme.local", "app.acme.local:3000"])
def test_platforms_active_dotlocal_csp_domain_refused_outside_offline(tmp_path, domain):
    """gap CFG-DOMLOCAL-1 · a .local CSP domain on an ACTIVE entry with an otherwise-real https
    issuer must NOT reach production frame-ancestors — refused outside offline, mirroring the
    issuer/jwks .local check that already existed."""
    plat = {
        "acme": _platform(
            issuer="https://acme.example.com",
            jwks_url="https://acme.example.com/j",
            domains=["app.acme.example.com", domain],
        )
    }
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    with pytest.raises(ValueError, match="acme") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert ".local" in str(exc.value)


@pytest.mark.parametrize(
    "host",
    ["app.mews.com", "127.example.com", "example.local.com", "notlocalhost.example.com"],
)
def test_platforms_active_alias_lookalike_host_not_refused_outside_offline(tmp_path, host):
    """gap BIT-LOOPBACK-EDGE-1 / CFG-DOMLOCAL-1 · lookalikes that are NOT loopback or a .local TLD —
    a real host (app.mews.com), a 127-prefixed hostname (127.example.com), a .local.com host
    (example.local.com), and a notlocalhost.* host — load fine outside offline as issuer/jwks host
    and CSP domain; neither the widened loopback matcher nor the .local check over-matches them."""
    plat = {
        "acme": _platform(issuer=f"https://{host}", jwks_url=f"https://{host}/j", domains=[host])
    }
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert reg.by_issuer(f"https://{host}") is not None


# --- W6-5-L1: backend/frontend loopback-matcher parity on non-ASCII digits -----------------------
# gap W6-5-L1 (Wave-6 cross-cut audit): the octet numeric check used ``str.isdigit()``, which is
# True for non-ASCII digits (Arabic-Indic, fullwidth, superscript) that the frontend twin's
# ASCII-only ``/^\d{1,3}$/`` rejects — so ``127.0.0.<arabic-5>`` was loopback on the backend but not
# the frontend (a twin divergence, the exact recurring bug the twins were written to close), and
# ``127.0.0.<superscript-2>`` raised an unhandled ``ValueError`` (``int()`` on the octet) at
# production-registry load instead of the intended "not a trusted issuer" rejection. Both twins must
# agree: a non-ASCII-digit octet is NOT a numeric octet, so the host is a normal (non-loopback) host
# and the matcher must never raise.

_NON_ASCII_DIGIT_HOSTS = [
    "127.0.0.٥",  # Arabic-Indic digit five — isdigit() True, ASCII \d False
    "127.0.0.²",  # superscript two — isdigit() True but int() raises
    "127.0.0.１",  # fullwidth digit one — isdigit() True, ASCII \d False
]


@pytest.mark.parametrize("host", _NON_ASCII_DIGIT_HOSTS)
def test_loopback_matcher_treats_non_ascii_digit_octet_as_non_loopback(host):
    """gap W6-5-L1 · a host whose final octet is a non-ASCII "digit" is NOT a 127.0.0.0/8 literal
    (parity with the frontend's ASCII-only ``/^\\d{1,3}$/``); the matcher returns False and never
    raises. Locks the twin invariant that a divergence here is the recurring loopback bug."""
    assert _is_ipv4_loopback_host(host) is False
    assert _is_loopback_host(host) is False


@pytest.mark.parametrize("host", _NON_ASCII_DIGIT_HOSTS)
def test_platforms_non_ascii_digit_issuer_loads_as_real_host_outside_offline(tmp_path, host):
    """gap W6-5-L1 · a non-ASCII-digit host on an ACTIVE issuer is treated as an ordinary (non-
    loopback) host — it loads outside offline without raising, exactly as the frontend twin would
    keep it as a real embedder domain rather than stripping it as localhost."""
    plat = {"acme": _platform(issuer=f"https://{host}", jwks_url=f"https://{host}/j", domains=[])}
    p = _write(tmp_path, _data(platforms=plat, integrations={}))
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False, offline=False)
    assert reg.by_issuer(f"https://{host}") is not None


# --- CIP-A1: per-platform allowed_integrations allow-list ----------------------------------------
# Each platform declares which integration CLAIM VALUES it may assert; a value not in the global
# integrations map stops startup naming the offender, and the loaded entry exposes the tuple.


def test_platforms_allowed_integration_not_in_map_stops_startup(tmp_path):
    """CIP-A1 · an allowed_integrations value with no matching integrations-map key stops startup,
    naming the offending platform and the bad value."""
    plat = {"mews": _platform(issuer="https://app.mews.com", allowed_integrations=["toast"])}
    p = _write(tmp_path, _data(platforms=plat, integrations={"mews": ["obi-mews-test"]}))
    with pytest.raises(ValueError, match="mews") as exc:
        load_platform_registry(p, RECOGNIZED, allow_empty=False)
    assert "allowed_integration" in str(exc.value)
    assert "toast" in str(exc.value)


def test_platforms_entry_exposes_allowed_integrations(tmp_path):
    """CIP-A1 · a valid allowed_integrations list is carried onto the loaded PlatformEntry."""
    plat = {"mews": _platform(issuer="https://app.mews.com", allowed_integrations=["mews"])}
    p = _write(tmp_path, _data(platforms=plat, integrations={"mews": ["obi-mews-test"]}))
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False)
    entry = reg.by_issuer("https://app.mews.com")
    assert entry is not None
    assert entry.allowed_integrations == ("mews",)


def test_platforms_allowed_integrations_defaults_empty(tmp_path):
    """CIP-A1 · a platform with no allowed_integrations key loads with an empty tuple (it may
    assert no integration — only general-only tokens)."""
    plat = {"mews": _platform(issuer="https://app.mews.com")}
    p = _write(tmp_path, _data(platforms=plat, integrations={"mews": ["obi-mews-test"]}))
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False)
    entry = reg.by_issuer("https://app.mews.com")
    assert entry is not None
    assert entry.allowed_integrations == ()


def test_platforms_real_file_datahub_vends_product_integrations():
    """CIP-A1 · the committed registry's active hub (datahub) is allowed to assert every product
    integration (OWNER TRUST DECISION — see platforms.json _readme)."""
    reg = load_platform_registry(
        DEFAULT_PLATFORMS_PATH,
        load_recognized_knowledge_scopes(),
        allow_empty=False,
        offline=True,
    )
    entry = reg.by_issuer("TODO until 4.x")
    assert entry is not None and entry.key == "datahub"
    assert set(entry.allowed_integrations) == {"mews", "toast", "opera-cloud"}


def test_platforms_local_file_allowed_integrations_match_test_hosts():
    """CIP-A1 · platforms.local.json's test-* allow-lists match exactly what the frontend test-host
    token routes mint (frontend/src/app/api/test-hosts/config.ts): test-mews->mews, test-toast->
    toast, test-opera->opera-cloud, test-none-> () (mints a general-only, no-integration token) —
    the local embed test flow must keep resolving."""
    local_file = DEFAULT_PLATFORMS_PATH.parent / "platforms.local.json"
    reg = load_platform_registry(local_file, RECOGNIZED, allow_empty=True, offline=True)
    expected = {
        "https://test-mews.local": ("mews",),
        "https://test-toast.local": ("toast",),
        "https://test-opera.local": ("opera-cloud",),
        "https://test-none.local": (),
    }
    for issuer, allowed in expected.items():
        entry = reg.by_issuer(issuer)
        assert entry is not None, issuer
        assert entry.allowed_integrations == allowed, issuer
