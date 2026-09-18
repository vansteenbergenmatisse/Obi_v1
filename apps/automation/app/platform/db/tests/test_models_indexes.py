"""Panel r2-indexes / substep 0.5.4: the two search indexes on `chunk` are exactly what the
design panel specifies — not just present, but built the way the plan demands.

`coverage-map.md` previously cited `test_gin_index_is_plan_usable_for_tags_overlap` for this
panel; that test proves the *planner* will use `ix_chunk_tags_gin` (the customer knowledge-scope
tags index from migration 0007) for a `tags && ...` query. It says nothing about
`ix_chunk_embedding_hnsw` or `ix_chunk_tsv_gin`, the two indexes this panel actually names. This
file closes that gap.

Queries the live catalogs (`pg_index`, `pg_class`, `pg_am`, `pg_opclass`) against a real, freshly
migrated local Postgres — never the Python model definition's text — so a green run proves the
migration actually created these indexes this way, not merely that `models.py` says so. Runs the
real Alembic chain against a dedicated, disposable database (mirroring
`test_migration_0007_knowledge_scope.py`'s pattern) so it never disturbs the shared local test
database other suites use.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from alembic import command
from app.platform.config import get_settings
from app.platform.db import engine as engine_mod
from app.platform.db.models import EMB_DIM

_AUTOMATION_ROOT = Path(__file__).resolve().parents[4]

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres, Alembic chain

_TABLE = "chunk"
_HNSW_INDEX = "ix_chunk_embedding_hnsw"
_GIN_INDEX = "ix_chunk_tsv_gin"

# The panel's own "Why halfvec" line: "pgvector caps a plain vector HNSW index at 2000 dims" — the
# same threshold `_embedding_hnsw_index()` branches on. Not a private import of that function's
# internal constant; this is the panel's stated number, used to derive which branch *should* be
# active for whatever EMBEDDING_DIM this process resolves to (see the module docstring note below
# on why that resolved value is not always 3072 here).
_HALFVEC_THRESHOLD_DIMS = 2000

# Catalog introspection, not model-text matching: joins pg_index -> pg_class -> pg_am for the
# access method, pg_opclass (via the index's indclass oidvector) for the operator class(es), and
# pg_get_expr() for the partial-index predicate and any indexed expression — exactly what a
# migrated database actually built, independent of what models.py claims it built.
_INDEX_SHAPE_SQL = """
SELECT
    am.amname AS method,
    pg_get_expr(ix.indexprs, ix.indrelid) AS expression,
    pg_get_expr(ix.indpred, ix.indrelid) AS predicate,
    (
        SELECT array_agg(opc.opcname ORDER BY ord)
        FROM unnest(ix.indclass) WITH ORDINALITY AS u(opcoid, ord)
        JOIN pg_opclass opc ON opc.oid = u.opcoid
    ) AS opclasses,
    ic.reloptions AS storage_options
