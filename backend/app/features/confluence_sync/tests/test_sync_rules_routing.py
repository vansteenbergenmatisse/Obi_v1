"""Sync rules 3 + 4 END TO END through the routing axis (panels i2-labels / tg-two / mi-hardfilter,
substep 9.4.1, ADR-0021 Path B).

The ``tags`` sibling (``test_sync_rules_visibility.py``) proves the metadata-only restamp of
``page_source.tags`` with no re-embed. The direct-seed sibling
(``retrieval/tests/test_label_hardfilter_db.py``) proves the ``labels && session_labels`` hard
filter against hand-seeded ``chunk.labels``. Neither drives a label change *through the real sync
path* and then shows the two consequences that rules 3 and 4 actually promise on the routing axis:

* rule 4 — ADD a routing label to an indexed page: ``chunk.labels`` GROWS as a metadata-only change
  (no re-embed, same document_version), and a directed chat whose connection now overlaps the new
  label starts being served the page (routing flips ON);
* rule 3 — REMOVE one routing label while another stays: ``chunk.labels`` SHRINKS as a metadata-only
  change, and the chat whose only overlap was the removed label stops being served the page (routing
  flips OFF), while the chat on the surviving label keeps seeing it.

The connections pivot on the *directed* box: ``toast->mews`` carries ``toast-to-pms`` and
``mews->toast`` carries ``mews-to-pos`` while sharing every general box, so a page labelled with
only the two directed boxes gives an unambiguous, order-independent flip. Assertions are outcomes —
the sync action, stored ``chunk.labels``, the embed-call count, the document_version id, and the
served page id under each connection — never code paths.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once
from app.features.retrieval import HybridRetriever, PrincipalPermissionPolicy
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings
from app.platform.config.product_catalog import load_product_catalog
from schema.engine import get_reader_sessionmaker, get_sessionmaker
from schema.models import KIND_CHILD

from ._helpers import (
    active_version,
    enqueue_sync,
    index_page,
    install_counting_embedder,
    read,
)

pytestmark = pytest.mark.db

# Page 3002 ("Mews PMS Sync Setup", space 300, unrestricted) — the fixture the tags/labels siblings
# use to prove label -> chunk -> retrieval end to end.
_PAGE = 3002
_SPACE = "300"
_QUERY = "Mews PMS Sync Setup"

_CATALOG = load_product_catalog()
# The two connections share every general box; they differ ONLY in the directed box.
_TOAST_TO_MEWS = _CATALOG.build_labels("toast", "mews")  # carries toast-to-pms, not mews-to-pos
_MEWS_TO_TOAST = _CATALOG.build_labels("mews", "toast")  # carries mews-to-pos, not toast-to-pms

_TOAST_BOX = "toast-to-pms"  # the directed box only toast->mews overlaps
_MEWS_BOX = "mews-to-pos"  # the directed box only mews->toast overlaps


def _retriever(settings: Settings) -> HybridRetriever:
    return HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
        trace_sessionmaker=get_sessionmaker(),
    )


def _child_labels(page_id: int) -> set[str]:
    """The raw routing labels stamped on the page's active child chunks (order-independent)."""
    with read() as s:
        rows = (
            s.execute(
                text("SELECT labels FROM chunk WHERE page_id = :p AND is_active AND kind = :k"),
                {"p": page_id, "k": KIND_CHILD},
            )
            .scalars()
            .all()
        )
        assert rows, "no active child chunks indexed"
        label_sets = [frozenset(r) for r in rows]
        assert len(set(label_sets)) == 1, "every chunk of a page carries the same labels"
        return set(label_sets[0])


def _served(settings: Settings, session_labels: list[str]) -> bool:
    """Is page 3002 served to a directed chat carrying these connection labels?"""
    retr = _retriever(settings)
    return str(_PAGE) in retr.retrieve(_QUERY, _SPACE, k=5, session_labels=session_labels)


def test_tags_add_routing_label_routes_page_into_new_connection(gateway, settings, monkeypatch):
    """panel tg-two · substep 9.4.1 (rule 4)
    Adding a routing label to an indexed page grows chunk.labels as a metadata-only change (no
    re-embed, same version) and flips the page INTO a connection that did not overlap it before: a
    toast->mews chat does not see a mews-to-pos-only page, and does see it once toast-to-pms is
    added."""
    gateway.set_labels(_PAGE, [_MEWS_BOX])
    index_page(gateway, settings, _PAGE, version=1)
    version_before = active_version(_PAGE)
    assert version_before is not None
    assert _child_labels(_PAGE) == {_MEWS_BOX}
    # before: the mews->toast chat is served the page; the toast->mews chat is not.
    assert _served(settings, _MEWS_TO_TOAST)
    assert not _served(settings, _TOAST_TO_MEWS)

    counter = install_counting_embedder(monkeypatch, settings)
    gateway.set_labels(_PAGE, [_MEWS_BOX, _TOAST_BOX])  # a label-only edit (no body change)
    enqueue_sync(_PAGE, cf_version=1, key="route-add:3002")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "metadata_only"
    assert counter.calls == 0  # metadata-only: nothing re-embedded
    version_after = active_version(_PAGE)
    assert version_after is not None and version_after.id == version_before.id
    assert _child_labels(_PAGE) == {_MEWS_BOX, _TOAST_BOX}  # chunk.labels GREW
    # after: the toast->mews chat is now served the page (routing flipped ON); mews->toast still is.
    assert _served(settings, _TOAST_TO_MEWS)
    assert _served(settings, _MEWS_TO_TOAST)


def test_tags_remove_routing_label_flips_routing_off_for_that_connection(
    gateway, settings, monkeypatch
):
    """panel i2-labels · substep 9.4.1 (rule 3)
    Removing one routing label while another stays shrinks chunk.labels as a metadata-only change
    (no re-embed, same version) and flips the page OUT of the connection whose only overlap was the
    removed label, while the connection on the surviving label keeps seeing it."""
    gateway.set_labels(_PAGE, [_TOAST_BOX, _MEWS_BOX])
    index_page(gateway, settings, _PAGE, version=1)
    version_before = active_version(_PAGE)
    assert version_before is not None
    assert _child_labels(_PAGE) == {_TOAST_BOX, _MEWS_BOX}
    # before: both directed chats are served the page.
    assert _served(settings, _TOAST_TO_MEWS)
    assert _served(settings, _MEWS_TO_TOAST)

    counter = install_counting_embedder(monkeypatch, settings)
    gateway.set_labels(_PAGE, [_MEWS_BOX])  # editor drops the toast-to-pms box, keeps mews-to-pos
    enqueue_sync(_PAGE, cf_version=1, key="route-remove:3002")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "metadata_only"
    assert counter.calls == 0  # no re-embed
    version_after = active_version(_PAGE)
    assert version_after is not None and version_after.id == version_before.id
    assert _child_labels(_PAGE) == {_MEWS_BOX}  # chunk.labels SHRANK
    # after: the toast->mews chat no longer sees the page (routing flipped OFF); mews->toast still
    # does (its overlap, mews-to-pos, survived).
    assert not _served(settings, _TOAST_TO_MEWS)
    assert _served(settings, _MEWS_TO_TOAST)
