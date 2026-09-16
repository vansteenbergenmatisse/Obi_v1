"""PLAN 10.7: the corpus-readiness check that gates flipping
``enable_knowledge_scope_filtering`` on in any environment with real content.

Proven against the real DB (same harness/`index_page` style as
`test_retrieval_knowledge_scope.py`): a live chunk whose tags overlap none of the recognized
knowledge scopes would silently vanish from every scoped result once the flag is on (ADR-0011
Decision 1 — ``general`` is always in the allowed set but is never inferred for an untagged chunk),
so `verify_knowledge_scope_coverage` must count it as untagged and report the corpus not-ready.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.features.confluence_sync.application.knowledge_scope_backfill import (
    verify_knowledge_scope_coverage,
)
from app.platform.config import Settings
from app.platform.db.engine import get_sessionmaker

from ._helpers import index_page

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_ONBOARDING_PAGE = 1001  # space 100, unrestricted
_EXPENSE_PAGE = 2001  # space 200, unrestricted

# The recognized set is loaded from config in production; tests pin it explicitly so a change to
# the committed config/knowledge_scopes.json can't silently alter what "tagged" means here.
_RECOGNIZED = frozenset(
    {"obi-general-test", "obi-mews-test", "obi-operacloud-test", "obi-toast-test"}
)


def _set_chunk_tags(page_id: int, tags: list[str]) -> None:
    with get_sessionmaker()() as s:
        s.execute(
            text("UPDATE chunk SET tags = :tags WHERE page_id = :pid"),
            {"tags": tags, "pid": page_id},
        )
        s.commit()


def _coverage(session):
    return verify_knowledge_scope_coverage(session, recognized_scopes=_RECOGNIZED)


def _active_chunk_count(page_id: int) -> int:
    """All active chunks for a page — parents *and* children — since the readiness gate must
    account for every live row that carries (or should carry) the scope tag, not only kind=1
    child chunks."""
    with get_sessionmaker()() as s:
        return int(
            s.execute(
                text("SELECT count(*) FROM chunk WHERE is_active AND page_id = :pid"),
                {"pid": page_id},
            ).scalar_one()
        )


def test_all_active_chunks_scope_tagged_is_ready(gateway, settings: Settings, session) -> None:
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_tags(_ONBOARDING_PAGE, ["obi-general-test"])

    cov = _coverage(session)

    assert cov.total_active_chunks > 0
    assert cov.untagged_active_chunks == 0
    assert cov.untagged_page_ids == []
    assert cov.is_ready is True


def test_untagged_active_chunk_is_not_ready(gateway, settings: Settings, session) -> None:
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_tags(_ONBOARDING_PAGE, [])  # no scope tag at all, not even "general"

    cov = _coverage(session)

    assert cov.total_active_chunks == _active_chunk_count(_ONBOARDING_PAGE) > 0
    assert cov.untagged_active_chunks == cov.total_active_chunks
    assert _ONBOARDING_PAGE in cov.untagged_page_ids
    assert cov.is_ready is False


def test_source_scope_tag_alone_does_not_count(gateway, settings: Settings, session) -> None:
    """A page carrying only its `source_scope`-derived tag (`base`, PLAN 3.5.6) but no knowledge
    scope must still read as not-ready — `base` is not a recognized knowledge scope, so the filter
    would exclude it. This is the whole reason 10.7 is a manual relabel, not a no-op."""
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_tags(_ONBOARDING_PAGE, ["base"])

    cov = _coverage(session)

    assert cov.untagged_active_chunks == cov.total_active_chunks
    assert _ONBOARDING_PAGE in cov.untagged_page_ids
    assert cov.is_ready is False


@pytest.mark.parametrize(
    "scope", ["obi-general-test", "obi-mews-test", "obi-operacloud-test", "obi-toast-test"]
)
def test_each_recognized_scope_tag_counts(gateway, settings: Settings, session, scope: str) -> None:
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_tags(_ONBOARDING_PAGE, [scope])

    cov = _coverage(session)

    assert cov.untagged_active_chunks == 0
    assert cov.is_ready is True


def test_partial_coverage_lists_only_untagged_pages(gateway, settings: Settings, session) -> None:
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    index_page(gateway, settings, _EXPENSE_PAGE, 4)
    _set_chunk_tags(_ONBOARDING_PAGE, ["obi-general-test"])
    _set_chunk_tags(_EXPENSE_PAGE, [])  # left untagged

    cov = _coverage(session)

    expense_chunks = _active_chunk_count(_EXPENSE_PAGE)
    assert cov.untagged_page_ids == [_EXPENSE_PAGE]
    assert cov.untagged_active_chunks == expense_chunks
    assert cov.total_active_chunks > cov.untagged_active_chunks
    assert cov.is_ready is False


def test_inactive_untagged_chunks_are_ignored(gateway, settings: Settings, session) -> None:
    """The gate is about *live* content only — retrieval reads `is_active` chunks (PLAN 10.7 note,
    `_base_filters`), so a superseded/inactive untagged chunk must not block the flip."""
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    index_page(gateway, settings, _EXPENSE_PAGE, 4)
    _set_chunk_tags(_ONBOARDING_PAGE, ["obi-general-test"])
    _set_chunk_tags(_EXPENSE_PAGE, [])
    # deactivate the untagged page's chunks: they no longer participate in retrieval.
    with get_sessionmaker()() as s:
        s.execute(
            text("UPDATE chunk SET is_active = false WHERE page_id = :pid"),
            {"pid": _EXPENSE_PAGE},
        )
        s.commit()

    cov = _coverage(session)

    assert cov.untagged_active_chunks == 0
    assert _EXPENSE_PAGE not in cov.untagged_page_ids
    assert cov.is_ready is True


def test_empty_corpus_is_vacuously_ready(session) -> None:
    cov = _coverage(session)

    assert cov.total_active_chunks == 0
    assert cov.untagged_active_chunks == 0
    assert cov.is_ready is True
