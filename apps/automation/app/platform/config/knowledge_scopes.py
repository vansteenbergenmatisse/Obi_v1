"""Loads the recognized knowledge-scope tags (PLAN 10, ADR-0011) from a dedicated config file.

Deliberately a dedicated file, not an env var: this is a content registry (which integration
platforms exist) an operator edits directly, not a per-deployment secret or runtime toggle —
those stay in `.env` (`enable_knowledge_scope_filtering`, `default_knowledge_scope`). It lives at
the repo-root `config/` (not nested under `apps/automation`) so it reads as one global place
regardless of which app you're looking at — `apps/web` can read the same file later (e.g. the
PLAN 10.8 scope-switcher UI) instead of duplicating the list.
"""

from __future__ import annotations

import json
from pathlib import Path

# apps/automation/app/platform/config/knowledge_scopes.py -> repo root is 5 levels up.
DEFAULT_KNOWLEDGE_SCOPES_PATH = (
    Path(__file__).resolve().parents[5] / "config" / "knowledge_scopes.json"
)


def load_recognized_knowledge_scopes(path: Path = DEFAULT_KNOWLEDGE_SCOPES_PATH) -> frozenset[str]:
    data = json.loads(path.read_text())
    names = frozenset(
        str(entry["name"]).strip().lower() for entry in data["scopes"] if str(entry["name"]).strip()
    )
    if "obi-general-test" not in names:
        raise ValueError(f"{path} must include a 'obi-general-test' scope (got {sorted(names)!r})")
    return names
