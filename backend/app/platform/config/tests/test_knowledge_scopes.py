"""panels tg-config / ks-validate / cm-config · substep 1.2.1 — The tag map.

The one tag file (`knowledge-base/config/knowledge_scopes.json`) is validated at startup: every
entry lowercase, no duplicates, the general scope present, the reserved `classified` scope present.
A bad entry stops the backend before it can leak; `classified` is present in the file but is never
offered — excluded from the returned set and from GET /health.
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

# The four recognized (offerable) scopes today; `classified` is reserved and excluded.
_RECOGNIZED = {
    "obi-general-test",
    "obi-mews-test",
    "obi-operacloud-test",
    "obi-toast-test",
}


def _write(path: Path, names: list[str]) -> Path:
    """A temp config file from a plain name list — never edits the real committed file."""
    path.write_text(json.dumps({"scopes": [{"name": n, "description": ""} for n in names]}))
    return path


def test_tags_uppercase_entry_fails_and_names_it(tmp_path: Path) -> None:
    """panel ks-validate · substep 1.2.1
    An uppercase slug ("Toast") is rejected at startup and the message names the entry."""
    path = _write(
        tmp_path / "knowledge_scopes.json",
        ["obi-general-test", "classified", "Toast"],
    )

    with pytest.raises(ValueError, match="Toast"):
        load_recognized_knowledge_scopes(path)


def test_tags_duplicate_fails_and_names_it(tmp_path: Path) -> None:
    """panel ks-validate · substep 1.2.1
    A duplicated slug fails startup and the message names the repeated entry."""
    path = _write(
        tmp_path / "knowledge_scopes.json",
        ["obi-general-test", "classified", "obi-mews-test", "obi-mews-test"],
    )

    with pytest.raises(ValueError, match="obi-mews-test"):
        load_recognized_knowledge_scopes(path)


def test_tags_missing_general_fails(tmp_path: Path) -> None:
    """panel ks-validate · substep 1.2.1
    A file without the general scope fails startup."""
    path = _write(
        tmp_path / "knowledge_scopes.json",
        ["obi-mews-test", "classified"],
    )

    with pytest.raises(ValueError, match="obi-general-test"):
        load_recognized_knowledge_scopes(path)


def test_tags_missing_classified_fails(tmp_path: Path) -> None:
    """panel ks-validate · substep 1.2.1
    A file without the reserved classified scope fails startup."""
    path = _write(
        tmp_path / "knowledge_scopes.json",
        ["obi-general-test", "obi-mews-test"],
    )

    with pytest.raises(ValueError, match="classified"):
        load_recognized_knowledge_scopes(path)


def test_tags_health_lists_scopes_without_classified() -> None:
    """panel tg-config · substep 1.2.1
    GET /health lists the loaded recognized scopes and never the reserved classified scope."""
    client = TestClient(create_app(start_scheduler=False))

    resp = client.get("/health")

    assert resp.status_code == 200
    scopes = resp.json()["knowledge_scopes"]
    assert set(scopes) == _RECOGNIZED
    assert "classified" not in scopes


def test_tags_real_committed_file_loads() -> None:
    """panel cm-config · substep 1.2.1
    The real committed file loads to exactly the recognized scopes (classified excluded)."""
    assert load_recognized_knowledge_scopes(DEFAULT_KNOWLEDGE_SCOPES_PATH) == _RECOGNIZED
