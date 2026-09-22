"""The keyword side's query behavior (design panel ``vd-keyword``): the OR-joined tsquery match
and the ts_rank ordering, proven behaviorally against a real Postgres connection running the real
``keyword_search`` function -- not just its emitted SQL text (that's already pinned, independently,
by ``test_search_repo_keyword.py``'s spy-session tests for the retrieval-stage-2 panel
``r2-keyword``; this file's job is the vector-database panel's own dedicated proof).

The session-scoped engine bootstrap is the shared ``app.tests.db_harness`` (run once per session
via the root conftest's ``_shared_db_schema`` fixture); the owner ``session`` fixture comes from the
root conftest and per-test truncation from this directory's ``conftest.py``. This file proves the
keyword query's own OR-join/ts_rank shape as the table owner (RLS-exempt, ADR-0013 NO FORCE), so the
shared harness's RLS policies do not affect it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.retrieval.infrastructure.search_repo import keyword_search
from app.platform.config import get_settings
from schema.enums import DocState, PageStatus
from schema.models import KIND_CHILD, Chunk, Document, DocumentVersion, PageSource

pytestmark = pytest.mark.db  # panel vd-keyword · substep 0.5.3: real local Postgres


def _seed_keyword_chunk(session: Session, *, page_id: int, tsv_text: str) -> None:
    """One page_source + document + document_version chain plus one active child chunk, with
    `tsv` set directly from `tsv_text` via a real `to_tsvector('english', ...)` call. The
    construction formula itself (title || heading path || text) is pinned separately by
    `test_vd_keyword_column_built_from_title_heading_path_and_text_english`; this helper only
    needs *some* real tsvector to drive the query-shape checks below, so it writes `tsv` straight
    from a caller-chosen body rather than replaying the whole ingestion pipeline for three words."""
    now = datetime.now(UTC)
    dim = get_settings().embedding_dim
    session.add(
        PageSource(
            page_id=page_id,
            space_id=page_id,
            source_id="confluence:default",
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
            display_content=tsv_text,
            retrieval_content=tsv_text,
            tokens=1,
            title=f"Page {page_id}",
            space_id=page_id,
            source_id="confluence:default",
            tags=[],
            source_url=f"https://example.test/{page_id}",
            is_active=True,
            page_status=PageStatus.current,
            retrieval_schema_version=1,
            embedding_model="fake",
            access_scope=b"",
            embedding=None,
        )
    )
    session.flush()
    session.execute(
        text("UPDATE chunk SET tsv = to_tsvector('english', :body) WHERE page_id = :pid"),
        {"body": tsv_text, "pid": page_id},
    )


def test_vd_keyword_query_or_joins_words_and_ranks_by_ts_rank(session: Session) -> None:
    """panel vd-keyword · substep 0.5.3
    Query: OR-joined words, ranked by ts_rank -- a two-word question ("alpha beta") matches a
    chunk containing only "alpha" and a chunk containing only "beta" (an AND-joined query would
    match neither of those on its own), proving the words are OR-joined, not AND-joined; and a
    third chunk that repeats both words outranks both single-word chunks, proving the results
    come back ordered by ts_rank score, not insertion order."""
    only_alpha, only_beta, both_repeated = 90001, 90002, 90003
    _seed_keyword_chunk(session, page_id=only_alpha, tsv_text="alpha")
    _seed_keyword_chunk(session, page_id=only_beta, tsv_text="beta")
    _seed_keyword_chunk(session, page_id=both_repeated, tsv_text="alpha beta alpha beta alpha beta")
    session.commit()

    rows = keyword_search(session, "alpha beta", None, 10)
    ids = [pid for pid, _ in rows]

    # OR, not AND: each single-word chunk still matches a two-word question.
    assert set(ids) == {only_alpha, only_beta, both_repeated}
    # ranked by ts_rank score: the chunk matching both words repeatedly ranks first.
    assert ids[0] == both_repeated
