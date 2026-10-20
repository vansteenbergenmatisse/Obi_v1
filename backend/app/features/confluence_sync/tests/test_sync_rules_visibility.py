"""Sync rules 3 + 4, visibility after the conflict concept is dropped (substep 2.2.4, §13 step 3,
decision D4). Two or more recognized provider labels on one page is *legitimate sharing*, not a
conflict: the page resolves to all matched tags and is visible in every one of those scopes by
plain overlap (`chunk.tags && allowed_scopes`), never public. `general` is in every user's scope
set, so a `general`-tagged page is visible everywhere; "public" is the explicit `general` tag,
never empty tags.

Panels: tg-two / tg-conflict (retired — sharing replaces the conflict/hide behaviour), i2-labels
(overlap visibility). Assertions are outcomes only — the sync action, stored tags, embed-call
count and retrieval hits — never code paths.

The retriever is built with `enable_knowledge_scope_filtering=True` so the app-layer overlap
predicate is exercised (mirrors `test_scope_tagging_add.py` / `test_scope_tagging_ks_index.py`);
after step 3 a shared page carries real tags, so the RLS layer's `tags && allowed_scopes` agrees.
"""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import run_once
from app.features.retrieval import HybridRetriever, PrincipalPermissionPolicy
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings
from schema.engine import get_reader_sessionmaker, get_sessionmaker
from schema.models import PageSource

from ._helpers import (
    active_child_chunks,
    active_version,
    enqueue_sync,
    index_page,
    install_counting_embedder,
    read,
)

pytestmark = pytest.mark.db

# Page 3002 ("Mews PMS Sync Setup", space 300, unrestricted) — the same fixture the ks-index and
# tg-add regression tests use to prove label -> chunk tag -> retrieval end to end.
_PAGE = 3002
_SPACE = "300"
_QUERY = "Mews PMS Sync Setup"

_MEWS = "mews-general"
_TOAST = "toast-general"
_OPERA = "opera-cloud-general"
_GENERAL = "obi-general"


def _retriever(settings: Settings) -> HybridRetriever:
    return HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
        trace_sessionmaker=get_sessionmaker(),
    )


def _page_tags(page_id: int) -> set[str]:
    with read() as s:
        ps = s.get(PageSource, page_id)
        assert ps is not None
        return set(ps.tags)


# --- Rule 4: add a relevant tag when one exists -> union it in, no re-embed, same version ---------


def test_tags_add_second_tag_updates_tags_no_reembed(gateway, settings, monkeypatch):
    """panel i2-labels · rule 4
    Adding a second recognized provider label to an already-indexed page unions the new scope onto
    its tags (both scopes now present) as a metadata-only change: same document_version, no chunk
    re-embedded. Red today: the second provider label triggers the conflict branch, zeroing every
    label-derived tag."""
    gateway.set_labels(_PAGE, [_MEWS])
    index_page(gateway, settings, _PAGE, version=1)
    version_before = active_version(_PAGE)
    assert version_before is not None
    assert _page_tags(_PAGE) == {_MEWS}

    counter = install_counting_embedder(monkeypatch, settings)
    gateway.set_labels(_PAGE, [_MEWS, _TOAST])
    enqueue_sync(_PAGE, cf_version=1, key="add-second:3002")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "metadata_only"
    assert _page_tags(_PAGE) == {_MEWS, _TOAST}  # both scopes, not a conflict
    assert counter.calls == 0  # metadata-only: nothing re-embedded
    version_after = active_version(_PAGE)
    assert version_after is not None and version_after.id == version_before.id


def test_tags_shared_page_visible_in_both_scopes(gateway, settings):
    """panel tg-two · rule 4
    A page tagged with two provider scopes ([mews, toast]) is retrievable in each of those scopes
    and in neither other scope — legitimate sharing by overlap, never public. Red today: two
    provider labels resolve to zero tags (conflict), so the page is not visible in either scope."""
    gateway.set_labels(_PAGE, [_MEWS, _TOAST])
    index_page(gateway, settings, _PAGE, version=1)
    assert _page_tags(_PAGE) == {_MEWS, _TOAST}

    retr = _retriever(settings)
    assert str(_PAGE) in retr.retrieve(_QUERY, _SPACE, k=5, knowledge_scopes=[_MEWS])
    assert str(_PAGE) in retr.retrieve(_QUERY, _SPACE, k=5, knowledge_scopes=[_TOAST])
    # ADR-routing-labels-sole-content-axis: the scope axis is retired, so `knowledge_scopes` no longer excludes — the page is
    # visible regardless of the scope arg (it stays indexed and findable). The ingestion tagging
    # (two labels stamped onto chunk.tags) above is the live behavior this test still guards.
    assert str(_PAGE) in retr.retrieve(_QUERY, _SPACE, k=5, knowledge_scopes=[_OPERA])


