"""PLAN 10.1: recognized knowledge-scope configuration (ADR-0011).

`knowledge_scopes` is the central registry of recognized scope identifiers a Confluence label
can resolve to (PLAN 10.2) and a chat request can ask to be filtered by (PLAN 10.4/10.5).
"general" must always be present — it is the always-included, never-inferred-from-untagged
scope (ADR-0011 Decision 1) — so a misconfigured deployment fails at process start rather than
silently dropping general-scoped content.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.platform.config import Settings


def test_default_knowledge_scope_set_is_general_only() -> None:
    assert Settings().knowledge_scope_set == {"general"}


def test_comma_separated_env_value_parses_lowercases_and_trims() -> None:
    settings = Settings(knowledge_scopes=" General, Mews ,opera-cloud,TOAST ")

    assert settings.knowledge_scope_set == {"general", "mews", "opera-cloud", "toast"}


def test_confirmed_deployment_value_parses_cleanly() -> None:
    settings = Settings(knowledge_scopes="general,mews,opera-cloud,toast")

    assert settings.knowledge_scope_set == {"general", "mews", "opera-cloud", "toast"}


def test_knowledge_scopes_missing_general_fails_at_construction() -> None:
    with pytest.raises(ValidationError, match="knowledge_scopes must include 'general'"):
        Settings(knowledge_scopes="mews,opera-cloud,toast")


def test_empty_knowledge_scopes_fails_at_construction() -> None:
    with pytest.raises(ValidationError, match="knowledge_scopes must include 'general'"):
        Settings(knowledge_scopes="")


def test_default_knowledge_scope_defaults_to_empty() -> None:
    assert Settings().default_knowledge_scope == ""


def test_enable_knowledge_scope_filtering_defaults_to_false() -> None:
    assert Settings().enable_knowledge_scope_filtering is False
