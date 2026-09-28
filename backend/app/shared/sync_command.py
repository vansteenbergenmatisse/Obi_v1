"""The contract between the Confluence trigger layer and the ingestion layer.

This is the ONLY thing the two features share. The trigger layer
(``app.features.confluence_sync``) watches Confluence and decides *what should
happen* to a page; the ingestion layer (``app.features.ingestion``) takes a
:class:`SyncCommand` and does the work (fetch, chunk, embed, version, swap, or
purge). Neither feature imports the other — both import these pure types from
``app.shared`` (which imports no feature and no platform, per the shared
contract in ``app/shared/__init__.py``).

Design decisions recorded on the command (see ``docs/plans/confluence-trigger-layer.md``):

* **D1** — the shape below: ``page_id``, ``action``, ``scopes``, ``reason``.
* **scopes is authoritative** — the trigger computes ``recognized_labels ∩
  authorized_tags`` and the ingestion layer stamps exactly those; it never
  re-derives membership. ``()`` for a ``delete``.
* **delete is a hard purge** (owner decision, 2026-09-25): ``delete`` removes
  every row for the page, and is idempotent — purging a page that isn't indexed
  is a no-op. That idempotency is what lets the whole event table collapse to a
  single decision rule on the page's *current* state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# The closed reason vocabulary (D5). Every command records why it was produced;
# only ``reason`` differs across the event→command table — the decision itself is
# a pure function of the page's current state.
Reason = Literal[
    "tag_added",
    "tag_removed",
    "edited",
    "page_gone",
    "moved_out_of_scope",
    "moved_into_scope",
    "back_to_draft",
    "sweep_drift",
    "sweep_discovery",
    "reconcile",
]

VALID_REASONS: frozenset[str] = frozenset(Reason.__args__)  # type: ignore[attr-defined]


@dataclass(frozen=True)
class SyncCommand:
    """A decided action for one page — the only value that crosses the layer boundary.

    ``scopes`` carries the authoritative knowledge-scope tags for an ``upsert``
    (``recognized_labels ∩ authorized_tags``); it is always empty for a
    ``delete``.
    """

    page_id: int
    action: Literal["upsert", "delete"]
    scopes: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SyncOutcome:
    """What the ingestion layer actually did with a :class:`SyncCommand`.

    ``action`` values mirror the pre-split handler for continuity of assertions
    and traces: ``indexed | metadata_only | no_change | purged | gone |
    skipped``. ``classes`` are the change-detection classes that drove the work
    (empty for a pure purge/skip).
    """

    action: str
    classes: list[str]
    page_id: int | None
