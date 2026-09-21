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
        [
            {"name": " Obi-General-Test "},
            {"name": "Obi-Mews-Test"},
            {"name": "obi-operacloud-test"},
            {"name": "OBI-TOAST-TEST"},
        ],
    )

    assert load_recognized_knowledge_scopes(path) == {
        "obi-general-test",
        "obi-mews-test",
        "obi-operacloud-test",
        "obi-toast-test",
    }


def test_missing_general_raises(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "knowledge_scopes.json",
        [{"name": "obi-mews-test"}, {"name": "obi-toast-test"}],
    )

    with pytest.raises(ValueError, match="must include a 'obi-general-test' scope"):
        load_recognized_knowledge_scopes(path)


def test_empty_scopes_raises(tmp_path: Path) -> None:
    path = _write(tmp_path / "knowledge_scopes.json", [])

    with pytest.raises(ValueError, match="must include a 'obi-general-test' scope"):
        load_recognized_knowledge_scopes(path)


def test_blank_names_are_ignored(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "knowledge_scopes.json",
        [{"name": "obi-general-test"}, {"name": "  "}],
    )

    assert load_recognized_knowledge_scopes(path) == {"obi-general-test"}


def test_committed_repo_config_file_is_well_formed() -> None:
    scopes = load_recognized_knowledge_scopes(DEFAULT_KNOWLEDGE_SCOPES_PATH)

    assert scopes == {
        "obi-general-test",
        "obi-mews-test",
        "obi-operacloud-test",
        "obi-toast-test",
    }
