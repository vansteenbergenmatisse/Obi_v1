"""Doc-integrity regression for the docs/Final_docs/brief operator runbooks (panel cm-config).

The Phase-4 embed-security clean-exit requires the brief runbooks to match the implemented
code. These runbooks (add-an-integration, add-a-host-platform, localhost-test) are dense with
repo-relative code links; a rename or a move silently rots them — exactly the failure already seen
in docs/embedding/obi-embed-local-test-keys.md, whose apps/web / apps/automation paths no longer
exist. This test extracts every backtick-quoted repo path from the brief and asserts it resolves,
so a maintainer who moves the referenced code is forced to update the runbook in the same change.

Deterministic, no network, no database: pure filesystem inspection of committed files.
"""

from __future__ import annotations

import re
from pathlib import Path

# repo root = first ancestor holding both docs/ and knowledge-base/ (robust to test relocation).
_here = Path(__file__).resolve()
REPO_ROOT = next(
    p for p in _here.parents if (p / "docs").is_dir() and (p / "knowledge-base").is_dir()
)
BRIEF_DIR = REPO_ROOT / "docs" / "Final_docs" / "brief"

# A backtick token is treated as a repo path when it starts with a known root and looks concrete
# (no glob, placeholder, whitespace, or shell metacharacter).
_ROOTS = ("backend/", "frontend/", "knowledge-base/", "docs/", ".github/", "packages/")
# Fenced code blocks (```...```) must be removed BEFORE matching inline `code` spans: their triple
# backticks otherwise desync inline-backtick pairing, so a broken link can slip through depending on
# its position in the file (a false-confidence bug this test itself must not have).
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_BACKTICK = re.compile(r"`([^`]+)`")
_REJECT = set(" *<>{}()|$\"'")


def _looks_like_repo_path(token: str) -> bool:
    return token.startswith(_ROOTS) and "/" in token and not any(c in _REJECT for c in token)


def _repo_paths_in(text: str) -> set[str]:
    out: set[str] = set()
    text = _FENCE.sub("", text)  # drop fenced code blocks so inline backticks pair cleanly
    for raw in _BACKTICK.findall(text):
        token = raw.strip().rstrip(".,:;")
        if _looks_like_repo_path(token):
            out.add(token)
    return out


def test_platforms_brief_dir_holds_the_three_runbooks():
    """panel cm-config · substep p4-embed-brief
    The docs/Final_docs/brief folder exists and carries the index plus the three operator runbooks
    the embed clean-exit names."""
    assert BRIEF_DIR.is_dir(), "docs/Final_docs/brief/ is missing"
    for name in (
        "README.md",
        "add-an-integration.md",
        "add-a-host-platform.md",
        "localhost-test.md",
    ):
        assert (BRIEF_DIR / name).is_file(), f"docs/Final_docs/brief/{name} is missing"


def test_platforms_brief_runbooks_reference_only_real_repo_paths():
    """panel cm-config · substep p4-embed-brief
    Every backtick-quoted repo path in the brief runbooks resolves to a file or directory that
    exists — the runbooks match the implemented code, and a moved/renamed target rots the test, not
    a reader's afternoon."""
    missing: list[str] = []
    checked = 0
    for md in sorted(BRIEF_DIR.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        for path in sorted(_repo_paths_in(text)):
            checked += 1
            if not (REPO_ROOT / path).exists():
                missing.append(f"{md.name}: {path}")
    assert checked > 0, "no repo paths were extracted — the matcher or the docs regressed"
    assert not missing, "brief runbooks reference paths that do not exist:\n" + "\n".join(missing)
