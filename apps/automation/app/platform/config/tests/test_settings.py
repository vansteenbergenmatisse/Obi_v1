"""PLAN 10.1 (revised): recognized knowledge-scope configuration (ADR-0011).

`knowledge_scope_set` delegates to `config/knowledge_scopes.json` (see
`test_knowledge_scopes.py` for the loader's own parsing/validation coverage) — this file only
covers that `Settings` wires it through and that the fail-fast-at-startup validator fires.
"general" must always be present — it is the always-included, never-inferred-from-untagged
scope (ADR-0011 Decision 1) — so a misconfigured deployment fails at process start rather than
silently dropping general-scoped content.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.platform.config import Settings
from app.platform.config import settings as settings_module


def test_knowledge_scope_set_reads_the_committed_config_file() -> None:
    assert Settings().knowledge_scope_set == {"general", "mews", "opera-cloud", "toast"}
    assert "general" in Settings().knowledge_scope_set


def test_construction_fails_fast_when_config_file_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> frozenset[str]:
        raise ValueError("config/knowledge_scopes.json must include a 'general' scope (got [])")

    monkeypatch.setattr(settings_module, "load_recognized_knowledge_scopes", _raise)

    with pytest.raises(ValidationError, match="must include a 'general' scope"):
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
