"""Raw routing labels on every chunk (panel mi-labels, substep 9.1.2 / Option A Stage 3).

The directed-connection hard filter (ADR-0020) routes a chat on the raw Confluence labels a page
was published with, NOT the resolved knowledge-scope ``tags``. This stage lands the storage: a
``labels text[]`` column stamped from the unresolved ``gateway.get_labels`` output, kept strictly
distinct from ``tags`` (the recognized-scope ∩ authorized set). Three things must hold:

* a build stamps the raw labels onto every chunk (and the page_source registry row);
* a label-only change restamps ``labels`` over the metadata-only path — no re-embed, same
  document_version (ADR-0020 D3, exactly as ``tags`` already restamp);
* the backfill is idempotent — safe to run twice over existing chunks.

Assertions are outcomes only — stored labels, the sync action, the embed-call count, row counts —
never code paths. Mirrors ``test_sync_rules_visibility.py`` (the ``tags`` sibling).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once
from schema.engine import session_scope
from schema.models import KIND_CHILD, PageSource

from ._helpers import (
    active_version,
    enqueue_sync,
    index_page,
    install_counting_embedder,
    page_row_counts,
    read,
)

pytestmark = pytest.mark.db

# Page 3002 ("Mews PMS Sync Setup", space 300, unrestricted) — the fixture the tags siblings use.
_PAGE = 3002
# ADR-0021: membership/recognition is the routing-label axis.
_MEWS = "mews-general"
_GENERAL = "obi-general"
_EXTRA = "extra-raw-label"  # a real Confluence label that is NOT a recognized routing label


def _page_labels(page_id: int) -> list[str]:
    with read() as s:
        ps = s.get(PageSource, page_id)
        assert ps is not None
        return list(ps.labels)


def _page_tags(page_id: int) -> set[str]:
    with read() as s:
        ps = s.get(PageSource, page_id)
        assert ps is not None
        return set(ps.tags)


def _active_child_labels(page_id: int) -> list[list[str]]:
    with read() as s:
        rows = (
            s.execute(
                text(
                    "SELECT labels FROM chunk WHERE page_id = :p AND is_active AND kind = :k "
                    "ORDER BY seq"
                ),
                {"p": page_id, "k": KIND_CHILD},
            )
            .scalars()
            .all()
        )
        return [list(r) for r in rows]


def test_in2_chunk_carries_raw_labels(gateway, settings):
    """panel mi-labels · substep 9.1.2
    After a build, every chunk (and the page_source row) carries the exact raw Confluence labels
    the page was published with, kept distinct from the resolved knowledge-scope tags. Red today:
    there is no ``labels`` column — the raw labels are dropped at ingestion."""
    gateway.set_labels(_PAGE, [_MEWS, _EXTRA])
    index_page(gateway, settings, _PAGE, version=1)

    # raw labels land verbatim (recognized + unrecognized), on page_source and every chunk
    assert _page_labels(_PAGE) == [_MEWS, _EXTRA]
    child_labels = _active_child_labels(_PAGE)
    assert child_labels, "no active child chunks indexed"
    assert all(labels == [_MEWS, _EXTRA] for labels in child_labels)
    # ...and are strictly distinct from the resolved scope tags (only the recognized label resolves)
    assert _page_tags(_PAGE) == {_MEWS}


def test_in2_label_only_change_restamps_labels_no_reembed(gateway, settings, monkeypatch):
    """panel mi-labels · substep 9.1.2 (D3)
    Adding a raw Confluence label to an indexed page restamps ``labels`` as a metadata-only change:
    same document_version, nothing re-embedded. Red today: no ``labels`` column to restamp."""
    gateway.set_labels(_PAGE, [_GENERAL])
    index_page(gateway, settings, _PAGE, version=1)
    version_before = active_version(_PAGE)
    assert version_before is not None
    assert _page_labels(_PAGE) == [_GENERAL]

    counter = install_counting_embedder(monkeypatch, settings)
    gateway.set_labels(_PAGE, [_GENERAL, _EXTRA])  # a label-only edit (no body change)
    enqueue_sync(_PAGE, cf_version=1, key="relabel:3002")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "metadata_only"
    assert _page_labels(_PAGE) == [_GENERAL, _EXTRA]  # raw labels restamped
    assert all(labels == [_GENERAL, _EXTRA] for labels in _active_child_labels(_PAGE))
    assert counter.calls == 0  # metadata-only: nothing re-embedded
    version_after = active_version(_PAGE)
    assert version_after is not None and version_after.id == version_before.id
    assert _page_tags(_PAGE) == {_GENERAL}  # tags unchanged — the extra label is not a scope


def test_in2_backfill_labels_twice_is_idempotent(gateway, settings):
    """panel mi-labels · substep 9.1.2
    The backfill stamps the raw labels onto existing chunks whose ``labels`` are empty (the
    pre-0016 state), and running it a second time is a safe no-op — identical final labels, no
    duplicated or lost rows. Red today: the backfill (and the column it fills) does not exist."""
    from app.features.ingestion import backfill_labels

    gateway.set_labels(_PAGE, [_MEWS, _EXTRA])
    index_page(gateway, settings, _PAGE, version=1)

    # simulate the pre-migration state: the column exists but the active rows were never stamped
    with session_scope() as s:
        s.execute(text("UPDATE chunk SET labels = '{}'::text[] WHERE page_id = :p"), {"p": _PAGE})
        s.execute(
            text("UPDATE page_source SET labels = '{}'::text[] WHERE page_id = :p"), {"p": _PAGE}
        )
    assert _page_labels(_PAGE) == []

    counts_before = page_row_counts(_PAGE)

    first = backfill_labels(gateway)
    labels_after_first = _active_child_labels(_PAGE)
    assert _page_labels(_PAGE) == [_MEWS, _EXTRA]
    assert all(labels == [_MEWS, _EXTRA] for labels in labels_after_first)
    assert first.pages_stamped == 1

    second = backfill_labels(gateway)  # running twice must be safe
    assert _active_child_labels(_PAGE) == labels_after_first  # identical final state
    assert _page_labels(_PAGE) == [_MEWS, _EXTRA]
    assert second.pages_stamped == 0  # nothing left to change
    assert page_row_counts(_PAGE) == counts_before  # no rows created or destroyed
