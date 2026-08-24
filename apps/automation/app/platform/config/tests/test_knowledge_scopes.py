"""PLAN 10.1 (revised): recognized knowledge scopes load from a dedicated global config file
(`config/knowledge_scopes.json`), not an env var — an operator-editable content registry, not a
per-deployment secret or runtime toggle (ADR-0011).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.platform.config.knowledge_scopes import (
    DEFAULT_KNOWLEDGE_SCOPES_PATH,
    load_recognized_knowledge_scopes,
)


def _write(path: Path, scopes: list[dict[str, str]]) -> Path:
    path.write_text(json.dumps({"scopes": scopes}))
    return path


def test_parses_lowercases_and_trims(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "knowledge_scopes.json",
        [{"name": " General "}, {"name": "Mews"}, {"name": "opera-cloud"}, {"name": "TOAST"}],
    )

    assert load_recognized_knowledge_scopes(path) == {"general", "mews", "opera-cloud", "toast"}


def test_missing_general_raises(tmp_path: Path) -> None:
    path = _write(tmp_path / "knowledge_scopes.json", [{"name": "mews"}, {"name": "toast"}])

    with pytest.raises(ValueError, match="must include a 'general' scope"):
        load_recognized_knowledge_scopes(path)


def test_empty_scopes_raises(tmp_path: Path) -> None:
    path = _write(tmp_path / "knowledge_scopes.json", [])

    with pytest.raises(ValueError, match="must include a 'general' scope"):
        load_recognized_knowledge_scopes(path)


def test_blank_names_are_ignored(tmp_path: Path) -> None:
    path = _write(tmp_path / "knowledge_scopes.json", [{"name": "general"}, {"name": "  "}])

    assert load_recognized_knowledge_scopes(path) == {"general"}


def test_committed_repo_config_file_is_well_formed() -> None:
    scopes = load_recognized_knowledge_scopes(DEFAULT_KNOWLEDGE_SCOPES_PATH)

    assert scopes == {"general", "mews", "opera-cloud", "toast"}
