"""``scripts/page_state.py`` — the read-only observation tool the sync-rules manual tests
(MT-1..MT-7, ``docs/Final_docs/sync-rules/manual-tests.md``) read from.

A thin operator script, so this is a smoke-level proof that it runs against a real corpus: it dumps
a seeded page (exit 0, reporting its ``document_version`` rows + active chunks + tags) and a
purged/absent page (exit 1, the "NO page_source row" signal a MT reads as "the page was purged").
Driven against the local test DB via this dir's session-scoped conftest, same as the sibling
``test_verify_isolation_script.py``.
"""

from __future__ import annotations

import pytest

import scripts.page_state as page_state
from app.platform.config import Settings

from ._helpers import index_page

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres via this dir's conftest

_PAGE = 1001  # space 100, unrestricted — the fixture page the sibling RLS tests seed


def test_page_state_dumps_an_indexed_page(gateway, settings: Settings, capsys) -> None:
    """An indexed page prints its version rows, active-chunk counts and tags, and exits 0."""
    index_page(gateway, settings, _PAGE, 1)  # commits chunk + page_source rows via the real sync

    rc = page_state.main([str(_PAGE)])
    out = capsys.readouterr().out

    assert rc == 0, out
    assert f"page {_PAGE}" in out
    assert "document_version rows:" in out
    assert "chunks active" in out
    assert "active chunk tags" in out
    assert "(active)" in out  # the active version row is flagged


def test_page_state_reports_an_absent_page_as_exit_1(capsys) -> None:
    """A page with no ``page_source`` row is the purge signal: the message + a non-zero exit."""
    rc = page_state.main(["999999999"])
    out = capsys.readouterr().out

    assert rc == 1
    assert "NO page_source row" in out


def test_page_state_marker_branch_runs(gateway, settings: Settings, capsys) -> None:
    """The optional ``marker`` argument prints the content-match line (MT-6 edit proof)."""
    index_page(gateway, settings, _PAGE, 1)

    rc = page_state.main([str(_PAGE), "obi"])
    out = capsys.readouterr().out

    assert rc == 0, out
    assert "marker 'obi'" in out
    assert "contain it" in out
