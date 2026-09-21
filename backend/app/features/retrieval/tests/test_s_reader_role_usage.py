"""panel s-reader · substep 0.5.3

``s-reader``'s "Who" line names three call sites that must run as the non-owner ``rag_reader``
role, never the owner: HybridRetriever's search transaction, the curated-answer fetch, and the
parent-chunk fetch. The curated fetch is proven in
``app/features/rag_agent/tests/test_s_reader_curated_fetch.py``; this file proves the other two,
which live in ``application/retriever.py``.

Both tests spy on a search-repo function that already runs inside the transaction under test --
capturing ``SELECT current_user`` from the *real* session the retriever opened -- then delegate to
the real implementation, so the retriever's actual production code path (not a stand-in) is what
executes. Neither test needs seeded rows: an empty result set still means the query ran, under
whichever role opened the connection.

``app/features/retrieval/tests/`` has no ``conftest.py`` of its own (its sibling tests are pure-fake
unit tests with no database need), so this file wires its own module-local harness -- the same
``schema.schema`` primitives and connection pattern as
``app/features/confluence_sync/tests/conftest.py`` / ``test_vector_data_nearest.py``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.features.retrieval.application import retriever as retriever_module
from app.features.retrieval.application.retriever import HybridRetriever
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings, get_settings
from schema import engine as engine_mod
from schema import schema

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres

_READER_ROLE = "rag_reader"
_READER_PASSWORD = "rag_reader_test"


def _ensure_database(url: str) -> None:
    u = make_url(url)
    admin_url = u.set(database="postgres")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": u.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{u.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _configure_test_engine() -> Iterator[None]:
    """Same bootstrap steps as confluence_sync/tests/conftest.py's ``_configure_test_engine``,
    duplicated here (module-local, not a shared conftest.py) because this directory has none."""
    base = make_url(get_settings().database_url)
    test_url = base.set(database=f"{base.database}_test").render_as_string(hide_password=False)
    _ensure_database(test_url)

    os.environ["DATABASE_URL"] = test_url
    get_settings.cache_clear()
    engine_mod.get_engine.cache_clear()
    engine_mod.get_sessionmaker.cache_clear()

    eng = engine_mod.get_engine()
    with eng.begin() as conn:
        schema.drop_all(conn)
        schema.create_all(conn)
        schema.ensure_reader_role(conn, role=_READER_ROLE, password=_READER_PASSWORD)
        schema.apply_chunk_rls(conn)
        schema.apply_chunk_scope_rls(conn)

    reader_url = (
        make_url(test_url)
        .set(username=_READER_ROLE, password=_READER_PASSWORD)
        .render_as_string(hide_password=False)
    )
    os.environ["DATABASE_READER_URL"] = reader_url
    get_settings.cache_clear()
    engine_mod.get_reader_engine.cache_clear()
    engine_mod.get_reader_sessionmaker.cache_clear()

    yield
    with eng.begin() as conn:
        schema.drop_all(conn)
    engine_mod.get_reader_engine().dispose()
    eng.dispose()


def _retriever(settings: Settings) -> HybridRetriever:
    """Wired exactly like `main.py::build_answer_service` wires reads: the reader sessionmaker."""
    return HybridRetriever(
        engine_mod.get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
    )


def test_s_reader_hybrid_retriever_search_transaction_runs_as_rag_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel s-reader · substep 0.5.3
    HybridRetriever's search transaction -- the one apply_source_scope/apply_knowledge_scope set
    the RLS GUCs on -- opens its session as rag_reader, not the owner role, matching the identity
    scripts/setup_supabase.py verify-isolation assumes for every read it checks."""
    seen_users: list[str] = []
    real_keyword_search = retriever_module.keyword_search

    def _spy_keyword_search(
        session: Session, *args: object, **kwargs: object
    ) -> list[tuple[int, float]]:
        seen_users.append(session.execute(text("SELECT current_user")).scalar_one())
        return real_keyword_search(session, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(retriever_module, "keyword_search", _spy_keyword_search)

    retr = _retriever(get_settings())
    retr.retrieve_with_context("does the exact wording even matter here", scope=None, k=5)

    assert seen_users == ["rag_reader"]


def test_s_reader_hybrid_retriever_parent_fetch_runs_as_rag_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel s-reader · substep 0.5.3
    fetch_parent_texts -- the panel's "parent fetch" -- opens its own, separate session as
    rag_reader too, not just the search transaction above."""
    seen_users: list[str] = []
    real_fetch_parent_context = retriever_module.fetch_parent_context

    def _spy_fetch_parent_context(session: Session, chunk_ids: Sequence[int]) -> dict[int, str]:
        seen_users.append(session.execute(text("SELECT current_user")).scalar_one())
        return real_fetch_parent_context(session, chunk_ids)

    monkeypatch.setattr(retriever_module, "fetch_parent_context", _spy_fetch_parent_context)

    retr = _retriever(get_settings())
    retr.fetch_parent_texts([999_999])  # no such chunk: proves the role, not the join

    assert seen_users == ["rag_reader"]