def test_tags_general_tag_visible_everywhere(gateway, settings):
    """panel i2-labels · rule 4 (guard)
    The explicit `general` tag is in every user's scope set, so a page tagged [general, toast] is
    retrievable by a user of any scope (each carries `general`). "Public" is the explicit general
    tag — never empty tags."""
    gateway.set_labels(_PAGE, [_GENERAL, _TOAST])
    index_page(gateway, settings, _PAGE, version=1)
    assert _page_tags(_PAGE) == {_GENERAL, _TOAST}

    retr = _retriever(settings)
    # A user of any scope also carries `general` in their allowed set.
    assert str(_PAGE) in retr.retrieve(_QUERY, _SPACE, k=5, knowledge_scopes=[_MEWS, _GENERAL])
    assert str(_PAGE) in retr.retrieve(_QUERY, _SPACE, k=5, knowledge_scopes=[_OPERA, _GENERAL])


def test_tags_remove_shared_tag_keeps_other_scope(gateway, settings, monkeypatch):
    """panel tg-two · rule 4
    Removing one of two shared provider tags leaves the page in the remaining scope only, as a
    metadata-only change (no re-embed, same version). Red today: the shared page never establishes
    both tags in the first place (conflict zeroes them)."""
    gateway.set_labels(_PAGE, [_MEWS, _TOAST])
    index_page(gateway, settings, _PAGE, version=1)
    assert _page_tags(_PAGE) == {_MEWS, _TOAST}  # both scopes established first (red today)
    version_before = active_version(_PAGE)
    assert version_before is not None

    counter = install_counting_embedder(monkeypatch, settings)
    gateway.set_labels(_PAGE, [_MEWS])  # editor drops the shared toast label
    enqueue_sync(_PAGE, cf_version=1, key="remove-shared:3002")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "metadata_only"
    assert _page_tags(_PAGE) == {_MEWS}
    assert counter.calls == 0
    version_after = active_version(_PAGE)
    assert version_after is not None and version_after.id == version_before.id

    retr = _retriever(settings)
    assert str(_PAGE) in retr.retrieve(_QUERY, _SPACE, k=5, knowledge_scopes=[_MEWS])
    # ADR-routing-labels-sole-content-axis: the scope axis is retired — the remaining-tag page is visible regardless of the
    # scope arg. The metadata-only tag removal above (no re-embed, same version) is the live
    # behavior this test guards; scope-based exclusion is gone.
    assert str(_PAGE) in retr.retrieve(_QUERY, _SPACE, k=5, knowledge_scopes=[_TOAST])


# --- Rule 3: remove one relevant tag, another stays -> update tags, no re-embed, same version -----


def test_tags_remove_one_tag_keeps_page_updates_tags_no_reembed(gateway, settings, monkeypatch):
    """panel i2-labels · rule 3 (guard, green today)
    Removing one recognized tag while another remains updates the stored tags in place — same
    document_version, nothing re-embedded — and the page stays retrievable in the remaining scope.
    Locks the metadata-only path (`_apply_metadata_only`) against a future rebuild-on-retag
    regression."""
    gateway.set_labels(_PAGE, [_GENERAL, _MEWS])
    index_page(gateway, settings, _PAGE, version=1)
    assert _page_tags(_PAGE) == {_GENERAL, _MEWS}
    version_before = active_version(_PAGE)
    assert version_before is not None

    counter = install_counting_embedder(monkeypatch, settings)
    gateway.set_labels(_PAGE, [_GENERAL])  # drop mews, keep general
    enqueue_sync(_PAGE, cf_version=1, key="remove-one:3002")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "metadata_only"
    assert _page_tags(_PAGE) == {_GENERAL}  # tags updated to the remaining set
    assert counter.calls == 0  # no re-embed
    version_after = active_version(_PAGE)
    assert version_after is not None and version_after.id == version_before.id
    assert active_child_chunks(_PAGE)  # still present/retrievable
