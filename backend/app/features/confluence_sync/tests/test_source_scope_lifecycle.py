"""The ``source_scope`` row lifecycle, end to end through the real sweeps (PLAN 3.5.6).

A root's ``tags`` are the authorization allow-list its coverage intersects with
(``ingest_decision.authorized_tags``). These tests pin what actually happens to already-stamped
pages when an operator edits a row after the fact:

* narrowing a root's tags fires **no** lightweight drift signal (``reconciliation._needs_sync``
  checks version/status/parent/title only), so stale tags — and the RLS visibility they grant —
  survive the lightweight sweep: a real, documented eventual-consistency window;
* the complete sweep re-enqueues everything, and since the §D.0 scope-restamp fix the handler
  compares ``cmd.scopes`` against the stamped tags: a mismatch takes the metadata-only restamp
  path (tags corrected on page_source + chunks, same version, zero embeds), closing the revoked
  scope's RLS visibility at the complete-sweep cadence;
* a space whose only active root is a page-root for a *different* subtree authorizes nothing for
  an uncovered page (``authorized_tags`` → ``set()``), so the sweep + worker purge it.

Driven against the local test DB via this dir's session-scoped conftest.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.features.confluence_sync.application.reconciliation import (
    KIND_COMPLETE,
    KIND_LIGHTWEIGHT,
    run_reconciliation,
)
from schema.engine import get_reader_sessionmaker, session_scope
from schema.models import PageSource, SourceScope

from ._helpers import (
    active_child_chunks,
    active_version,
    index_page,
    install_counting_embedder,
    run_worker,
)

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres via this dir's conftest

_PAGE = 1001  # space 100, parentless root page of the generic fixture space
_SPACE = 100
_TAG_A = "obi-mews-test"
_TAG_B = "obi-toast-test"


def _add_root(root_type: str, root_id: str, *, tags: list[str]) -> int:
    with session_scope() as s:
        row = SourceScope(root_type=root_type, root_id=root_id, tags=tags)
        s.add(row)
        s.flush()
        return row.id


def _set_root_tags(row_id: int, tags: list[str]) -> None:
    with session_scope() as s:
        row = s.get(SourceScope, row_id)
        assert row is not None
        row.tags = tags


def _index_page_with_both_tags_under_covering_root(gateway, settings) -> int:
    """Index _PAGE stamped {A, B} under a space root authorizing both. Returns the root's id."""
    root_id = _add_root("space", str(_SPACE), tags=[_TAG_A, _TAG_B])
    gateway.set_labels(_PAGE, [_TAG_A, _TAG_B])
    index_page(gateway, settings, _PAGE, 1)
    chunks = active_child_chunks(_PAGE)
    assert chunks, "setup: the page must index under the covering root"
    assert all(c.tags == sorted([_TAG_A, _TAG_B]) for c in chunks), "setup: both scopes stamped"
    return root_id


def _reader_chunk_count_under_scope(scope: str) -> int:
    """How many of _PAGE's chunks the RLS-subject ``rag_reader`` sees under one scope GUC."""
    reader = get_reader_sessionmaker()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
        s.execute(
            text("SELECT set_config('app.allowed_knowledge_scopes', :scope, true)"),
            {"scope": scope},
        )
        return s.execute(
            text("SELECT count(*) FROM chunk WHERE page_id = :p AND is_active"), {"p": _PAGE}
        ).scalar_one()


def test_tags_narrowed_root_lightweight_sweep_leaves_stale_tags(gateway, settings) -> None:
    """Narrowing a root's tags is invisible to the lightweight sweep — the documented
    eventual-consistency window.

    ``reconciliation._needs_sync`` (reconciliation.py:70-77) checks version / status / parent /
    title only; a ``source_scope.tags`` edit moves none of them, so the lightweight sweep enqueues
    nothing and the chunks keep the revoked scope — which still satisfies the RLS ``tags &&``
    overlap, so a scope-B reader still sees the page (the leak window is real). A future fix that
    closes this window (a tags drift signal, or restamping on root edit) must consciously update
    this test to assert the new, tighter behavior."""
    root_id = _index_page_with_both_tags_under_covering_root(gateway, settings)

    _set_root_tags(root_id, [_TAG_A])  # operator narrows the allow-list: B is revoked

    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_LIGHTWEIGHT, space_ids=[_SPACE]
        )
        # No cheap drift signal fires on a root-tags-only change: _PAGE is neither drifted nor
        # new. (The sweep may still legitimately enqueue OTHER pages — e.g. 1002, newly covered
        # by the space root and discovered for the first time — so the assertion is per-page,
        # not jobs_enqueued == 0.)
        report = run.report
        assert report is not None
        assert _PAGE not in report["drifted_pages"]
        assert _PAGE not in report["new_pages"]
    results = run_worker(gateway, settings)  # drain whatever else the sweep found
    assert all(getattr(r.outcome, "page_id", None) != _PAGE for r in results), (
        "no sync job may have run for the narrowed page on the lightweight cadence"
    )

    chunks = active_child_chunks(_PAGE)
    assert chunks
    assert all(c.tags == sorted([_TAG_A, _TAG_B]) for c in chunks), (
        "stale tags expected: the lightweight sweep must not notice a root-tags edit"
    )

    # The stale tag still satisfies the RLS overlap for the revoked scope B — rag_reader with
    # only the GUCs set (no app predicate) still reads the page under B.
    assert _reader_chunk_count_under_scope(_TAG_B) > 0, (
        "revoked scope no longer sees the page -> the window closed; update this test consciously"
    )
    assert _reader_chunk_count_under_scope(_TAG_A) > 0  # the kept scope, of course, still does


