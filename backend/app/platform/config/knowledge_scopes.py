"""Loads the reserved Confluence labels (ADR-routing-labels-sole-content-axis, superseding ADR-knowledge-scope-tagging-and-filtering) from the config file.

ADR-routing-labels-sole-content-axis retired the knowledge-scope `-test` axis: index membership and content routing now ride
the ADR-directed-source-target-routing-labels routing-label axis alone (the `chunk.labels` column, validated against
`product_catalog.json`), so this file no longer carries any offerable knowledge scope. It keeps
only the RESERVED `classified` label. A dedicated file, not an env var: it is a content registry an
operator edits directly, living at `knowledge-base/config/` so it reads as one global place.

Validation (panels tg-config / ks-validate / cm-config). A bad entry stops the backend before it
can serve. At startup, in order, each rule raises with a message that names the offending entry:
  1. every entry is lowercase (an uppercase slug is rejected, not silently lowercased);
  2. no duplicates;
  3. the reserved `classified` scope is present.
`classified` is reserved: it must be in the file, but it is never a recognized/offerable scope —
it is excluded from the returned set, from GET /health, and from any scope list. A body
`knowledge_scope: "classified"` therefore stays an unknown-scope 400, never selectable. The
returned set is normally empty (nothing but `classified` is in the file).
"""

from __future__ import annotations

import json
from pathlib import Path

# backend/app/platform/config/knowledge_scopes.py -> repo root is 4 levels up.
DEFAULT_KNOWLEDGE_SCOPES_PATH = (
    Path(__file__).resolve().parents[4] / "knowledge-base" / "config" / "knowledge_scopes.json"
)

# Reserved scope: present in the file, never recognized/offered. Kept in sync with the forbidden
# integration slug in platform/config/platforms.py (`_FORBIDDEN`).
RESERVED_CLASSIFIED_SCOPE = "classified"


def load_recognized_knowledge_scopes(path: Path = DEFAULT_KNOWLEDGE_SCOPES_PATH) -> frozenset[str]:
    """Validate the tag file at startup and return the recognized, offerable scopes.

    The returned set is every scope in the file EXCEPT the reserved `classified` scope — which,
    post-ADR-routing-labels-sole-content-axis, is normally empty. A failing rule raises ``ValueError`` before ``create_app``
    finishes, so a malformed file exits the process non-zero rather than serving one request under
    wrong permissions.
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

    # 3. the reserved classified scope present (never offered — excluded from the returned set).
    if RESERVED_CLASSIFIED_SCOPE not in seen:
        raise ValueError(
            f"{path} must include the reserved {RESERVED_CLASSIFIED_SCOPE!r} scope "
            f"(got {sorted(seen)!r})"
        )

    return frozenset(seen - {RESERVED_CLASSIFIED_SCOPE})
