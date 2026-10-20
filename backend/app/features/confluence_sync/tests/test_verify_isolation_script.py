"""Phase 13.2: ``setup_supabase.verify_isolation`` must gate the *full* reader read-path.

``verify_isolation`` is the live-Supabase operator step 5. Beyond chunk default-deny / scoping it
now also proves the reader can resolve pgvector types (the dense-query path — broken on Supabase
until the ``extensions`` GRANT, NEXT FIXES #1), can read its non-``chunk`` page-ACL + curated tables
(migration 0009 ``*_reader_read`` policy), and that an ``anon``-like public REST role stays denied.

Driven here against the local test DB (pgvector in ``public``, reader has ``USAGE``; no ``anon``
role), where the reader's positive read-path holds and the anon check is a documented skip-as-pass
— so a green run asserts every new check actually executed, not just the pre-existing chunk logic.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

import scripts.setup_supabase as setup_supabase
from app.platform.config import Settings
from schema.engine import get_sessionmaker

from ._helpers import index_page

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_PAGE = 1001  # space 100, unrestricted — the fixture page the sibling RLS tests seed


def _set_chunk_tags(page_id: int, tags: list[str]) -> None:
    with get_sessionmaker()() as s:
        s.execute(
            text("UPDATE chunk SET tags = :tags WHERE page_id = :pid"),
            {"tags": tags, "pid": page_id},
        )
        s.commit()


def test_verify_isolation_passes_and_runs_reader_readpath_checks(
    gateway, settings: Settings, capsys
) -> None:
    """A loaded corpus with a healthy reader passes; every 13.2 check runs with a pass detail."""
    index_page(gateway, settings, _PAGE, 1)  # commits chunk + page_source rows via the real sync
    # The 2.2.4 membership gate stamps a recognized tag on every indexed page, but this test
    # exercises the script's UNTAGGED-corpus branch (the "no tagged chunks -> scope check
    # skip-as-pass" path, still reachable for pre-2.2.4 empty-tags rows until the step-4 backfill).
    # Force the corpus back to empty tags directly, bypassing the ingestion gate.
    _set_chunk_tags(_PAGE, [])

    rc = setup_supabase.verify_isolation()
    out = capsys.readouterr().out

    assert rc == 0, out
    # Pre-existing chunk isolation still gated.
    assert "reader, no GUC" in out
    # 13.2 additions each executed and passed.
    assert "reader halfvec" in out and "resolves halfvec" in out
    assert "reader non-chunk" in out and "reader reads its non-chunk tables" in out
    assert "anon role" in out and "anon-denied check N/A" in out  # no `anon` role locally
    # The knowledge-scope axis is retired (ADR-routing-labels-sole-content-axis, migration 0018
    # drops its policies): the script no longer measures it, so it can never fail on it.
    assert "scope axis" not in out


def test_verify_isolation_passes_on_a_tagged_corpus_without_a_scope_check(
    gateway, settings: Settings, capsys
) -> None:
    """ADR-routing-labels-sole-content-axis: migration 0018 dropped the knowledge-scope RLS
    policies, so on a live database a tagged chunk is no longer hidden by scope. The script must
    not test that retired axis (it would report a false leak, exit 8, on every tagged corpus); the
    source-axis and reader checks still run and pass."""
    index_page(gateway, settings, _PAGE, 1)
    _set_chunk_tags(_PAGE, ["mews-general"])

    rc = setup_supabase.verify_isolation()
    out = capsys.readouterr().out

    assert rc == 0, out
    assert "reader, no GUC" in out
    assert "scope axis" not in out
    assert "out-of-scope" not in out
