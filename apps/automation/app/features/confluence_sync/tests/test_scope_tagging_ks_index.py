"""panel ks-index · substep p0-s0_5-reg-knowledge-scopes

`tg-first` already proves a first build resolves the recognized label into the chunk tag
(`test_scope_tagging_first.py::test_tg_first_page_indexed_with_tags_already_resolved`), and the
i2/i3/i4 stage panels each prove their own slice of "stages 2 to 4 ran". Neither proves the
`ks-index` panel's own third check end to end: that the page which just went through the *real*
label-driven tagging pipeline (no tag stamped by hand) is actually retrievable through the
knowledge-scope filter for its own scope. `test_retrieval_knowledge_scope.py` proves the retrieval
predicate itself, but deliberately stamps `chunk.tags` via raw SQL to isolate the predicate from
the tagging pipeline (see that file's module docstring) — so it never exercises the two together.
This test closes that gap.
"""

from __future__ import annotations

import pytest

from app.features.confluence_sync.application.worker import run_once
from app.features.retrieval import HybridRetriever, PrincipalPermissionPolicy
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings
from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker
from app.platform.db.models import PageSource

from ._helpers import active_child_chunks, active_version, enqueue_sync, index_page, read

pytestmark = pytest.mark.db

# Page 3002 ("Mews PMS Sync Setup", space 300, unrestricted) carries the real Confluence label
# "obi-mews-test" in its fixture, which config/knowledge_scopes.json recognizes as a knowledge
# scope — same page `tg-first` uses to prove the label resolves to the chunk tag.
_MEWS_PAGE = 3002
_MEWS_SPACE = "300"

# Page 3004 ("Toast POS Menu Sync", space 300, unrestricted) is a separate fixture from the two
# tests above, carrying the recognized label "obi-toast-test". Used only by the two tests below,
# which exercise the queued job itself (enqueue_sync + run_once) rather than the index_page
# convenience wrapper, so the assertions below are pinned to the queued job driving stages 2-4,
# not merely to whatever index_page happens to do internally.
_TOAST_PAGE = 3004
_TOAST_SPACE = "300"


def _retriever(*, enable_knowledge_scope_filtering: bool) -> HybridRetriever:
    settings = Settings()
    return HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
        enable_knowledge_scope_filtering=enable_knowledge_scope_filtering,
        trace_sessionmaker=get_sessionmaker(),
    )


def test_ks_index_page_tagged_by_real_pipeline_is_searchable_in_its_scope(
    gateway, settings: Settings
) -> None:
    """panel ks-index · substep p0-s0_5-reg-knowledge-scopes
    A page that goes through the queued sync — stages 2 to 4 — comes out carrying the recognized
    label as a chunk tag (no tag stamped by hand), and a caller allowed for that same knowledge
    scope can then find it through the knowledge-scope-filtered retriever.
    """
    index_page(gateway, settings, _MEWS_PAGE, version=1)

    # Check (b): the chunk tag came from the real label pipeline, not a manual SQL stamp.
    chunks = active_child_chunks(_MEWS_PAGE)
    assert chunks and all("obi-mews-test" in c.tags for c in chunks)

    # Check (c): the page is now searchable within its own recognized knowledge scope.
    retr = _retriever(enable_knowledge_scope_filtering=True)
    hits = retr.retrieve(
        "Mews PMS Sync Setup",
        _MEWS_SPACE,
        k=5,
        knowledge_scopes=["obi-mews-test"],
    )
    assert str(_MEWS_PAGE) in hits


def test_ks_index_page_not_searchable_outside_its_scope(gateway, settings: Settings) -> None:
    """panel ks-index · substep p0-s0_5-reg-knowledge-scopes
    Negative case for the same real-pipeline-tagged page: a caller allowed only for a different
    knowledge scope does not find it — the scope the page actually landed in is the one that
    resolves it, not any scope.
    """
    index_page(gateway, settings, _MEWS_PAGE, version=1)

    retr = _retriever(enable_knowledge_scope_filtering=True)
    hits = retr.retrieve(
        "Mews PMS Sync Setup",
        _MEWS_SPACE,
        k=5,
        knowledge_scopes=["obi-toast-test"],
    )
    assert str(_MEWS_PAGE) not in hits


def test_ks_index_queued_job_runs_stages_2_to_4_on_the_page(gateway, settings: Settings) -> None:
    """panel ks-index · substep p0-s0_5-reg-knowledge-scopes
    The queued job runs ingestion stages 2 to 4 on the page: enqueuing a real sync_page job for a
    fresh, not-yet-indexed page and running the worker once (the queued job itself, not the
    index_page convenience wrapper) leaves the page with a stage-2 PageSource carrying its
    recognized tag, stage-3 active child chunks, and a stage-4 active document_version."""
    gateway.set_version(_TOAST_PAGE, 1)  # fresh page, never indexed before this test
    enqueue_sync(_TOAST_PAGE, 1, key=f"sync:{_TOAST_PAGE}:v1")

    result = run_once(gateway, settings, owner="test")
    assert result is not None
    assert result.status == "succeeded"

    # Stage 2 (fetch/tag): a PageSource row exists and carries the recognized label.
    with read() as s:
        page_source = s.get(PageSource, _TOAST_PAGE)
        assert page_source is not None
        assert "obi-toast-test" in page_source.tags

    # Stage 3 (chunk/contextualize): active chunks exist for the page.
    chunks = active_child_chunks(_TOAST_PAGE)
    assert chunks

    # Stage 4 (version/activate): the page now has an active document_version.
    assert active_version(_TOAST_PAGE) is not None


def test_ks_index_chunk_tags_carry_the_recognized_label(gateway, settings: Settings) -> None:
    """panel ks-index · substep p0-s0_5-reg-knowledge-scopes
    Tags on the chunks are the recognized labels: after the queued sync_page job runs the real
    tagging pipeline (no tag stamped by hand), every active child chunk's own `tags` field --
    not just `page_source.tags` -- contains the recognized label."""
    gateway.set_version(_TOAST_PAGE, 1)  # fresh page, never indexed before this test
    enqueue_sync(_TOAST_PAGE, 1, key=f"sync:{_TOAST_PAGE}:v1")

    result = run_once(gateway, settings, owner="test")
    assert result is not None
    assert result.status == "succeeded"

    chunks = active_child_chunks(_TOAST_PAGE)
    assert chunks and all("obi-toast-test" in c.tags for c in chunks)
