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
    The real knowledge-base/config/platforms.json loads under the real scopes in strict mode."""
    reg = load_platform_registry(
        DEFAULT_PLATFORMS_PATH,
        load_recognized_knowledge_scopes(),
        allow_empty=False,
    )
    # strict mode did not raise -> at least one active platform is present (datahub).
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
