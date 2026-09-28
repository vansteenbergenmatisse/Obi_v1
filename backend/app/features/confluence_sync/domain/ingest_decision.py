"""The one decision rule of the trigger layer (pure — no I/O).

Both the webhook worker and the reconciliation sweep call :func:`decide_command`
on a page's **current** state, so the two paths can never disagree — the event
table in ``docs/plans/confluence-trigger-layer.md`` is this one function applied
to the state *after* each event, with only ``reason`` differing.

Membership has two independent gates, both required:

1. **Label gate** (never-bend rule 5, substep 2.2.4): a page is in the index
   only while it carries at least one recognized knowledge-scope label. The
   reserved ``classified`` label always removes.
2. **Authorization gate** (the allow-list lives in ``source_scope``): a covering
   ``source_scope`` row must authorize the tag. A row's ``tags`` are the
   allow-list for its coverage; **empty tags authorize every recognized scope**
   in that coverage (Decision D3 — preserves the existing empty-tag roots).

The stamped ``scopes`` are ``recognized_labels ∩ authorized`` — the intersection,
not a union. This is what makes an all-scopes space root behave as an allow-list
(a page labelled ``obi-mews-test`` under a space row authorizing all four scopes
is stamped only ``obi-mews-test``, not all four), rather than over-sharing the
page into every scope the root permits.

The "unrestricted" fall-through (no ``source_scope`` row for the space at all)
authorizes every recognized scope, which keeps the common no-scoping case
behaving exactly as label-only stamping did before roots existed.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.platform.clients import ConfluencePageMeta
from app.platform.config import RESERVED_CLASSIFIED_SCOPE
from app.shared.sync_command import SyncCommand
from schema.models import SourceScope

from .scope_resolver import ROOT_TYPE_SPACE

_CURRENT_STATUS = "current"


def _norm(labels: Iterable[str]) -> set[str]:
    return {label.strip().lower() for label in labels if label and label.strip()}


def _row_covers(row: SourceScope, space_id: int, self_and_ancestor_ids: set[int]) -> bool:
    """Does one ``source_scope`` row cover this page?

    A ``space`` root covers every page whose ``space_id`` matches ``root_id``. A
    ``page`` root covers the page only when the root page id is the page itself or
    one of its ancestors (subtree coverage — the single-page analogue of
    ``scope_resolver.resolve_scope_roots``).
    """
    try:
        root_id = int(row.root_id)
    except (TypeError, ValueError):
        return False
    if row.root_type == ROOT_TYPE_SPACE:
        return root_id == int(space_id)
    return root_id in self_and_ancestor_ids


def authorized_tags(
    space_id: int,
    self_and_ancestor_ids: set[int],
    space_rows: list[SourceScope],
    recognized: frozenset[str],
) -> set[str] | None:
    """The scopes a covering ``source_scope`` row permits for this page.

    Returns ``None`` when the space has **no** rows at all (unrestricted — every
    recognized scope is allowed, today's default). Otherwise returns the explicit
    set of authorized tags, which may be empty:

    * rows exist but none active → ``set()`` (the space was scoped and every root
      deactivated → purge everything, mirroring ``resolve_space_scope``);
    * rows active but none cover this page → ``set()`` (page is outside every
      root's coverage in a scoped space);
    * a covering row with empty ``tags`` → all recognized scopes (D3).
    """
    if not space_rows:
        return None  # unrestricted
    active = [row for row in space_rows if row.is_active]
    if not active:
        return set()  # scoped, but the last root was deactivated → purge
    authorized: set[str] = set()
    covered = False
    for row in active:
        if not _row_covers(row, space_id, self_and_ancestor_ids):
            continue
        covered = True
        row_tags = _norm(row.tags)
        authorized |= row_tags if row_tags else set(recognized)  # D3: empty = all
    if not covered:
        return set()
    return authorized


def resolve_scopes(
    meta: ConfluencePageMeta | None,
    labels: list[str],
    space_rows: list[SourceScope],
    self_and_ancestor_ids: set[int],
    recognized: frozenset[str],
) -> set[str]:
    """The knowledge scopes to stamp on this page, or ``set()`` if it does not belong.

    Empty result means "not in the index" — the caller emits a ``delete``.
    """
    if meta is None:
        return set()
    if meta.status != _CURRENT_STATUS:
        return set()  # draft / archived / trashed / deleted → not in the index
    norm_labels = _norm(labels)
    if RESERVED_CLASSIFIED_SCOPE in norm_labels:
        return set()  # sync rule 7: the reserved label always removes
    recognized_labels = norm_labels & recognized
    if not recognized_labels:
        return set()  # rule 5: membership requires a recognized label
    authorized = authorized_tags(meta.space_id, self_and_ancestor_ids, space_rows, recognized)
    if authorized is None:
        return recognized_labels  # unrestricted space → labels are the scopes
    return recognized_labels & authorized


def should_ingest(
    meta: ConfluencePageMeta | None,
    labels: list[str],
    space_rows: list[SourceScope],
    self_and_ancestor_ids: set[int],
    recognized: frozenset[str],
) -> bool:
    return bool(resolve_scopes(meta, labels, space_rows, self_and_ancestor_ids, recognized))


def decide_command(
    page_id: int,
    meta: ConfluencePageMeta | None,
    labels: list[str],
    space_rows: list[SourceScope],
    self_and_ancestor_ids: set[int],
    recognized: frozenset[str],
    reason: str,
) -> SyncCommand:
    """Turn a page's current state into an ``upsert`` or ``delete`` command.

    ``delete`` is idempotent (a hard purge that no-ops on an unindexed page), so
    every "not in the index" case — gone, drafted, untagged, unauthorized,
    moved out of scope — collapses to the same command; only ``reason`` differs.
    """
    scopes = resolve_scopes(meta, labels, space_rows, self_and_ancestor_ids, recognized)
    if not scopes:
        return SyncCommand(page_id=page_id, action="delete", scopes=(), reason=reason)
    return SyncCommand(
        page_id=page_id, action="upsert", scopes=tuple(sorted(scopes)), reason=reason
    )
