import json
from pathlib import Path

import pytest

from app.platform.config.platforms import load_platform_registry

RECOGNIZED = frozenset(
    {"obi-general-test", "obi-mews-test", "obi-toast-test", "obi-operacloud-test"}
)


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "platforms.json"
    p.write_text(json.dumps(data))
    return p


def test_maps_platform_key_to_live_slugs(tmp_path):
    p = _write(
        tmp_path,
        {
            "platforms": {
                "mews": {
                    "issuer": "https://app.mews.com",
                    "jwks_url": "https://app.mews.com/j",
                    "domains": ["app.mews.com"],
                    "lifetime_minutes": 60,
                    "algs": ["RS256"],
                    "active": True,
                }
            },
            "integrations": {"mews": ["obi-mews-test", "obi-general-test"]},
        },
    )
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False)
    entry = reg.by_issuer("https://app.mews.com")
    assert entry is not None
    assert entry.key == "mews"
    assert reg.scopes_for("mews") == [
        "obi-general-test",
        "obi-mews-test",
    ]  # sorted, general always present
    assert reg.scopes_for("unknown") is None
    assert reg.active_domains() == ["app.mews.com"]


def test_unknown_slug_in_integrations_stops_startup(tmp_path):
    p = _write(
        tmp_path,
        {
            "platforms": {
                "mews": {
                    "issuer": "i",
                    "jwks_url": "j",
                    "domains": ["d"],
                    "lifetime_minutes": 60,
                    "algs": ["RS256"],
                    "active": True,
                }
            },
            "integrations": {"mews": ["obi-not-a-real-scope"]},
        },
    )
    with pytest.raises(ValueError, match="not in knowledge_scopes"):
        load_platform_registry(p, RECOGNIZED, allow_empty=False)


def test_empty_platforms_stops_startup_when_not_allowed(tmp_path):
    p = _write(tmp_path, {"platforms": {}, "integrations": {}})
    with pytest.raises(ValueError, match="no platforms"):
        load_platform_registry(p, RECOGNIZED, allow_empty=False)


def test_empty_platforms_allowed_locally(tmp_path):
    p = _write(tmp_path, {"platforms": {}, "integrations": {}})
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=True)
    assert reg.active_domains() == []


def test_general_always_appended_even_if_omitted(tmp_path):
    p = _write(
        tmp_path,
        {
            "platforms": {
                "mews": {
                    "issuer": "i",
                    "jwks_url": "j",
                    "domains": ["d"],
                    "lifetime_minutes": 60,
                    "algs": ["RS256"],
                    "active": True,
                }
            },
            "integrations": {"mews": ["obi-mews-test"]},
        },
    )
    reg = load_platform_registry(p, RECOGNIZED, allow_empty=False)
    scopes = reg.scopes_for("mews")
    assert scopes is not None
    assert "obi-general-test" in scopes


def test_classified_scope_is_never_mappable(tmp_path):
    p = _write(
        tmp_path,
        {
            "platforms": {
                "mews": {
                    "issuer": "i",
                    "jwks_url": "j",
                    "domains": ["d"],
                    "lifetime_minutes": 60,
                    "algs": ["RS256"],
                    "active": True,
                }
            },
            "integrations": {"mews": ["classified", "obi-general-test"]},
        },
    )
    with pytest.raises(ValueError, match="classified"):
        load_platform_registry(p, RECOGNIZED, allow_empty=False)


def test_hs256_alg_is_forbidden(tmp_path):
    p = _write(
        tmp_path,
        {
            "platforms": {
                "mews": {
                    "issuer": "i",
                    "jwks_url": "j",
                    "domains": ["d"],
                    "lifetime_minutes": 60,
                    "algs": ["HS256"],
                    "active": True,
                }
            },
            "integrations": {"mews": ["obi-mews-test"]},
        },
    )
    with pytest.raises(ValueError, match="HS256"):
        load_platform_registry(p, RECOGNIZED, allow_empty=False)