FROM pg_index ix
JOIN pg_class ic ON ic.oid = ix.indexrelid
JOIN pg_class t ON t.oid = ix.indrelid
JOIN pg_am am ON am.oid = ic.relam
WHERE t.relname = :table_name AND ic.relname = :index_name
"""


def _ensure_database(admin_url: str, dbname: str) -> None:
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    finally:
        admin.dispose()


def _drop_database(admin_url: str, dbname: str) -> None:
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :n AND pid <> pg_backend_pid()"
                ),
                {"n": dbname},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
    finally:
        admin.dispose()


def _alembic_config() -> Config:
    cfg = Config(str(_AUTOMATION_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_AUTOMATION_ROOT / "alembic"))
    return cfg


@pytest.fixture
def indexed_engine() -> Iterator[Engine]:
    """A dedicated database, migrated to head, so index shape reflects the real migration chain."""
    base = make_url(get_settings().database_url)
    dbname = f"{base.database}_indexes_test"
    test_url_str = base.set(database=dbname).render_as_string(hide_password=False)
    admin_url = base.set(database="postgres").render_as_string(hide_password=False)

    _ensure_database(admin_url, dbname)

    prior_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url_str
    get_settings.cache_clear()

    eng = create_engine(test_url_str)
    try:
        command.upgrade(_alembic_config(), "head")
        yield eng
    finally:
        eng.dispose()
        if prior_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prior_database_url
        get_settings.cache_clear()
        engine_mod.get_engine.cache_clear()
        _drop_database(admin_url, dbname)


def _index_shape(engine: Engine, index_name: str) -> dict | None:
    with engine.connect() as conn:
        row = (
            conn.execute(text(_INDEX_SHAPE_SQL), {"table_name": _TABLE, "index_name": index_name})
            .mappings()
            .one_or_none()
        )
    return dict(row) if row is not None else None


def test_r2_indexes_hnsw_uses_hnsw_method_with_dimension_correct_opclass(
    indexed_engine: Engine,
) -> None:
    """panel r2-indexes · substep 0.5.4
    ix_chunk_embedding_hnsw is a genuine HNSW index (not a fallback btree/ivfflat). Above the
    panel's own 2000-dim threshold it is built over the `embedding::halfvec(EMB_DIM)` cast with
    the halfvec_cosine_ops operator class (the mechanism that lets a >2000-dim vector column get
    an HNSW index at all); at or below it, over the raw `embedding` column with vector_cosine_ops.

    This repo's root conftest.py pins EMBEDDING_DIM=256 for the whole suite (halfvec HNSW builds
    are ~30x slower at 3072 dims), so a stock `make test-db` run exercises the plain-vector branch
    here, not the halfvec branch the design panel's own example (3072 dims, production's real
    root .env value) describes. Confirmed by hand: running this file alone with
    `EMBEDDING_DIM=3072` explicitly exported (which pytest's `setdefault` cannot override) takes
    the halfvec branch and this assertion holds identically. Flagged as an open finding in the
    hand-back, not fixed here — this substep protects existing behavior, it does not change the
    suite's speed/dimension trade-off."""
    shape = _index_shape(indexed_engine, _HNSW_INDEX)

    assert shape is not None, f"{_HNSW_INDEX} does not exist on {_TABLE}"
    assert shape["method"] == "hnsw"
    if EMB_DIM > _HALFVEC_THRESHOLD_DIMS:
        assert shape["expression"] == f"(embedding)::halfvec({EMB_DIM})"
        assert shape["opclasses"] == ["halfvec_cosine_ops"]
    else:
        assert shape["expression"] is None
        assert shape["opclasses"] == ["vector_cosine_ops"]


def test_r2_indexes_hnsw_storage_params_are_m16_ef_construction_200(
    indexed_engine: Engine,
) -> None:
    """panel r2-indexes · substep 0.5.4
    The HNSW index's storage parameters are exactly m=16, ef_construction=200 — the values the
    design panel names, as actually recorded on the index relation, not merely in models.py."""
    shape = _index_shape(indexed_engine, _HNSW_INDEX)

    assert shape is not None, f"{_HNSW_INDEX} does not exist on {_TABLE}"
    assert set(shape["storage_options"] or []) == {"m=16", "ef_construction=200"}


def test_r2_indexes_hnsw_partial_predicate_is_active_kind_and_embedding_not_null(
    indexed_engine: Engine,
) -> None:
    """panel r2-indexes · substep 0.5.4
    The HNSW index's partial-index predicate is exactly `is_active AND kind = 1 AND embedding IS
    NOT NULL` — it only indexes active child chunks that actually have a vector."""
    shape = _index_shape(indexed_engine, _HNSW_INDEX)

    assert shape is not None, f"{_HNSW_INDEX} does not exist on {_TABLE}"
    assert shape["predicate"] == "(is_active AND (kind = 1) AND (embedding IS NOT NULL))"


def test_r2_indexes_gin_uses_gin_method_over_tsv_column(indexed_engine: Engine) -> None:
    """panel r2-indexes · substep 0.5.4
    ix_chunk_tsv_gin is a genuine GIN index directly over the `tsv` column (no expression, no
    other access method) — the keyword-search shortcut."""
    shape = _index_shape(indexed_engine, _GIN_INDEX)

    assert shape is not None, f"{_GIN_INDEX} does not exist on {_TABLE}"
    assert shape["method"] == "gin"
    assert shape["expression"] is None
    assert shape["opclasses"] == ["tsvector_ops"]


def test_r2_indexes_gin_partial_predicate_is_active_and_kind(indexed_engine: Engine) -> None:
    """panel r2-indexes · substep 0.5.4
    The GIN index's partial-index predicate is exactly `is_active AND kind = 1` — matching the
    design panel, distinct from (and narrower in shape than) the HNSW predicate above."""
    shape = _index_shape(indexed_engine, _GIN_INDEX)

    assert shape is not None, f"{_GIN_INDEX} does not exist on {_TABLE}"
    assert shape["predicate"] == "(is_active AND (kind = 1))"
