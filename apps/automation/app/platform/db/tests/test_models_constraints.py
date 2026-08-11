"""PLAN 4.6.8: explicit CHECK-constraint names must survive the naming convention unchanged.

`Base.metadata`'s naming convention interpolates ``%(constraint_name)s`` from whatever name a
constraint is given — an unwrapped explicit name (e.g. ``"ck_chunk_source_type"``) gets
re-prefixed into ``"ck_chunk_ck_chunk_source_type"`` on a fresh ``create_all()`` run, silently
diverging from the hand-written migration DDL that names the same constraint
``ck_chunk_source_type`` directly. `sqlalchemy.schema.conv(...)` marks a name as already-resolved
so the convention leaves it alone — these tests are pure metadata inspection (no DB needed) that
would have caught the divergence before it ever reached a live database.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint

# import models for side effect: register tables on Base.metadata
from app.platform.db import models  # noqa: F401
from app.platform.db.base import Base


def _check_constraint_names(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {str(c.name) for c in table.constraints if isinstance(c, CheckConstraint)}


def test_chunk_has_exactly_one_canonically_named_source_type_check() -> None:
    assert _check_constraint_names("chunk") == {"ck_chunk_source_type"}


def test_page_source_has_exactly_one_canonically_named_source_type_check() -> None:
    assert _check_constraint_names("page_source") == {"ck_page_source_source_type"}


def test_source_scope_has_canonically_named_checks() -> None:
    assert _check_constraint_names("source_scope") == {
        "ck_source_scope_root_type",
        "ck_source_scope_source_type",
    }
