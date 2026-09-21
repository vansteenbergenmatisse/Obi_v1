"""NEXT FIXES #1 (P0) / Phase 13.2: ``rag_reader`` must be able to resolve pgvector types.

On Supabase pgvector is installed into an ``extensions`` schema (not ``public``), and the reader
role is granted no ``USAGE`` there and has ``extensions`` off its ``search_path``. Every dense query
(``embedding::halfvec(dim)``) then fails as ``rag_reader`` with ``type "halfvec" does not exist`` /
``permission denied for schema extensions`` — so live semantic retrieval, which MUST run as
the non-owner reader (ADR-0004), is broken. ``schema.ensure_reader_role`` must therefore grant it
``USAGE`` on the ``extensions`` schema and add it to the role ``search_path`` whenever that schema
exists (a local/RDS install puts pgvector in ``public``, where the reader is already covered).

The live GRANT on Supabase's supabase-owned ``extensions`` schema is applied by the operator (the
owner role is permission-gated off it); these tests exercise the code path against a local install
where the owner can grant, and a rolled-back transaction keeps the shared session DB clean.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.platform.config import get_settings
from schema import engine as engine_mod
from schema import schema
from schema.enums import DocState, PageStatus
from schema.models import EMB_DIM, KIND_CHILD, Chunk, Document, DocumentVersion, PageSource

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_READER_ROLE = "rag_reader"


def test_reader_can_run_dense_halfvec_query() -> None:
    """Regression guard: the reader can resolve/cast ``halfvec`` (the production dense-query path).

    If the reader ever loses access to the schema holding pgvector's types, this fails the same way
    live retrieval does — ``type "halfvec" does not exist`` — instead of silently at query time.
    """
    reader = engine_mod.get_reader_sessionmaker()
    with reader() as s:
        casted = s.execute(text("SELECT CAST('[1,2,3]' AS halfvec(3))")).scalar_one()
    assert casted is not None


def test_ensure_reader_role_grants_extensions_usage_when_schema_exists() -> None:
    """When an ``extensions`` schema exists, the reader gets USAGE on it + it joins search_path."""
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS extensions"))
            schema.ensure_reader_role(conn, role=_READER_ROLE, password="rag_reader_test")

            usage = conn.execute(
                text("SELECT has_schema_privilege(:r, 'extensions', 'USAGE')"),
                {"r": _READER_ROLE},
            ).scalar_one()
            rolconfig = conn.execute(
                text("SELECT rolconfig FROM pg_roles WHERE rolname = :r"),
                {"r": _READER_ROLE},
            ).scalar_one()

            assert usage is True, "reader lacks USAGE on extensions -> dense query fails as reader"
            assert rolconfig is not None and any(
                c.startswith("search_path=") and "extensions" in c for c in rolconfig
            ), "extensions not on the reader role search_path -> halfvec unresolved as reader"
        finally:
            trans.rollback()


def test_ensure_reader_role_no_extensions_schema_is_a_noop_for_extensions() -> None:
    """A local/RDS install (pgvector in ``public``, no ``extensions`` schema) must not error.

    ensure_reader_role stays idempotent and grants no phantom ``extensions`` access. This also
    exercises the re-provision (role-already-exists) path, which on managed Postgres must be a bare
    password reset with no role-attribute clauses (NEXT FIXES #2).
    """
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("DROP SCHEMA IF EXISTS extensions CASCADE"))
            schema.ensure_reader_role(conn, role=_READER_ROLE, password="rag_reader_test")
            schema.ensure_reader_role(conn, role=_READER_ROLE, password="rag_reader_test")

            ext_exists = conn.execute(
                text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'extensions'")
            ).scalar()
            assert ext_exists is None, "test setup drop failed"
        finally:
            trans.rollback()


# --- panel vd-hnsw · substep p0-s0_5-reg-the-vector-database -----------------------------------
# The coverage map cites `test_reader_can_run_dense_halfvec_query` above for both vd-hnsw and
# vd-rls, but that test only proves the reader role can resolve the `halfvec` type — it asserts
# nothing about the index's own name, definition or build parameters (vd-hnsw), nor about row
# security actually hiding a forbidden row from a vector search (vd-rls). The tests below close
# that gap, one test per check bullet on each panel.


def _hnsw_indexdef() -> str:
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        return conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = 'chunk' "
                "AND indexname = 'ix_chunk_embedding_hnsw'"
            )
        ).scalar_one()


def test_vd_hnsw_name_is_ix_chunk_embedding_hnsw() -> None:
    """panel vd-hnsw · substep p0-s0_5-reg-the-vector-database
    Name: the index built over chunk.embedding is named ix_chunk_embedding_hnsw."""
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        exists = conn.execute(
            text(
                "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' "
                "AND tablename = 'chunk' AND indexname = 'ix_chunk_embedding_hnsw'"
            )
        ).scalar()
    assert exists == 1


# pgvector caps a plain `vector` HNSW index at 2000 dims (models.py::_HNSW_MAX_VECTOR_DIM); above
# it, the index casts to halfvec instead. This repo's root conftest.py pins EMBEDDING_DIM=256 for
# the whole DB-test suite (halfvec HNSW builds are far slower at the design's real 3072 dims — see
# the root .env), so a stock `make test-db` run exercises the plain-vector branch, not the halfvec
# branch the panel's own "3072" example describes — the identical, independently-disclosed finding
# in knowledge-base/schema/tests/test_models_indexes.py's test_r2_indexes_hnsw_uses_hnsw_method_..., which
# already pins this same index's shape for panel r2-indexes. Branching on EMB_DIM (rather than
# asserting the literal "halfvec(3072)") keeps this test honest under both configurations, per that
# same precedent.
_HALFVEC_THRESHOLD_DIMS = 2000


def test_vd_hnsw_over_embedding_halfvec_cosine() -> None:
    """panel vd-hnsw · substep p0-s0_5-reg-the-vector-database
    Over: embedding::halfvec(3072), cosine — above the 2000-dim cap on a plain vector HNSW index,
    the built index casts chunk.embedding to halfvec(EMB_DIM) and orders it with the halfvec
    cosine opclass; at or below it (this suite's own shrunk EMBEDDING_DIM), over the raw column
    with vector_cosine_ops instead. Either branch is genuinely cosine."""
    indexdef = _hnsw_indexdef()
    assert "USING hnsw" in indexdef
    if EMB_DIM > _HALFVEC_THRESHOLD_DIMS:
        assert f"halfvec({EMB_DIM})" in indexdef
        assert "halfvec_cosine_ops" in indexdef
    else:
        assert "halfvec" not in indexdef
        assert "vector_cosine_ops" in indexdef


def test_vd_hnsw_build_is_m16_ef_construction_200() -> None:
    """panel vd-hnsw · substep p0-s0_5-reg-the-vector-database
    Build: m=16, ef_construction=200 — the index's stored build-time HNSW options match exactly."""
    indexdef = _hnsw_indexdef()
    assert "m='16'" in indexdef
    assert "ef_construction='200'" in indexdef


# --- panel vd-rls · substep p0-s0_5-reg-the-vector-database ------------------------------------


def test_vd_rls_the_vector_sits_on_the_chunk_row() -> None:
    """panel vd-rls · substep p0-s0_5-reg-the-vector-database
    The vector sits on the chunk row: chunk.embedding is a column on chunk itself, not a
    separate table — so any row-security policy on chunk necessarily covers it too."""
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        udt = conn.execute(
            text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'chunk' "
                "AND column_name = 'embedding'"
            )
        ).scalar()
    assert udt == "vector"


def test_vd_rls_source_and_scope_policies_cover_every_select_on_chunk() -> None:
    """panel vd-rls · substep p0-s0_5-reg-the-vector-database
    The source and scope policies apply to every SELECT on chunk: row security is enabled on
    chunk, and both the permissive source policy and the restrictive knowledge-scope policy are
    registered FOR SELECT (not scoped to one query shape) — so no SELECT on chunk, including a
    nearest-neighbor vector search, can bypass either."""
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        rls_enabled = conn.execute(
            text(
                "SELECT relrowsecurity FROM pg_class "
                "WHERE relname = 'chunk' AND relnamespace = 'public'::regnamespace"
            )
        ).scalar_one()
        policies = conn.execute(
            text(
                "SELECT policyname, permissive, cmd FROM pg_policies "
                "WHERE schemaname = 'public' AND tablename = 'chunk'"
            )
        ).all()
    assert rls_enabled is True
    by_name = {row.policyname: row for row in policies}
    assert by_name["chunk_source_read"].cmd == "SELECT"
    assert by_name["chunk_source_read"].permissive == "PERMISSIVE"
    assert by_name["chunk_scope_read"].cmd == "SELECT"
    assert by_name["chunk_scope_read"].permissive == "RESTRICTIVE"


def _seed_chunk(
    session: Session,
    *,
    page_id: int,
    cos_sim: float,
    dim: int,
    source_id: str,
    source_type: str = "confluence",
) -> None:
    """One page_source + document + document_version chain, plus one active child chunk on it,
    embedded so its cosine distance to the all-ones query vector is controlled by ``cos_sim``
    (both are unit vectors, so cosine distance ``1 - cos_sim`` is exact). ``source_type``
    defaults to ``"confluence"`` (every pre-existing caller); pass a different connector label
    (e.g. ``"zendesk"``) to simulate a second, wholly different source system, not just a second
    Confluence namespace."""
    now = datetime.now(UTC)
    session.add(
        PageSource(
            page_id=page_id,
            space_id=page_id,
            source_type=source_type,
            source_id=source_id,
            current_cf_version=1,
            page_status=PageStatus.current,
            title=f"Page {page_id}",
            source_url=f"https://example.test/{page_id}",
            source_modified_at=now,
            content_hash=f"ch-{page_id}".encode(),
            structure_hash=f"sh-{page_id}".encode(),
            attachment_manifest_hash=b"none",
            access_scope_hash=b"none",
            labels_hash=b"none",
            parser_version=1,
            chunker_version=1,
            contextualization_version=1,
            embedding_model="fake",
            embedding_dim=dim,
            retrieval_schema_version=1,
        )
    )
    session.add(Document(id=page_id, page_id=page_id))
    session.add(
        DocumentVersion(
            id=page_id,
            document_id=page_id,
            page_id=page_id,
            cf_version=1,
            state=DocState.active,
            content_hash=f"ch-{page_id}".encode(),
            structure_hash=f"sh-{page_id}".encode(),
            parser_version=1,
            chunker_version=1,
            contextualization_version=1,
            embedding_model="fake",
            embedding_dim=dim,
            retrieval_schema_version=1,
        )
    )
    session.flush()

    other = math.sqrt(max(0.0, 1.0 - cos_sim * cos_sim))
    vec = [cos_sim, other] + [0.0] * (dim - 2)
    session.add(
        Chunk(
            doc_version_id=page_id,
            page_id=page_id,
            cf_version=1,
            kind=KIND_CHILD,
            stable_key=f"sk-{page_id}".encode(),
            positional_key=f"pk-{page_id}".encode(),
            content_key=f"ck-{page_id}".encode(),
            content_hash=f"ch-{page_id}".encode(),
            seq=0,
            heading_path=[],
            location={},
            display_content="x",
            retrieval_content="x",
            tokens=1,
            title=f"Page {page_id}",
            space_id=page_id,
            source_type=source_type,
            source_id=source_id,
            tags=[],
            source_url=f"https://example.test/{page_id}",
            is_active=True,
            page_status=PageStatus.current,
            retrieval_schema_version=1,
            embedding_model="fake",
            access_scope=b"",
            embedding=vec,
        )
    )


def test_vd_rls_forbidden_rows_nearest_neighbor_hit_is_never_returned(session: Session) -> None:
    """panel vd-rls · substep p0-s0_5-reg-the-vector-database
    So a nearest-neighbor hit from a forbidden row is never returned: a chunk on a source the
    caller is not scoped to is seeded strictly nearer to the query vector than a chunk on an
    allowed source. A raw nearest-neighbor SELECT run as the non-owner reader — not the app's own
    dense_search query, proving the protection is the table's row security and not one query's
    hand-written WHERE clause — returns the allowed row and never the nearer, forbidden one."""
    dim = get_settings().embedding_dim
    _seed_chunk(session, page_id=90001, cos_sim=0.5, dim=dim, source_id="confluence:default")
    _seed_chunk(session, page_id=90002, cos_sim=0.99, dim=dim, source_id="confluence:hidden")
    session.commit()

    query_vec = [1.0] + [0.0] * (dim - 1)
    reader = engine_mod.get_reader_sessionmaker()
    with reader() as reader_session:
        reader_session.execute(
            text("SELECT set_config('app.allowed_sources', :s, true)"),
            {"s": "confluence:default"},
        )
        reader_session.execute(
            text("SELECT set_config('app.allowed_knowledge_scopes', :s, true)"),
            {"s": "*"},
        )
        # `vector` (unlike `halfvec(N)`) casts without a dimension type modifier, so this stays
        # correct regardless of which HNSW branch is built (see _HALFVEC_THRESHOLD_DIMS above) —
        # this test only needs a real nearest-neighbor ORDER BY, not index usage.
        rows = reader_session.execute(
            text(
                "SELECT page_id FROM chunk WHERE is_active AND kind = 1 "
                "AND embedding IS NOT NULL "
                "ORDER BY embedding <=> CAST(:qvec AS vector) "
                "LIMIT 5"
            ),
            {"qvec": str(query_vec)},
        ).all()
        reader_session.rollback()

    returned_ids = {row.page_id for row in rows}
    assert returned_ids == {90001}
    assert 90002 not in returned_ids


def test_s_source_separates_whole_source_systems_by_source_id(session: Session) -> None:
    """panel s-source · substep p0-s0_5-reg-security
    ADR-0004 Lock 1: RLS separates whole source systems by ``source_id``, not just individual
    pages within one connector. Two *different* source systems (a Confluence page and a Zendesk
    page, distinct ``source_type``s and ``source_id``s) both carry a chunk that would match the
    same query — the Zendesk chunk is seeded strictly nearer to it than the Confluence one. A
    reader scoped only to the Confluence source (``app.allowed_sources = "confluence:default"``)
    reads back the Confluence row and zero rows from the Zendesk source, on both a plain
    unfiltered SELECT and a nearest-neighbor ORDER BY — the nearer, wrong-system row never
    surfaces just because it would otherwise rank first."""
    dim = get_settings().embedding_dim
    _seed_chunk(
        session,
        page_id=91001,
        cos_sim=0.5,
        dim=dim,
        source_id="confluence:default",
        source_type="confluence",
    )
    _seed_chunk(
        session,
        page_id=91002,
        cos_sim=0.99,
        dim=dim,
        source_id="zendesk:default",
        source_type="zendesk",
    )
    session.commit()

    query_vec = [1.0] + [0.0] * (dim - 1)
    reader = engine_mod.get_reader_sessionmaker()
    with reader() as reader_session:
        reader_session.execute(
            text("SELECT set_config('app.allowed_sources', :s, true)"),
            {"s": "confluence:default"},
        )
        reader_session.execute(
            text("SELECT set_config('app.allowed_knowledge_scopes', :s, true)"),
            {"s": "*"},
        )
        all_rows = reader_session.execute(
            text("SELECT page_id, source_id FROM chunk WHERE is_active AND kind = 1")
        ).all()
        nearest = reader_session.execute(
            text(
                "SELECT page_id FROM chunk WHERE is_active AND kind = 1 "
                "AND embedding IS NOT NULL "
                "ORDER BY embedding <=> CAST(:qvec AS vector) "
                "LIMIT 5"
            ),
            {"qvec": str(query_vec)},
        ).all()
        reader_session.rollback()

    seen_sources = {row.source_id for row in all_rows}
    assert seen_sources == {"confluence:default"}  # the whole Zendesk system is invisible
    nearest_ids = {row.page_id for row in nearest}
    assert nearest_ids == {91001}
    assert 91002 not in nearest_ids  # the nearer Zendesk chunk never surfaces


# --- panel s-reader · substep 0.5.3 ------------------------------------------------------------
# Checks 1 (HybridRetriever/curated/parent fetch bind rag_reader) live in
# app/features/retrieval/tests/test_s_reader_role_usage.py and
# app/features/rag_agent/tests/test_s_reader_curated_fetch.py (both cross-feature call sites, so
# they need their own feature's boundary-legal imports). The two checks below -- no-GUC fails
# closed, and the role cannot write or create -- need only this file's already-provisioned
# rag_reader + populated chunk table, so they are dedicated tests here instead, named for the
# panel per this codebase's own precedent (test_s_source_fails_closed_with_no_guc_set /
# test_r3_source_no_guc_returns_zero_rows already prove the identical no-GUC behavior under two
# other panels' names).


def test_s_reader_no_guc_set_returns_zero_rows(session: Session) -> None:
    """panel s-reader · substep 0.5.3
    Verify: scripts/setup_supabase.py verify-isolation's "reader no-GUC 0" check -- a fresh
    rag_reader session that never calls set_config sees the populated chunk table as empty
    (current_setting(...) is NULL, so the source-scope predicate is never true), not the whole
    corpus."""
    dim = get_settings().embedding_dim
    _seed_chunk(session, page_id=92001, cos_sim=0.5, dim=dim, source_id="confluence:default")
    session.commit()

    owner_total = int(session.execute(text("SELECT count(*) FROM chunk")).scalar_one())
    assert owner_total > 0  # the corpus is genuinely populated, so a leak would be visible

    with engine_mod.get_reader_sessionmaker()() as reader_session:
        no_guc = int(reader_session.execute(text("SELECT count(*) FROM chunk")).scalar_one())
    assert no_guc == 0


def test_s_reader_cannot_insert_update_delete_or_create_table() -> None:
    """panel s-reader · substep 0.5.3
    Cannot: write, create. rag_reader has SELECT (and default-SELECT-on-future-tables) only --
    ensure_reader_role grants nothing else -- so every write and every CREATE TABLE this role
    attempts fails with a permission error, never silently succeeding."""
    with engine_mod.get_reader_sessionmaker()() as reader_session:
        with pytest.raises(ProgrammingError, match="permission denied"):
            reader_session.execute(text("INSERT INTO page_source (page_id) VALUES (999999999)"))
        reader_session.rollback()

        with pytest.raises(ProgrammingError, match="permission denied"):
            reader_session.execute(
                text("UPDATE page_source SET title = 'x' WHERE page_id = 999999999")
            )
        reader_session.rollback()

        with pytest.raises(ProgrammingError, match="permission denied"):
            reader_session.execute(text("DELETE FROM page_source WHERE page_id = 999999999"))
        reader_session.rollback()

        with pytest.raises(ProgrammingError, match="permission denied"):
            reader_session.execute(text("CREATE TABLE reader_write_probe (id integer)"))
        reader_session.rollback()
