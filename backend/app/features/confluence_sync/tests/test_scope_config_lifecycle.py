"""Recognized-label CONFIG lifecycle: the recognized routing-label set gains or loses a label.

Membership tests elsewhere (test_sync_rules_membership.py) change a PAGE's labels; this file
changes the RECOGNIZED SET and proves what happens to pages already in the index. The operator
edit is simulated by patching ``ProductCatalog.all_routing_labels`` to return exactly the edited
set (ADR-routing-labels-sole-content-axis retired the knowledge_scopes.json tag map), so
``settings.product_catalog.all_routing_labels()`` — read by the worker and both sweeps — serves
the edited set exactly as a deploy of an edited product catalog would.

Panels: tg-config (the recognized label list tells stage 2 which labels count), ks-sweep (sweeps
as the safety net), tg-classified (the reserved label), tg-add. Never-bend rule 5: a page is in
the index for one reason — published and carrying a recognized routing label.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.features.confluence_sync.application.reconciliation import (
    KIND_COMPLETE,
    KIND_LIGHTWEIGHT,
    run_reconciliation,
)
from app.features.confluence_sync.application.sync_service import SyncOutcome
from app.features.confluence_sync.application.worker import RunResult, run_once
from schema.engine import session_scope
from schema.models import PageSource

from ._helpers import (
    active_child_chunks,
    active_version,
    count_versions,
    enqueue_sync,
    index_page,
    install_counting_embedder,
    page_row_counts,
    read,
    run_worker,
)

pytestmark = pytest.mark.db

_ZERO_ROWS = {
    "chunk": 0,
    "document_version": 0,
    "document": 0,
    "page_source": 0,
    "page_restriction": 0,
}

_SPACE = 300
# Fixture page with the single recognized label "mews-general" (page-3002-mews-general.json).
_MEWS_PAGE = 3002
# Fixture page carrying no label at all (page-3007-unlabeled.json).
_UNLABELED_PAGE = 3007
# Every space-300 fixture page, so a sweep-driven test can isolate the one page it is about.
_SPACE_PAGES = (3001, 3002, 3003, 3004, 3005, 3006, 3007, 3008, 3009, 3010)


def _isolate_space_to(gateway, page_id: int) -> None:
    """Hide every other space-300 fixture page so a sweep sees exactly the page under test."""
    for pid in _SPACE_PAGES:
        if pid != page_id:
            gateway.hide(pid)


def _set_recognized(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, names: list[str]) -> None:
    """Simulate the operator changing the recognized membership set.

    ADR-routing-labels-sole-content-axis: membership is the ROUTING-label set the worker and both
    sweeps read from
    ``settings.product_catalog.all_routing_labels()`` (the old knowledge_scopes.json axis is
    retired). A redeploy that adds/removes a product changes that set; here we patch
    ``ProductCatalog.all_routing_labels`` to return exactly ``names`` so the shrunk/grown set flows
    through the real membership path (``resolve_scopes`` / discovery) unchanged.
    """
    from app.platform.config.product_catalog import ProductCatalog

    recognized = frozenset(names)
    monkeypatch.setattr(ProductCatalog, "all_routing_labels", lambda self: recognized, raising=True)


def _outcome_for(results: list[RunResult], page_id: int) -> SyncOutcome:
    for result in results:
        outcome = result.outcome
        if isinstance(outcome, SyncOutcome) and outcome.page_id == page_id:
            return outcome
    raise AssertionError(f"no SyncOutcome for page {page_id} in {results!r}")


def test_tags_scope_removed_from_config_purges_on_complete_sweep(
    gateway, settings, monkeypatch, tmp_path
):
    """panel tg-config · never-bend rule 5
    A scope removed from the recognized routing-label set stops counting: a page indexed under it
    (and carrying no
    other recognized label) is hard-purged — page_source, document_version and chunk all gone —
    when the COMPLETE sweep re-enqueues it and the worker re-derives membership against the
    shrunk recognized set."""
    _isolate_space_to(gateway, _MEWS_PAGE)
    index_page(gateway, settings, _MEWS_PAGE, version=1)
    assert active_child_chunks(_MEWS_PAGE)  # indexed under mews-general first

    # The operator removes mews-general from knowledge_scopes.json.
    _set_recognized(monkeypatch, tmp_path, ["obi-general", "opera-cloud-general", "toast-general"])
    assert (
        "mews-general" not in settings.product_catalog.all_routing_labels()
    )  # the edit took effect

    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_COMPLETE, space_ids=[_SPACE]
        )
        assert run.jobs_enqueued >= 1  # complete sweep re-verifies every candidate

    results = run_worker(gateway, settings)
    assert _outcome_for(results, _MEWS_PAGE).action == "purged"
    assert page_row_counts(_MEWS_PAGE) == _ZERO_ROWS


def test_tags_scope_removed_lightweight_sweep_does_not_catch_it(
    gateway, settings, monkeypatch, tmp_path
):
    """panel tg-config / ks-sweep · documents the known purge window
    A scope removed from the recognized routing-label set is NOT caught by the LIGHTWEIGHT (daily)
    sweep: the page
    shows no cheap drift signal (version/status/parent/title unchanged), so nothing is enqueued
    and its stale rows remain retrievable until the COMPLETE sweep (every
    ``complete_recon_interval_days``, default 14 days) re-verifies it. This test PINS that
    window deliberately: any future fix that closes it (e.g. a config-change signal that drives
    the lightweight sweep, or an immediate purge on scope removal) MUST consciously update this
    test — going red here means the window changed, which is the point."""
    _isolate_space_to(gateway, _MEWS_PAGE)
    index_page(gateway, settings, _MEWS_PAGE, version=1)
    rows_before = page_row_counts(_MEWS_PAGE)
    assert rows_before["page_source"] == 1
    assert rows_before["chunk"] > 0

    _set_recognized(monkeypatch, tmp_path, ["obi-general", "opera-cloud-general", "toast-general"])
    assert "mews-general" not in settings.product_catalog.all_routing_labels()

    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_LIGHTWEIGHT, space_ids=[_SPACE]
        )
        assert run.jobs_enqueued == 0  # no drift signal -> the lightweight sweep enqueues nothing

    assert run_worker(gateway, settings) == []  # queue is empty: the worker never saw the page
    assert page_row_counts(_MEWS_PAGE) == rows_before  # stale rows remain (the pinned window)


def test_tags_scope_added_already_indexed_page_restamped_by_complete_sweep(
    gateway, settings, monkeypatch, tmp_path
):
    """panel tg-config / tg-add · substep D.0 (roadmap step 5, gap A)
    A page indexed under scope A while also carrying label B (B not yet in the recognized
    routing-label set) IS
    retroactively stamped with B when B is added to the recognized routing-label set: the COMPLETE
    sweep re-enqueues
    the page, the trigger re-derives scopes = {A, B}, and the handler sees the stamped tags
    disagree with ``cmd.scopes`` — a metadata-only restamp (same document_version, zero embed
    calls), never a rebuild. The LIGHTWEIGHT sweep still enqueues nothing (no cheap drift signal
    fires on a config-only edit — that window remains and is pinned by the scope-removed test
    above). A second complete sweep after the restamp is ``no_change`` (no churn)."""
    _isolate_space_to(gateway, _MEWS_PAGE)
    # Phase 1: only mews-general is recognized; the page carries mews + toast labels.
    _set_recognized(monkeypatch, tmp_path, ["obi-general", "mews-general"])
    gateway.set_labels(_MEWS_PAGE, ["mews-general", "toast-general"])
    index_page(gateway, settings, _MEWS_PAGE, version=1)

    with read() as s:
        ps = s.get(PageSource, _MEWS_PAGE)
        assert ps is not None
        assert ps.tags == ["mews-general"]  # toast not recognized yet -> not stamped
        doc_version_before = ps.active_doc_version_id
    assert doc_version_before is not None

    # Phase 2: the operator adds toast-general to the recognized routing-label set.
    _set_recognized(monkeypatch, tmp_path, ["obi-general", "mews-general", "toast-general"])
    assert "toast-general" in settings.product_catalog.all_routing_labels()
    counter = install_counting_embedder(monkeypatch, settings)

    # Lightweight sweep: no drift signal -> page untouched (this window stays).
    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_LIGHTWEIGHT, space_ids=[_SPACE]
        )
        assert run.jobs_enqueued == 0
    run_worker(gateway, settings)
    with read() as s:
        ps = s.get(PageSource, _MEWS_PAGE)
        assert ps is not None
        assert ps.tags == ["mews-general"]

    # Complete sweep: labels_hash is unchanged but cmd.scopes now includes toast -> restamp.
    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_COMPLETE, space_ids=[_SPACE]
        )
        assert run.jobs_enqueued >= 1
    results = run_worker(gateway, settings)
    assert _outcome_for(results, _MEWS_PAGE).action == "metadata_only"

    with read() as s:
        ps = s.get(PageSource, _MEWS_PAGE)
        assert ps is not None
        assert ps.tags == ["mews-general", "toast-general"]  # restamped to both scopes
        assert ps.active_doc_version_id == doc_version_before  # same version, no rebuild
    chunks = active_child_chunks(_MEWS_PAGE)
    assert chunks
    assert all(c.tags == ["mews-general", "toast-general"] for c in chunks)
    assert counter.calls == 0  # a restamp is metadata-only: no re-embed by either sweep

    # Idempotence: a second complete sweep finds tags already matching -> no_change, no churn.
    with session_scope() as s:
        run = run_reconciliation(
            s, gateway=gateway, settings=settings, kind=KIND_COMPLETE, space_ids=[_SPACE]
        )
        assert run.jobs_enqueued >= 1
    results = run_worker(gateway, settings)
    assert _outcome_for(results, _MEWS_PAGE).action == "no_change"
    assert counter.calls == 0


def test_tags_classified_removed_reindexes_as_first_build(gateway, settings, monkeypatch):
    """panel tg-classified · never-bend rules 4 + 5 (closes soft gap 5b)
    The literal classified round-trip on one page: indexed -> classified label added (hard
    purge, every row gone) -> classified removed with the recognized label still present ->
    re-indexed as a genuine FIRST build: a NEW document_version id, exactly one version row,
    and every child chunk embedded from scratch (rule 4: no vector reused from before the
    purge)."""
    index_page(gateway, settings, _MEWS_PAGE, version=1)
    version_before = active_version(_MEWS_PAGE)
    assert version_before is not None
    old_version_id = version_before.id
    assert page_row_counts(_MEWS_PAGE)["chunk"] > 0

    # classified added -> sync rule 7: the reserved label always removes, rows go to zero.
    gateway.set_labels(_MEWS_PAGE, ["mews-general", "classified"])
    enqueue_sync(_MEWS_PAGE, cf_version=1, key="classified-add:3002")
    result = run_once(gateway, settings, owner="test")
    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "purged"
    assert page_row_counts(_MEWS_PAGE) == _ZERO_ROWS

    # classified removed (recognized label still present) -> full first build, NEW version id.
    counter = install_counting_embedder(monkeypatch, settings)
    gateway.set_labels(_MEWS_PAGE, ["mews-general"])
    enqueue_sync(_MEWS_PAGE, cf_version=1, key="classified-removed:3002")
    result = run_once(gateway, settings, owner="test")
    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "indexed"

    version_after = active_version(_MEWS_PAGE)
    assert version_after is not None
    assert version_after.id != old_version_id  # a NEW document_version, not a resurrected one
    assert count_versions(_MEWS_PAGE) == 1  # a true first build: exactly one version row exists
    built = active_child_chunks(_MEWS_PAGE)
    assert built
    assert counter.texts == len(built)  # every child embedded fresh — no vector reused (rule 4)


def test_tags_mixed_case_label_normalized_end_to_end(gateway, settings):
    """panel ks-index / tg-add · rule 5
    A label arriving from the gateway with stray case and whitespace ("  OBI-General ")
    is normalized by the real worker path — the page indexes, and both page_source.tags and
    every chunk's tags are stamped with the canonical lowercase 'obi-general'."""
    gateway.set_labels(_UNLABELED_PAGE, ["  OBI-General "])
    gateway.set_version(_UNLABELED_PAGE, 1)
    enqueue_sync(_UNLABELED_PAGE, cf_version=1, key="mixedcase:3007")
    result = run_once(gateway, settings, owner="test")

    assert result is not None and isinstance(result.outcome, SyncOutcome)
    assert result.outcome.action == "indexed"
    with read() as s:
        ps = s.get(PageSource, _UNLABELED_PAGE)
        assert ps is not None
        assert ps.tags == ["obi-general"]  # stamped canonical, not the raw gateway string
    chunks = active_child_chunks(_UNLABELED_PAGE)
    assert chunks
    assert all(chunk.tags == ["obi-general"] for chunk in chunks)
