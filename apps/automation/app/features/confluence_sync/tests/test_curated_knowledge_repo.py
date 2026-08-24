"""PLAN 10.6: the always-present curated knowledge layer's query, proven against the real DB.

Lives here (not in `rag_agent/tests/`, which is deliberately "no network, no DB" per its own
module docstring) to reuse this package's DB test harness — the same placement decision PLAN 10.4
made for `test_retrieval_knowledge_scope.py`. Rows are seeded directly via the ORM, not through any
ingestion path, since this table has no ingestion path of its own (PLAN 10.6's seed script is a
separate, one-off CLI).
"""

from __future__ import annotations

from app.features.rag_agent import fetch_curated_entries
from app.platform.db.engine import get_sessionmaker
from app.platform.db.models import CuratedKnowledgeEntry


def _seed(*, title: str, body: str, tags: list[str], is_active: bool = True) -> int:
    with get_sessionmaker()() as s:
        row = CuratedKnowledgeEntry(title=title, body=body, tags=tags, is_active=is_active)
        s.add(row)
        s.commit()
        return row.id


def test_empty_tags_entry_is_always_included_regardless_of_allowed_scopes() -> None:
    _seed(title="General FAQ", body="Applies everywhere.", tags=[])

    with get_sessionmaker()() as s:
        entries = fetch_curated_entries(s, ["general"], limit=10)
    assert [e.title for e in entries] == ["General FAQ"]

    with get_sessionmaker()() as s:
        entries = fetch_curated_entries(s, ["general", "mews"], limit=10)
    assert [e.title for e in entries] == ["General FAQ"]


def test_scoped_entry_only_returned_when_its_scope_is_allowed() -> None:
    _seed(title="Mews-only note", body="Mews specific.", tags=["mews"])

    with get_sessionmaker()() as s:
        excluded = fetch_curated_entries(s, ["general"], limit=10)
    assert excluded == []

    with get_sessionmaker()() as s:
        included = fetch_curated_entries(s, ["general", "mews"], limit=10)
    assert [e.title for e in included] == ["Mews-only note"]


def test_inactive_entry_is_never_returned() -> None:
    _seed(title="Retired note", body="Stale.", tags=[], is_active=False)

    with get_sessionmaker()() as s:
        entries = fetch_curated_entries(s, ["general"], limit=10)
    assert entries == []


def test_cap_enforcement_limits_the_result_count() -> None:
    for i in range(5):
        _seed(title=f"Note {i}", body="...", tags=[])

    with get_sessionmaker()() as s:
        entries = fetch_curated_entries(s, ["general"], limit=3)
    assert len(entries) == 3


def test_ordering_is_stable_by_id_for_deterministic_citation_numbering() -> None:
    first = _seed(title="Z first", body="...", tags=[])
    second = _seed(title="A second", body="...", tags=[])

    with get_sessionmaker()() as s:
        entries = fetch_curated_entries(s, ["general"], limit=10)
    assert [e.id for e in entries] == sorted([first, second])


def test_two_differently_scoped_entries_never_cross_leak() -> None:
    _seed(title="Mews note", body="...", tags=["mews"])
    _seed(title="Toast note", body="...", tags=["toast"])

    with get_sessionmaker()() as s:
        mews_view = fetch_curated_entries(s, ["general", "mews"], limit=10)
    assert [e.title for e in mews_view] == ["Mews note"]

    with get_sessionmaker()() as s:
        toast_view = fetch_curated_entries(s, ["general", "toast"], limit=10)
    assert [e.title for e in toast_view] == ["Toast note"]
