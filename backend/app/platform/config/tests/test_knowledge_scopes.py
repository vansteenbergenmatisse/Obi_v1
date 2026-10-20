"""panels tg-config / ks-validate / cm-config — The reserved-label file
(ADR-routing-labels-sole-content-axis).

The one file (`knowledge-base/config/knowledge_scopes.json`) is validated at startup: every entry
lowercase, no duplicates, the reserved `classified` scope present.
ADR-routing-labels-sole-content-axis retired the
knowledge-scope `-test` axis, so the file now holds only `classified` and the recognized (offerable)
set is empty. `classified` is present in the file but is never offered — excluded from the returned
set and from GET /health.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.platform.config.knowledge_scopes import (
    DEFAULT_KNOWLEDGE_SCOPES_PATH,
    load_recognized_knowledge_scopes,
)

# Post-ADR-routing-labels-sole-content-axis there are NO offerable knowledge scopes; `classified` is
# reserved and excluded.
_RECOGNIZED: set[str] = set()


def _write(path: Path, names: list[str]) -> Path:
    """A temp config file from a plain name list — never edits the real committed file."""
    path.write_text(json.dumps({"scopes": [{"name": n, "description": ""} for n in names]}))
    return path


def test_tags_uppercase_entry_fails_and_names_it(tmp_path: Path) -> None:
    """panel ks-validate
    An uppercase slug ("Toast") is rejected at startup and the message names the entry."""
    path = _write(
        tmp_path / "knowledge_scopes.json",
        ["classified", "Toast"],
    )

    with pytest.raises(ValueError, match="Toast"):
        load_recognized_knowledge_scopes(path)


def test_tags_duplicate_fails_and_names_it(tmp_path: Path) -> None:
    """panel ks-validate
    A duplicated slug fails startup and the message names the repeated entry."""
    path = _write(
        tmp_path / "knowledge_scopes.json",
        ["classified", "dup-scope", "dup-scope"],
    )

    with pytest.raises(ValueError, match="dup-scope"):
        load_recognized_knowledge_scopes(path)


def test_tags_general_no_longer_required(tmp_path: Path) -> None:
    """panel ks-validate · ADR-routing-labels-sole-content-axis
    The old `obi-general-test` requirement is retired: a file with only `classified` (no general
    base scope) loads fine and returns an empty recognized set."""
    path = _write(
        tmp_path / "knowledge_scopes.json",
        ["classified"],
    )

    assert load_recognized_knowledge_scopes(path) == set()


def test_tags_missing_classified_fails(tmp_path: Path) -> None:
    """panel ks-validate
    A file without the reserved classified scope fails startup."""
    path = _write(
        tmp_path / "knowledge_scopes.json",
        ["some-scope"],
    )

    with pytest.raises(ValueError, match="classified"):
        load_recognized_knowledge_scopes(path)


def test_tags_health_lists_scopes_without_classified() -> None:
    """panel tg-config
    GET /health lists the loaded recognized scopes (empty post-ADR-routing-labels-sole-content-axis)
    and never classified."""
    client = TestClient(create_app(start_scheduler=False))

    resp = client.get("/health")

    assert resp.status_code == 200
    scopes = resp.json()["knowledge_scopes"]
    assert set(scopes) == _RECOGNIZED
    assert "classified" not in scopes


def test_tags_real_committed_file_loads() -> None:
    """panel cm-config
    The real committed file loads to the empty recognized set (classified excluded)."""
    assert load_recognized_knowledge_scopes(DEFAULT_KNOWLEDGE_SCOPES_PATH) == _RECOGNIZED
