"""PLAN 10.1 (revised): recognized knowledge-scope configuration (ADR-0011).

`knowledge_scope_set` delegates to `config/knowledge_scopes.json` (see
`test_knowledge_scopes.py` for the loader's own parsing/validation coverage) — this file only
covers that `Settings` wires it through and that the fail-fast-at-startup validator fires.
"obi-general-test" must always be present — it is the always-included, never-inferred-from-untagged
base scope (ADR-0011 Decision 1) — so a misconfigured deployment fails at process start rather
than silently dropping base-scoped content.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.platform.config import Settings
from app.platform.config import settings as settings_module


def test_knowledge_scope_set_reads_the_committed_config_file() -> None:
    assert Settings().knowledge_scope_set == {
        "obi-general-test",
        "obi-mews-test",
        "obi-operacloud-test",
        "obi-toast-test",
    }
    assert "obi-general-test" in Settings().knowledge_scope_set


def test_construction_fails_fast_when_config_file_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> frozenset[str]:
        raise ValueError(
            "config/knowledge_scopes.json must include a 'obi-general-test' scope (got [])"
        )

    monkeypatch.setattr(settings_module, "load_recognized_knowledge_scopes", _raise)

    with pytest.raises(ValidationError, match="must include a 'obi-general-test' scope"):
        Settings()


# These two assert the CODE default, read straight off the declared field — not a constructed
# `Settings()`, which loads the root `.env` and would (correctly) reflect an operator's real config.
# PLAN 10.7 flips ENABLE_KNOWLEDGE_SCOPE_FILTERING=true in that `.env` once the corpus is labeled,
# so a `.env`-coupled assertion here would fail on the real deployment; the field default is what
# "X defaults to Y" actually means.
def test_default_knowledge_scope_defaults_to_empty() -> None:
    assert Settings.model_fields["default_knowledge_scope"].default == ""


def test_enable_knowledge_scope_filtering_defaults_to_false() -> None:
    assert Settings.model_fields["enable_knowledge_scope_filtering"].default is False


# -- chat image caps: w-composer panel / decision w-composer-images (substep 4.2.7) ---------------


def test_chat_image_caps_default_to_the_w_composer_images_decision() -> None:
    """4.2.7 · The composer image cap (design panel w-composer). Decision w-composer-images
    (2026-09-18): at most 3 images per turn, each <= 3 MB. These two defaults are what the
    composer mirrors and the /chat endpoint enforces with a 400; asserting the field defaults
    keeps that contract from silently drifting back to the old 4 / 5 MB caps."""
    assert Settings.model_fields["chat_max_images_per_turn"].default == 3
    assert Settings.model_fields["chat_max_image_bytes"].default == 3_000_000


# -- obi_identity_text: operator-editable static identity block (config/obi_identity.md) ----------


def test_obi_identity_path_defaults_to_empty() -> None:
    assert Settings.model_fields["obi_identity_path"].default == ""


def test_obi_identity_text_reads_the_file_when_present(tmp_path) -> None:
    f = tmp_path / "obi_identity.md"
    f.write_text("Omniboost builds hospitality software.\n")
    assert Settings(obi_identity_path=str(f)).obi_identity_text == (
        "Omniboost builds hospitality software."
    )


def test_obi_identity_text_is_empty_when_file_missing_does_not_raise(tmp_path) -> None:
    missing = tmp_path / "nope.md"
    assert Settings(obi_identity_path=str(missing)).obi_identity_text == ""


# -- CFG-B: the backend offline/local env-value set, narrowed to genuine local/CI labels ----------


def test_offline_env_value_set_is_narrowed_to_local_ci_labels() -> None:
    """gap CFG-B · the backend offline/local env-value set is pinned here. It is narrowed to only
    genuine local/CI labels — `dev`/`development` were DROPPED so a public deployment labelled
    `dev`/`development`/`staging` is GUARDED (fail closed), not run with the platform-trust guard
    off. This set is intentionally NOT identical to the frontend's LOCAL_OR_DEV_ENVS: the two apps
    read different vars (backend ENV vs frontend APP_ENV) with different defaults and different
    production signals, so the old "identical cross-side contract" claim is retired — see the
    corrected _OFFLINE_ENVS docstring in settings.py. A change here is security-relevant."""
    expected = {"local", "test", "ci"}
    assert expected == settings_module._OFFLINE_ENVS


# -- CFG-A / CFG-C: the platform-trust guard fails CLOSED on an unset/unknown ENV -----------------
# The registry guard sits in front of the /chat JWT-issuer trust path (which issuers Obi trusts +
# which domains seed the embed CSP). It MUST fail closed: an unset or unknown ENV is treated as a
# real deployment (production) so the SEC-S2 trust guard and the zero-active guard both FIRE. Only
# an explicit offline/local label (`local`/`test`/`ci`) relaxes it. `allow_empty_platforms` is a
# test-only convenience that must NOT defeat the trust guard outside an offline env (CFG-C).


def _valid_prod_platforms_json(tmp_path: Path) -> str:
    """A registry with one real, https, non-localhost ACTIVE platform — passes the trust guard and
    the zero-active guard, so a non-offline Settings can be constructed for tests that only need
    `is_offline_env()` to be False (they do not care about the registry itself)."""
    p = tmp_path / "platforms.json"
    p.write_text(
        json.dumps(
            {
                "platforms": {
                    "acme": {
                        "issuer": "https://acme.example.com",
                        "jwks_url": "https://acme.example.com/.well-known/jwks.json",
                        "domains": ["app.acme.example.com"],
                        "lifetime_minutes": 60,
                        "algs": ["RS256"],
                        "active": True,
                    }
                },
                "integrations": {},
            }
        )
    )
    return str(p)


@pytest.fixture
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip the env vars the test-suite conftest pins (ENV=test, ALLOW_EMPTY_PLATFORMS=true,
    PLATFORMS_PATH="") AND disable root-.env loading, so `Settings(...)` observes the pure code
    defaults — the exact posture of a real deployment where an operator forgot to set ENV. Without
    the env_file override a developer's local `.env` (ENV=local) would leak in and mask the
    fail-closed default, passing locally but failing in CI (which has no .env)."""
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("ALLOW_EMPTY_PLATFORMS", raising=False)
    monkeypatch.delenv("PLATFORMS_PATH", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)


