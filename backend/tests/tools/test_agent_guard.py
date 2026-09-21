"""Tests for tools/agent_guard.py — the PreToolUse guard for the Obi subagents.

Hermetic: each test drives agent_guard.py as a subprocess with a JSON payload on
stdin, exactly as a hook would. No network, no sleep. Exit 0 = allow, exit 2 = block.
The implementer marker is created/removed inside a tmp cwd so nothing leaks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / "tools" / "agent_guard.py"

ALLOW = 0
BLOCK = 2


def guard(
    profile: str,
    payload: dict,
    cwd: Path | None = None,
    env: dict | None = None,
) -> int:
    run_env = None
    if env is not None:
        run_env = {**os.environ, **env}
    proc = subprocess.run(
        [sys.executable, str(GUARD), profile],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        env=run_env,
    )
    return proc.returncode


def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def write(path: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path}}


def edit(path: str) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": path}}


def test_guard_rejects_unknown_profile():
    assert guard("bogus", bash("ls")) == BLOCK


def test_auditor_read_only_shell_allowed():
    assert guard("auditor", bash("ls docs")) == ALLOW
    assert guard("auditor", bash("git log --oneline")) == ALLOW
    assert guard("auditor", bash("python3 backend/tools/panel.py --list")) == ALLOW


def test_auditor_allows_read_only_pytest():
    # 0.3.2 (the test inventory) needs the collector; a plain run is read-only too.
    assert guard("auditor", bash("uv run pytest --collect-only -q")) == ALLOW
    assert guard("auditor", bash("cd /repo/backend && uv run pytest -q")) == ALLOW


def test_auditor_blocks_mutating_shell():
    assert guard("auditor", bash("git status")) == BLOCK
    assert guard("auditor", bash("rm -rf docs")) == BLOCK


def test_auditor_write_scoped_to_final_docs():
    assert guard("auditor", write("docs/Final_docs/shared.md")) == ALLOW
    assert guard("auditor", write("PROBE.txt")) == BLOCK
    assert guard("auditor", edit("docs/Final_docs/shared.md")) == BLOCK


def test_auditor_write_check_is_cwd_independent(tmp_path: Path):
    # The hook may run from any cwd. With CLAUDE_PROJECT_DIR set, an absolute
    # path under the project's docs/Final_docs/ is allowed no matter where the
    # guard is invoked from, and a path outside it is still blocked.
    root = tmp_path
    env = {"CLAUDE_PROJECT_DIR": str(root)}
    inside = str(root / "docs" / "Final_docs" / "tests.md")
    outside = str(root / "apps" / "web" / "PROBE.txt")
    assert guard("auditor", write(inside), cwd=tmp_path, env=env) == ALLOW
    assert guard("auditor", write(outside), cwd=tmp_path, env=env) == BLOCK


def test_auditor_blocks_redirect_even_to_allowed_dir():
    assert guard("auditor", bash("echo x > docs/Final_docs/probe.md")) == BLOCK
    assert guard("auditor", bash("echo x | tee docs/Final_docs/probe.md")) == BLOCK


def test_auditor_checks_every_chained_part():
    # first part allowed, second part not: the whole chain is blocked.
    assert guard("auditor", bash("git log && git status")) == BLOCK


def test_tester_allows_test_runners_blocks_writes():
    assert guard("tester", bash("make check")) == ALLOW
    assert guard("tester", bash("uv run pytest -q")) == ALLOW
    assert guard("tester", bash("git diff")) == ALLOW
    assert guard("tester", bash("rm -rf docs/synopsis")) == BLOCK
    assert guard("tester", write("x.py")) == BLOCK
    assert guard("tester", edit("x.py")) == BLOCK


def test_implementer_gated_on_marker(tmp_path: Path):
    # no marker in this cwd -> Write/Edit blocked; Bash always allowed.
    assert guard("implementer", write("app/x.py"), cwd=tmp_path) == BLOCK
    assert guard("implementer", edit("app/x.py"), cwd=tmp_path) == BLOCK
    assert guard("implementer", bash("rm -rf anything"), cwd=tmp_path) == ALLOW
    # create the marker -> Write/Edit allowed.
    marker = tmp_path / ".obi"
    marker.mkdir()
    (marker / "active-substep").write_text("0.1.5\n")
    assert guard("implementer", write("app/x.py"), cwd=tmp_path) == ALLOW
    assert guard("implementer", edit("app/x.py"), cwd=tmp_path) == ALLOW


def test_none_profile_is_passthrough():
    assert guard("none", write("PROBE.txt")) == ALLOW
    assert guard("none", bash("rm -rf anything")) == ALLOW
    assert guard("none", edit("app/x.py")) == ALLOW
