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

from sqlalchemy import text

import scripts.setup_supabase as setup_supabase
from app.platform.config import Settings
from app.platform.db.engine import get_sessionmaker

from ._helpers import index_page

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

    rc = setup_supabase.verify_isolation()
    out = capsys.readouterr().out

    assert rc == 0, out
    # Pre-existing chunk isolation still gated.
    assert "reader, no GUC" in out
    # 13.2 additions each executed and passed.
    assert "reader halfvec" in out and "resolves halfvec" in out
    assert "reader non-chunk" in out and "reader reads its non-chunk tables" in out
    assert "anon role" in out and "anon-denied check N/A" in out  # no `anon` role locally
    # ADR-0014 scope axis: untagged corpus -> the scope check is a documented skip-as-pass.
    assert "scope axis" in out and "no tagged chunks" in out


def test_verify_isolation_proves_scope_isolation_on_tagged_corpus(
    gateway, settings: Settings, capsys
) -> None:
    """ADR-0014 / 0010 backstop: a chunk tagged for one knowledge scope is invisible to the reader
    under any other scope, yet still passes the source-axis checks (which opt out via the '*'
    wildcard). Before the extension, the source-axis `scoped` count collapsed to 0 on a tagged
    corpus (the RESTRICTIVE scope policy denies tagged rows with no scope GUC) and rc was non-zero.
    """
    index_page(gateway, settings, _PAGE, 1)
    _set_chunk_tags(_PAGE, ["obi-mews-test"])

    rc = setup_supabase.verify_isolation()
    out = capsys.readouterr().out

    assert rc == 0, out  # source axis survives a tagged corpus (scope GUC set to '*')
    assert "scope axis" in out
    assert "in-scope" in out and "out-of-scope" in out  # the scope isolation was measured
