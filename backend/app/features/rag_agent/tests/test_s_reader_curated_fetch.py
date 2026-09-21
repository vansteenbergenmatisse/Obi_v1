"""panel s-reader · substep 0.5.3

``s-reader``'s "Who" line names three call sites that must run as the non-owner ``rag_reader``
role: HybridRetriever's search transaction, the parent-chunk fetch (both proven in
``app/features/retrieval/tests/test_s_reader_role_usage.py``), and this file's subject -- the
curated-answer fetch, ``AnswerService._fetch_curated_entries``.

``app/features/rag_agent/tests/`` has no ``conftest.py`` of its own (its sibling tests are
pure-fake unit tests with no database need), so this file wires its own module-local harness --
the same ``schema.schema`` primitives and connection pattern as
``app/features/confluence_sync/tests/conftest.py`` / ``app/features/retrieval/tests/
test_vector_data_nearest.py``, plus ``apply_reader_rls`` for the ``curated_knowledge_entry`` table
this feature reads.

``_fetch_curated_entries`` is invoked directly (not through the public ``answer()`` entry point):
it is the exact, whole call the panel's "curated fetch" line names, and reaching it through
``answer()`` would need a real rewriter/generator/retriever wired only to be skipped -- the
retriever and rewriter/generator collaborators are never touched by this call, so untyped
placeholders stand in for them (``cast``, not a behavioral fake): only the reader session matters
here.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from typing import cast

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.features.rag_agent.application import answer_service as answer_service_module
from app.features.rag_agent.application.answer_service import AnswerService
from app.features.rag_agent.infrastructure.llm_client import AnswerGenerator, QueryRewriter
from app.features.retrieval import HybridRetriever
from app.platform.config import get_settings
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
    duplicated here (module-local, not a shared conftest.py) because this directory has none --
    plus ``apply_reader_rls`` for ``curated_knowledge_entry``, the table this feature reads."""
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
        schema.apply_reader_rls(conn, role=_READER_ROLE)

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


def test_s_reader_answer_service_curated_fetch_runs_as_rag_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel s-reader · substep 0.5.3
    AnswerService's curated-answer fetch opens its reader_sessionmaker session as rag_reader,
    not the owner engine -- the third of the panel's three named call sites."""
    seen_users: list[str] = []
    real_fetch_curated_entries = answer_service_module.fetch_curated_entries

    def _spy_fetch_curated_entries(
        session: Session, allowed_scopes: Sequence[str], limit: int
    ) -> list:
        seen_users.append(session.execute(text("SELECT current_user")).scalar_one())
        return real_fetch_curated_entries(session, allowed_scopes, limit)

    monkeypatch.setattr(answer_service_module, "fetch_curated_entries", _spy_fetch_curated_entries)

    service = AnswerService(
        cast(HybridRetriever, object()),  # never called: only _fetch_curated_entries runs below
        cast(QueryRewriter, object()),
        cast(AnswerGenerator, object()),
        reader_sessionmaker=engine_mod.get_reader_sessionmaker(),
    )

    service._fetch_curated_entries(["obi-general-test"])  # the exact call the panel names

    assert seen_users == ["rag_reader"]
