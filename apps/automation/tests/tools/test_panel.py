"""Tests for tools/panel.py — the design-panel reader/updater.

Hermetic: every test drives panel.py as a subprocess against a synthetic HTML
fixture written to a tmp dir. No network, no sleep, no real design file.
Covers print, --list, --grep, and the in-place update, and asserts every byte
outside the JSON block is identical after an update.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PANEL_PY = Path(__file__).resolve().parents[2] / "tools" / "panel.py"

# A "·" keeps ensure_ascii=False in the byte-identity assertion honest.
PANELS: dict[str, dict] = {
    "r5-coverage": {
        "n": "Retrieval stage 5",
        "h": "Coverage check on the final context",
        "st": "build",
        "today": "Does not exist. One strong passage is treated as enough.",
        "simple": "Checks every part · a part with no passage is named undocumented.",
        "f": [["Owner", "stage 5, on the final context"], ["Band", "0.35"]],
        "files": [["rag_agent/domain/coverage.py", "decide_coverage (proposed)"]],
        "s": ["Stage 1 listed the parts.", "Score each part against the band."],
        "t": ["Ask with no rollback passage: the answer says rollback is undocumented."],
        "c": "def decide_coverage(parts):\n    return 'answer'",
        "note": "Relevant and sufficient are different things.",
    },
    "i1-ledger": {
        "n": "Step",
        "h": "The event ledger",
        "st": "built",
        "simple": "Writes every ring down once. A repeat ring is ignored.",
        "f": [["Dedup key", "delivery_id"]],
        "t": ["Same delivery id, different payload: dedupes quietly."],
    },
    "x-empty": {
        "n": "Step",
        "h": "Empty panel",
        "st": "discuss",
        "simple": "Nothing yet.",
    },
}

PREFIX = "<!doctype html>\n<h1>before the block · leave me alone</h1>\n"
OPEN = '<script type="application/json" id="nodedata">'
CLOSE = "</script>"
SUFFIX = "\n<footer>after the block · leave me alone</footer>\n"

NODEDATA_RE = re.compile(rf"{re.escape(OPEN)}(.*?){re.escape(CLOSE)}", re.S)


def _write_fixture(tmp_path: Path) -> Path:
    body = json.dumps(PANELS, ensure_ascii=False, indent=0)
    html = PREFIX + OPEN + body + CLOSE + SUFFIX
    path = tmp_path / "obi-rag-system-flow.html"
    path.write_text(html, encoding="utf-8")
    return path


def _run(fixture: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PANEL_PY), "--file", str(fixture), *args],
        capture_output=True,
        text=True,
    )


def test_panel_print_returns_only_that_panel(tmp_path: Path) -> None:
    """Printing one id renders that panel and no other."""
    fixture = _write_fixture(tmp_path)
    result = _run(fixture, "r5-coverage")
    assert result.returncode == 0, result.stderr
    assert "Coverage check on the final context" in result.stdout
    assert "`r5-coverage`" in result.stdout
    # nothing from a different panel leaks in
    assert "The event ledger" not in result.stdout
    assert "Empty panel" not in result.stdout


def test_panel_list_one_line_per_panel(tmp_path: Path) -> None:
    """--list prints exactly one `id | title | status` line per panel."""
    fixture = _write_fixture(tmp_path)
    result = _run(fixture, "--list")
    assert result.returncode == 0, result.stderr
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == len(PANELS)
    assert all(ln.count(" | ") == 2 for ln in lines)
    assert lines[0] == "r5-coverage | Coverage check on the final context | build"
    assert {ln.split(" | ")[0] for ln in lines} == set(PANELS)


def test_panel_grep_prints_matching_ids_only(tmp_path: Path) -> None:
    """--grep prints the ids whose text mentions the word, and only those."""
    fixture = _write_fixture(tmp_path)
    rollback = _run(fixture, "--grep", "rollback")
    assert rollback.returncode == 0, rollback.stderr
    assert rollback.stdout.split() == ["r5-coverage"]

    dedup = _run(fixture, "--grep", "dedupes")
    assert dedup.stdout.split() == ["i1-ledger"]

    none = _run(fixture, "--grep", "no-such-word-anywhere")
    assert none.stdout.strip() == ""


def test_panel_update_changes_two_fields_and_leaves_the_rest_identical(
    tmp_path: Path,
) -> None:
    """--status and --today rewrite exactly two fields; every other byte holds."""
    fixture = _write_fixture(tmp_path)
    original = fixture.read_text(encoding="utf-8")

    new_today = "Rule on part scores, Haiku for unsure parts. Shipped in 3.6.2."
    result = _run(fixture, "r5-coverage", "--status", "built", "--today", new_today)
    assert result.returncode == 0, result.stderr
    assert "r5-coverage.st" in result.stdout
    assert "r5-coverage.today" in result.stdout

    updated = fixture.read_text(encoding="utf-8")
    orig_json = NODEDATA_RE.search(original).group(1)  # type: ignore[union-attr]
    new_json = NODEDATA_RE.search(updated).group(1)  # type: ignore[union-attr]

    # everything outside the JSON block is byte-identical
    assert original[: original.index(orig_json)] == updated[: updated.index(new_json)]
    assert (
        original[original.index(orig_json) + len(orig_json) :]
        == updated[updated.index(new_json) + len(new_json) :]
    )

    # exactly the two fields on the one panel changed; nothing else did
    before = json.loads(orig_json)
    after = json.loads(new_json)
    assert after["r5-coverage"]["st"] == "built"
    assert after["r5-coverage"]["today"] == new_today
    for pid in PANELS:
        for field in set(before[pid]) | set(after[pid]):
            if pid == "r5-coverage" and field in {"st", "today"}:
                continue
            assert before[pid][field] == after[pid][field]


def test_panel_status_only_leaves_today_untouched(tmp_path: Path) -> None:
    """--status alone changes the status and nothing else."""
    fixture = _write_fixture(tmp_path)
    result = _run(fixture, "r5-coverage", "--status", "unverified")
    assert result.returncode == 0, result.stderr
    after = json.loads(NODEDATA_RE.search(fixture.read_text("utf-8")).group(1))  # type: ignore[union-attr]
    assert after["r5-coverage"]["st"] == "unverified"
    assert after["r5-coverage"]["today"] == PANELS["r5-coverage"]["today"]


def test_panel_unknown_id_fails(tmp_path: Path) -> None:
    """An unknown id is an error for both print and update, not a silent pass."""
    fixture = _write_fixture(tmp_path)
    printed = _run(fixture, "no-such-panel")
    assert printed.returncode != 0
    assert "no-such-panel" in printed.stderr

    updated = _run(fixture, "no-such-panel", "--status", "built")
    assert updated.returncode != 0


def test_panel_rejects_unknown_status_word(tmp_path: Path) -> None:
    """--status only accepts the five status words."""
    fixture = _write_fixture(tmp_path)
    result = _run(fixture, "r5-coverage", "--status", "shipped")
    assert result.returncode != 0
    assert "shipped" in result.stderr
