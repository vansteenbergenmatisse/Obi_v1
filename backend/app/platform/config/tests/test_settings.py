"""PLAN 10.1 (revised): recognized knowledge-scope configuration (ADR-0011).

`knowledge_scope_set` delegates to `config/knowledge_scopes.json` (see
`test_knowledge_scopes.py` for the loader's own parsing/validation coverage) — this file only
covers that `Settings` wires it through and that the fail-fast-at-startup validator fires.
"obi-general-test" must always be present — it is the always-included, never-inferred-from-untagged
base scope (ADR-0011 Decision 1) — so a misconfigured deployment fails at process start rather
than silently dropping base-scoped content.
"""

from __future__ import annotations

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


# -- gap CFG-05: the canonical offline/local env-value set, pinned against silent drift -----------


def test_offline_env_value_set_is_the_canonical_cross_side_contract() -> None:
    """gap CFG-05 · the backend offline/local env-value set is pinned here and MUST stay identical
    to the frontend's LOCAL_OR_DEV_ENVS (frontend/src/features/embed/csp.ts, with its own mirror
    test). 'development' is offline/local on BOTH sides — the single canonical treatment — so that
    setting only ENV or only APP_ENV can no longer gate the two apps inconsistently. A change here
    without the matching frontend change is the silent-drift bug this test exists to stop."""
    expected = {"local", "dev", "development", "test", "ci"}
    assert expected == settings_module._OFFLINE_ENVS
