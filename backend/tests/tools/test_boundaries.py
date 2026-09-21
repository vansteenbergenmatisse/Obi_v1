"""panel sc-kb · substep 1.1.2
The boundary checker enforces the Phase-1 one-way folder rule: knowledge-base never imports the
backend (app/features/platform/shared), the backend never imports the frontend, and the frontend
never reaches into backend/ or a .py file. Each negative case must fail AND name the offending file;
the untouched tree must pass.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CHECKER = _REPO_ROOT / "backend" / "tools" / "check_feature_boundaries.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("_boundary_checker", _CHECKER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def checker():
    return _load_checker()


@pytest.fixture
def probe() -> Iterator:
    """Yield a factory that writes a temp file under a real folder and always removes it."""
    created: list[Path] = []

    def _make(rel_path: str, content: str) -> Path:
        p = _REPO_ROOT / rel_path
        p.write_text(content, encoding="utf-8")
        created.append(p)
        return p

    yield _make
    for p in created:
        p.unlink(missing_ok=True)


def test_sec_boundary_clean_tree_passes(checker):
    """panel sc-kb · substep 1.1.2
    The real tree has no wrong-way folder imports, so the checker reports none."""
    assert checker.check_folder_boundaries() == []


def test_sec_boundary_kb_cannot_import_backend(checker, probe):
    """panel sc-kb · substep 1.1.2
    A file under knowledge-base/ that imports a backend package (features) fails and is named."""
    probe("knowledge-base/schema/_tmp_kb_probe.py", "from features import thing\n")
    failures = checker.check_folder_boundaries()
    assert any("_tmp_kb_probe.py" in f for f in failures), failures


def test_sec_boundary_backend_cannot_import_frontend(checker, probe):
    """panel sc-backend · substep 1.1.2
    A file under backend/ that imports the frontend fails and is named."""
    probe("backend/app/_tmp_be_probe.py", "import frontend\n")
    failures = checker.check_folder_boundaries()
    assert any("_tmp_be_probe.py" in f for f in failures), failures


def test_sec_boundary_frontend_cannot_reach_backend(checker, probe):
    """panel sc-frontend · substep 1.1.2
    A frontend TypeScript file that imports ../backend/anything fails and is named."""
    probe("frontend/src/_tmp_fe_probe.ts", 'import { x } from "../backend/thing";\n')
    failures = checker.check_folder_boundaries()
    assert any("_tmp_fe_probe.ts" in f for f in failures), failures
