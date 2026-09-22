"""Row-security-before-limit and tie-break ordering on the dense (pgvector) nearest-75 query
(design panel ``vd-nearest``).

``dense_search``'s SQL is already ``... ORDER BY dist ASC, page_id ASC LIMIT :limit``, with the
row-security policy and the app-layer source/knowledge-scope predicates in the same ``WHERE``
clause that precedes ``ORDER BY``/``LIMIT`` in one SQL statement. That shape structurally guarantees
row security is applied *before* the limit truncates, and that ties break on ascending ``page_id`` —
but no existing test proves either behaviorally against a real Postgres connection
(``test_search_repo_knowledge_scope.py`` and ``test_search_repo_gucs.py`` only assert the emitted
SQL text/params against a spy session, and neither seeds more than a handful of rows, so nothing
proves the ``LIMIT 75`` actually truncates a result set behaviorally). These tests seed real chunk
rows and real RLS state to prove it.

The session-scoped engine bootstrap (guard, ``*_test`` database, ``create_all``,
``ensure_reader_role``, ``apply_chunk_rls``, ``apply_chunk_scope_rls``) is the shared
``app.tests.db_harness``, run once per session via the root conftest's ``_shared_db_schema``
fixture; the owner ``session`` fixture comes from the root conftest and per-test truncation from
this directory's ``conftest.py``.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.features.retrieval.infrastructure.search_repo import (
    apply_knowledge_scope,
    apply_source_scope,
    dense_search,
)
from app.platform.config import get_settings
from schema import engine as engine_mod
from schema.enums import DocState, PageStatus
from schema.models import KIND_CHILD, Chunk, Document, DocumentVersion, PageSource

pytestmark = pytest.mark.db  # panel vd-nearest · substep 0.5.3: real local Postgres


def _query_vector(dim: int) -> list[float]:
    return [1.0] + [0.0] * (dim - 1)


def _unit_vector(dim: int, cos_sim: float) -> list[float]:
    """A unit vector whose cosine similarity to ``_query_vector`` is exactly ``cos_sim`` (both
    unit vectors, so cosine distance ``1 - cos_sim`` is exact and reproducible)."""
    other = math.sqrt(max(0.0, 1.0 - cos_sim * cos_sim))
    return [cos_sim, other] + [0.0] * (dim - 2)


def _add_page_chain(session: Session, *, page_id: int, dim: int, source_id: str) -> None:
    """One page_source + document + document_version chain for ``page_id``.

    ``page_source ⇄ document ⇄ document_version`` form a deferred-FK insert-order cycle
    (see the ``Document.page_id`` docstring reference in ``knowledge-base/schema/models.py``): the ORM's
    automatic dependency sort does not carry a strict ordering guarantee across that cycle *and*
    ``chunk`` within a single flush, so callers must ``session.flush()`` this chain before adding
    any ``Chunk`` row that references it (``_add_chunk`` below).
    """
    now = datetime.now(UTC)
    session.add(
        PageSource(
            page_id=page_id,
            space_id=page_id,
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


def _add_chunk(session: Session, *, page_id: int, cos_sim: float, dim: int, source_id: str) -> None:
    """One active child chunk on ``page_id``'s (already-flushed) document_version, embedded so its
    cosine distance to ``_query_vector`` is controlled exactly by ``cos_sim``."""
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
            source_id=source_id,
            tags=[],
            source_url=f"https://example.test/{page_id}",
            is_active=True,
            page_status=PageStatus.current,
            retrieval_schema_version=1,
            embedding_model="fake",
            access_scope=b"",
            embedding=_unit_vector(dim, cos_sim),
        )
    )


def _seed_chunk(
    session: Session,
    *,
    page_id: int,
    cos_sim: float,
    dim: int,
    source_id: str = "confluence:default",
) -> None:
    """One page's full chain plus its chunk, flushed in the two phases ``_add_page_chain`` and
    ``_add_chunk`` require. Convenience for tests that seed one page at a time."""
    _add_page_chain(session, page_id=page_id, dim=dim, source_id=source_id)
    session.flush()
    _add_chunk(session, page_id=page_id, cos_sim=cos_sim, dim=dim, source_id=source_id)


def test_vd_nearest_orders_by_distance_then_page_id_on_ties(session: Session) -> None:
    """panel vd-nearest · substep 0.5.3
    Ties are broken by page_id: two chunks at the identical distance from the query vector come
    back with the lower page_id first, and a strictly nearer chunk still ranks ahead of both."""
    dim = get_settings().embedding_dim
    _seed_chunk(session, page_id=500, cos_sim=0.4, dim=dim)
    _seed_chunk(session, page_id=100, cos_sim=0.4, dim=dim)  # identical distance, lower page_id
    _seed_chunk(session, page_id=300, cos_sim=0.9, dim=dim)  # strictly nearer: ranks first
    session.commit()

    rows = dense_search(session, _query_vector(dim), None, 10, dim)
    ordered_page_ids = [pid for pid, _ in rows]

    assert ordered_page_ids[0] == 300
    assert ordered_page_ids[1:3] == [100, 500]


def test_vd_nearest_limit_caps_the_result_at_75_nearest(session: Session) -> None:
    """panel vd-nearest · substep p0-s0_5-reg-the-vector-database
    ``LIMIT 75`` behaviorally caps the returned rows at 75 and keeps only the 75 nearest: 80
    chunks are seeded at 80 distinct cosine distances (a plain ``LIMIT`` with no ``ORDER BY``
    could just as easily keep the 5 farthest), so getting back exactly the 75 closest — with the
    single nearest chunk first — proves the query orders by distance ASC before truncating at 75,
    not the other way round."""
    dim = get_settings().embedding_dim
    base_page_id = 40000
    n = 80
    for i in range(n):
        # cos_sim strictly increasing with i -> distance (1 - cos_sim) strictly decreasing with i,
        # so higher page_id == nearer chunk. Page ids 40005..40079 (75 of them) are the 75 nearest;
        # 40000..40004 (the 5 farthest) must be excluded by the LIMIT.
        cos_sim = 0.10 + i * 0.01
        _seed_chunk(session, page_id=base_page_id + i, cos_sim=cos_sim, dim=dim)
    session.commit()

    rows = dense_search(session, _query_vector(dim), None, 75, dim)
    ordered_page_ids = [pid for pid, _ in rows]

    assert len(rows) == 75
    assert set(ordered_page_ids) == {base_page_id + i for i in range(5, n)}
    assert ordered_page_ids[0] == base_page_id + (n - 1)  # highest cos_sim == nearest, ranks first


def test_vd_nearest_row_security_filters_before_the_limit_not_after(session: Session) -> None:
    """panel vd-nearest · substep 0.5.3
    Row security filters before LIMIT, not after: 60 chunks visible under the caller's source
    context and 140 more chunks under a different source — every one of them strictly nearer to
    the query vector than any visible chunk — are seeded. Naively taking the nearest 75 across all
    200 first and then filtering by row security would return zero visible rows (the 140 hidden
    chunks fill every slot). Returning all 60 visible rows instead proves row security is applied
    ahead of the LIMIT, inside the same query."""
    dim = get_settings().embedding_dim
    visible_ids = list(range(20000, 20060))  # 60 pages, visible source
    hidden_ids = list(range(30000, 30140))  # 140 pages, hidden source, all strictly nearer

    for i, pid in enumerate(visible_ids):
        cos_sim = 0.5 - i * 0.005  # spread of distances, all far weaker than the hidden cluster
        _seed_chunk(session, page_id=pid, cos_sim=cos_sim, dim=dim, source_id="confluence:default")
    for pid in hidden_ids:
        _seed_chunk(session, page_id=pid, cos_sim=0.99, dim=dim, source_id="confluence:hidden")
    session.commit()

    reader = engine_mod.get_reader_sessionmaker()
    with reader() as reader_session:
        apply_source_scope(reader_session, ["confluence:default"])
        apply_knowledge_scope(reader_session, None)
        rows = dense_search(reader_session, _query_vector(dim), None, 75, dim)
        reader_session.rollback()

    returned_ids = {pid for pid, _ in rows}
    assert len(rows) == 60
    assert returned_ids == set(visible_ids)
    assert returned_ids.isdisjoint(hidden_ids)
