"""Locate and load the Confluence fixture corpus from the evaluation harness.

The fixture corpus lives at ``backend/tests/fixtures/confluence`` and is
loaded by file path so the harness never depends on the ``tests`` package being
importable (it must run DB-free and without pytest's path wiring). This module
imports the corpus ``loader`` module directly from its file location.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _automation_root() -> Path:
    # this file: app/features/evaluation/fixtures.py -> parents[3] == backend
    return Path(__file__).resolve().parents[3]


def confluence_fixtures_dir() -> Path:
    """Absolute path to the Confluence fixture corpus directory."""
    return _automation_root() / "tests" / "fixtures" / "confluence"


def datasets_dir() -> Path:
    """Absolute path to the evaluation datasets directory (bundled in the package)."""
    return Path(__file__).resolve().parent / "datasets"


def load_corpus_loader() -> ModuleType:
    """Import the fixture corpus ``loader.py`` module by file path."""
    loader_path = confluence_fixtures_dir() / "loader.py"
    spec = importlib.util.spec_from_file_location("confluence_fixture_loader", loader_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load fixture loader from {loader_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


__all__ = ["confluence_fixtures_dir", "datasets_dir", "load_corpus_loader"]