def test_tags_narrowed_root_complete_sweep_restamps_and_closes_the_leak(
    gateway, settings, monkeypatch
) -> None:
    """panel tg-config / ks-sweep · substep D.0 (roadmap step 5, gap B)
    Narrowing a root's allow-list reaches already-stamped pages at the complete-sweep cadence:
    the sweep re-enqueues the unchanged page, ``decide_command`` re-derives scopes =
    recognized_labels ∩ authorized = {A}, and the handler — comparing ``cmd.scopes`` to the
    stamped tags — takes the metadata-only restamp path: tags become {A} on page_source AND
    every active chunk, the revoked scope B loses RLS visibility (rag_reader under B reads 0
    rows), with no rebuild and no re-embed (same ``document_version``, zero embed calls —
    never-bend rule 4's cost guarantee holds). A second complete sweep is ``no_change``."""
    root_id = _index_page_with_both_tags_under_covering_root(gateway, settings)
    version_before = active_version(_PAGE)
    assert version_before is not None

    _set_root_tags(root_id, [_TAG_A])
    counter = install_counting_embedder(monkeypatch, settings)  # installed after the first index

    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_COMPLETE, space_ids=[_SPACE]
        )
        assert run.jobs_enqueued >= 1  # the complete sweep re-enqueues the unchanged page too
    results = run_worker(gateway, settings)

    # The page WAS re-synced — and the sync restamped the narrowed scopes, metadata-only.
    page_outcomes = [r.outcome for r in results if getattr(r.outcome, "page_id", None) == _PAGE]
    assert page_outcomes, "the complete sweep must enqueue the page for a re-check"
    assert all(getattr(o, "action", None) == "metadata_only" for o in page_outcomes), (
        "the complete sweep must restamp a narrowed root's tags (the §D.0 fix)"
    )

    chunks = active_child_chunks(_PAGE)
    assert chunks
    assert all(c.tags == [_TAG_A] for c in chunks), (
        "the revoked scope must be removed from every active chunk's tags"
    )
    with session_scope() as s:
        ps = s.get(PageSource, _PAGE)
        assert ps is not None
        assert ps.tags == [_TAG_A]

    # The leak window is closed at the RLS level: rag_reader under the revoked scope B reads
    # nothing, while the kept scope A still reads the page.
    assert _reader_chunk_count_under_scope(_TAG_B) == 0, (
        "revoked scope B must no longer satisfy the RLS overlap after the restamp"
    )
    assert _reader_chunk_count_under_scope(_TAG_A) > 0

    version_after = active_version(_PAGE)
    assert version_after is not None
    assert version_after.id == version_before.id, "no rebuild: same document_version stays active"
    assert counter.calls == 0, "no re-embed: the sweep must never spend embedding cost on this"

    # Idempotence: with tags now matching, the next complete sweep is a pure no_change.
    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_COMPLETE, space_ids=[_SPACE]
        )
        assert run.jobs_enqueued >= 1
    results = run_worker(gateway, settings)
    page_outcomes = [r.outcome for r in results if getattr(r.outcome, "page_id", None) == _PAGE]
    assert page_outcomes
    assert all(getattr(o, "action", None) == "no_change" for o in page_outcomes)
    assert counter.calls == 0


def test_tags_space_root_active_but_not_covering_page_purges(gateway, settings) -> None:
    """In a scoped space, an active root that does not cover the page authorizes nothing.

    ``authorized_tags`` has three ``set()`` legs; this pins the space-variant one: rows exist and
    are active, but the only root is a page-root for a different subtree, so ``covered`` stays
    False and the function returns ``set()`` — the worker's ``decide_command`` turns that into a
    delete and the previously-indexed, still-labelled page is hard-purged (never-bend rule 5's
    authorization gate: membership needs a covering root once the space is scoped)."""
    index_page(gateway, settings, _PAGE, 1)  # unrestricted space (no rows yet) -> indexed
    assert active_child_chunks(_PAGE)

    # The space becomes scoped, but its only active root is 1002's subtree — 1002 is _PAGE's
    # child, so the root never covers _PAGE (self_and_ancestor_ids of 1001 is just {1001}).
    _add_root("page", "1002", tags=[_TAG_B])

    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_COMPLETE, space_ids=[_SPACE]
        )
        assert run.jobs_enqueued >= 1  # the still-labelled page is re-enqueued for the re-check
    run_worker(gateway, settings)

    assert active_child_chunks(_PAGE) == [], "uncovered page in a scoped space must be purged"
    with session_scope() as s:
        assert s.get(PageSource, _PAGE) is None, "purge is hard: the registry row goes too"
