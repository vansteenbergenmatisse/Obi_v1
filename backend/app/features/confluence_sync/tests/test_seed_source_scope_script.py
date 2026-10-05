"""``scripts/seed_source_scope.py`` — the operator seed for ``source_scope`` rows (PLAN 3.5.6).

Rows in ``source_scope`` are one-off operator-owned (no CRUD API yet, per the approved design
spec), so this script is the only writer. These tests prove its three contracts against the real
local test DB: insert (a ``space`` root with empty tags is the all-scopes root, Decision D3),
idempotent upsert keyed on ``(root_type, root_id)`` (``uq_source_scope_root``), and the two
teardown paths (``--deactivate`` flips ``is_active`` only; ``--delete`` removes the row). Driven
against the local test DB via this dir's session-scoped conftest, same as the sibling
``test_page_state_script.py``.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

import scripts.seed_source_scope as seed_script
from schema.engine import session_scope
from schema.models import SourceScope

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres via this dir's conftest


def _fetch_rows(root_type: str, root_id: str) -> list[dict[str, Any]]:
    """Every row for one root, as plain dicts (safe to read after the session closes)."""
    with session_scope() as s:
        rows = (
            s.execute(
                select(SourceScope).where(
                    SourceScope.root_type == root_type, SourceScope.root_id == root_id
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": r.id,
                "root_type": r.root_type,
                "root_id": r.root_id,
                "source_type": r.source_type,
                "tags": list(r.tags),
                "label": r.label,
                "is_active": r.is_active,
            }
            for r in rows
        ]


def test_tags_seed_script_inserts_row() -> None:
    """``seed()`` creates one row with the given fields; a space root seeded with no tags is the
    all-scopes root (empty ``tags`` authorize every recognized scope — Decision D3)."""
    row_id = seed_script.seed(root_type="space", root_id="100", label="Engineering")

    rows = _fetch_rows("space", "100")
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == row_id
    assert row["root_type"] == "space"
    assert row["root_id"] == "100"
    assert row["source_type"] == "confluence"
    assert row["tags"] == []  # empty tags = all recognized scopes (D3), the whole-space default
    assert row["label"] == "Engineering"
    assert row["is_active"] is True


def test_tags_seed_script_upsert_updates_in_place() -> None:
    """Re-running ``seed()`` for the same ``(root_type, root_id)`` updates the existing row in
    place (tags, label, is_active) — never a duplicate (``uq_source_scope_root``), so an operator
    can safely re-run the one-off script."""
    first_id = seed_script.seed(
        root_type="page", root_id="1002", tags=["obi-mews-test"], label="first"
    )

    second_id = seed_script.seed(
        root_type="page",
        root_id="1002",
        tags=["obi-toast-test", "obi-mews-test"],
        label="second",
    )

    assert second_id == first_id  # same row updated, not a new one
    rows = _fetch_rows("page", "1002")
    assert len(rows) == 1  # no duplicate for the same root
    row = rows[0]
    assert row["id"] == first_id
    assert row["tags"] == ["obi-toast-test", "obi-mews-test"]
    assert row["label"] == "second"
    assert row["is_active"] is True


def test_tags_seed_script_deactivate_and_delete() -> None:
    """``--deactivate`` flips ``is_active`` only (tags/label untouched, row kept so the next sweep
    purges its coverage); ``--delete`` removes the row entirely. Exercised through ``main()`` so
    the real CLI paths are what is proven."""
    rc = seed_script.main(
        ["--root-type", "page", "--root-id", "1002", "--tags", "obi-toast-test", "--label", "Run"]
    )
    assert rc == 0

    rc = seed_script.main(["--root-type", "page", "--root-id", "1002", "--deactivate"])
    assert rc == 0

    rows = _fetch_rows("page", "1002")
    assert len(rows) == 1
    row = rows[0]
    assert row["is_active"] is False  # the one flipped field
    assert row["tags"] == ["obi-toast-test"]  # untouched by --deactivate
    assert row["label"] == "Run"  # untouched by --deactivate

    rc = seed_script.main(["--root-type", "page", "--root-id", "1002", "--delete"])
    assert rc == 0
    assert _fetch_rows("page", "1002") == []  # row gone entirely
