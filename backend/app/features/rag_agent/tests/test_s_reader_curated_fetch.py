"""panel s-reader · substep 0.5.3

``s-reader``'s "Who" line names three call sites that must run as the non-owner ``rag_reader``
role: HybridRetriever's search transaction, the parent-chunk fetch (both proven in
``app/features/retrieval/tests/test_s_reader_role_usage.py``), and this file's subject -- the
curated-answer fetch, ``AnswerService._fetch_curated_entries``.

The session-scoped engine bootstrap is the shared ``app.tests.db_harness`` (run once per session via
the root conftest's ``_shared_db_schema`` fixture; per-test truncation from this directory's
``conftest.py``). The shared harness grants the reader ``SELECT`` on every table via
``ensure_reader_role``, so the curated read below runs as ``rag_reader`` without needing
``apply_reader_rls`` — this test seeds no rows and only asserts the connection's ``current_user``.

``_fetch_curated_entries`` is invoked directly (not through the public ``answer()`` entry point):
it is the exact, whole call the panel's "curated fetch" line names, and reaching it through
``answer()`` would need a real rewriter/generator/retriever wired only to be skipped -- the
retriever and rewriter/generator collaborators are never touched by this call, so untyped
placeholders stand in for them (``cast``, not a behavioral fake): only the reader session matters
here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.rag_agent.application import answer_service as answer_service_module
from app.features.rag_agent.application.answer_service import AnswerService
from app.features.rag_agent.infrastructure.llm_client import AnswerGenerator, QueryRewriter
from app.features.retrieval import HybridRetriever
from schema import engine as engine_mod

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres


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
