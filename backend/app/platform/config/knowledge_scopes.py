"""Loads the recognized knowledge-scope tags (PLAN 10, ADR-0011) from a dedicated config file.

Deliberately a dedicated file, not an env var: this is a content registry (which integration
platforms exist) an operator edits directly, not a per-deployment secret or runtime toggle —
those stay in `.env` (`enable_knowledge_scope_filtering`, `default_knowledge_scope`). It lives at
`knowledge-base/config/` so it reads as one global place regardless of which app you're looking at
— `frontend` reads the same file (the PLAN 10.8 scope-switcher UI generates its list from this JSON
at build time, substep 1.2.2) instead of duplicating the list.

Validation (substep 1.2.1, panels tg-config / ks-validate / cm-config). The file decides what a
person may see, so a bad entry stops the backend before it can leak. At startup, in order, each
rule raises with a message that names the offending entry:
  1. every entry is lowercase (an uppercase slug is rejected, not silently lowercased);
  2. no duplicates;
  3. the general scope (`obi-general-test`) is present;
  4. the reserved `classified` scope is present.
`classified` is reserved: it must be in the file, but it is never a recognized/offerable scope —
it is excluded from the returned set, from GET /health, and from the widget's scope list. A body
`knowledge_scope: "classified"` therefore stays an unknown-scope 400, never selectable.
"""

from __future__ import annotations

import json
from pathlib import Path

# backend/app/platform/config/knowledge_scopes.py -> repo root is 4 levels up.
DEFAULT_KNOWLEDGE_SCOPES_PATH = (
    Path(__file__).resolve().parents[4] / "knowledge-base" / "config" / "knowledge_scopes.json"
)

# The always-present base scope (ADR-0011): untagged content falls into it and it is always allowed.
GENERAL_SCOPE = "obi-general-test"
# Reserved scope: present in the file, never recognized/offered. Kept in sync with the forbidden
# integration slug in platform/config/platforms.py (`_FORBIDDEN`).
RESERVED_CLASSIFIED_SCOPE = "classified"


def load_recognized_knowledge_scopes(path: Path = DEFAULT_KNOWLEDGE_SCOPES_PATH) -> frozenset[str]:
    """Validate the tag file at startup and return the recognized, offerable scopes.

    The returned set is every scope in the file EXCEPT the reserved `classified` scope. A failing
    rule raises ``ValueError`` before ``create_app`` finishes, so a malformed file exits the
    process non-zero rather than serving one request under wrong permissions.
    """
    data = json.loads(path.read_text())
    names: list[str] = []
    for entry in data["scopes"]:
        name = str(entry["name"]).strip()
        if name:
            names.append(name)

    # 1. every entry lowercase — name the offending entry.
    for name in names:
        if name != name.lower():
            raise ValueError(f"{path}: knowledge scope {name!r} must be lowercase")

    # 2. no duplicates — name the offending entry.
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ValueError(f"{path}: knowledge scope {name!r} is listed more than once")
        seen.add(name)

    # 3. the general scope present.
    if GENERAL_SCOPE not in seen:
        raise ValueError(f"{path} must include the {GENERAL_SCOPE!r} scope (got {sorted(seen)!r})")

    # 4. the reserved classified scope present (never offered — excluded from the returned set).
    if RESERVED_CLASSIFIED_SCOPE not in seen:
        raise ValueError(
            f"{path} must include the reserved {RESERVED_CLASSIFIED_SCOPE!r} scope "
            f"(got {sorted(seen)!r})"
        )

    return frozenset(seen - {RESERVED_CLASSIFIED_SCOPE})