def test_env_default_is_empty_string_so_unset_is_not_offline() -> None:
    """gap CFG-A · the CODE default for ENV is "" (not "local"). An empty/unset ENV is NOT in the
    offline set, so is_offline_env() is False and the deployment is treated as production. Asserted
    off the declared field (not a constructed Settings, which would load the root .env)."""
    assert Settings.model_fields["env"].default == ""


def test_unset_env_fires_the_trust_guard_fail_closed(_clean_env: None) -> None:
    """gap CFG-A · with NO ENV set, constructing Settings against the committed platforms.json
    (whose only active platform, datahub, still carries a TODO placeholder issuer) RAISES — the
    fail-closed path. Before the fix the "local" default made this silently pass with the guard
    off."""
    with pytest.raises(ValidationError):
        Settings()


def test_unset_env_is_not_offline(_clean_env: None, tmp_path: Path) -> None:
    """gap CFG-A · an unset ENV resolves is_offline_env() to False. Uses a valid production
    registry so construction succeeds and we can read the flag off the built object."""
    s = Settings(platforms_path=_valid_prod_platforms_json(tmp_path))
    assert s.is_offline_env() is False


def test_dev_and_unknown_labels_are_not_offline_but_local_ci_are(
    _clean_env: None, tmp_path: Path
) -> None:
    """gap CFG-B · only `local`/`test`/`ci` are offline. `dev`/`development`/`staging`/`production`
    and an empty label are treated as production (guard fires). A valid registry lets the
    non-offline objects construct so we can assert the flag directly."""
    valid = _valid_prod_platforms_json(tmp_path)
    for label in ("dev", "development", "staging", "production", ""):
        s = Settings(env=label, platforms_path=valid)
        assert s.is_offline_env() is False, label
    for label in ("local", "test", "ci", "LOCAL", "CI"):
        s = Settings(env=label, platforms_path=valid)
        assert s.is_offline_env() is True, label


def test_explicit_offline_env_relaxes_the_registry(_clean_env: None) -> None:
    """gap CFG-A · an explicit offline label (env="test") relaxes the guard: the committed
    placeholder registry loads without raising, and is_offline_env() is True."""
    s = Settings(env="test")
    assert s.is_offline_env() is True
    _ = s.platform_registry  # loads; datahub's placeholder is tolerated offline


def test_allow_empty_platforms_does_not_relax_trust_guard_outside_offline(
    _clean_env: None,
) -> None:
    """gap CFG-C · the test-only escape hatch must NOT disable the trust guard in production.
    A non-offline Settings with allow_empty_platforms=True still RAISES against the committed
    placeholder registry — allow_empty may only relax things inside an offline env."""
    with pytest.raises(ValidationError):
        Settings(env="production", allow_empty_platforms=True)


def test_allow_empty_platforms_does_not_permit_zero_active_outside_offline(
    _clean_env: None, tmp_path: Path
) -> None:
    """gap CFG-C · allow_empty_platforms=True does NOT let an empty/zero-active registry through in
    a non-offline env — the zero-active guard still fires."""
    empty = tmp_path / "platforms.json"
    empty.write_text(json.dumps({"platforms": {}, "integrations": {}}))
    with pytest.raises(ValidationError):
        Settings(
            env="production",
            allow_empty_platforms=True,
            platforms_path=str(empty),
        )
