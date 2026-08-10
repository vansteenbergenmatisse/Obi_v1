"""End-to-end AnswerService integration (PLAN 4.2): real retrieval, real permission/source
scoping, real parent-context expansion, and a real query_trace UPDATE against the indexed fixture
corpus. Only the two LLM stages (rewrite, generation) are faked, so the suite stays network-free
and deterministic regardless of what is in the developer's `.env` — mirrors the same discipline
`test_retrieval_eval.py` applies to the reranker.
"""

from __future__ import annotations

import re

from sqlalchemy import text

from app.features.rag_agent import AnswerService, ChatMessage
from app.features.retrieval import HybridRetriever
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings
from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker

from .test_retrieval_eval import _build_policy, _index_corpus


class _EchoRewriter:
    """Deterministic stand-in: returns the last user turn verbatim (no LLM call)."""

    def rewrite(self, history):
        return history[-1].content


class _CitingGenerator:
    """Deterministic stand-in: cites every numbered marker present in the evidence block."""

    def generate(self, query: str, evidence_block: str) -> str:
        markers = sorted({int(m) for m in re.findall(r"\[(\d+)\]", evidence_block)})
        if not markers:
            return "No grounded evidence was provided."
        return " ".join(f"See source [{m}] for the answer to: {query}." for m in markers)


class _SilentGenerator:
    """Deterministic stand-in that cites nothing — exercises the no-grounded-claim refusal path."""

    def generate(self, query: str, evidence_block: str) -> str:
        return "This answer cites nothing."


def _build_retriever(
    gateway, settings: Settings, *, allowed_sources: tuple[str, ...] = ("confluence:default",)
) -> HybridRetriever:
    return HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        _build_policy(gateway),
        build_reranker(settings),
        allowed_sources=allowed_sources,
        trace_sessionmaker=get_sessionmaker(),
    )


def test_answer_service_grounds_a_cited_answer_end_to_end(gateway, settings: Settings) -> None:
    _index_corpus(gateway, settings)
    service = AnswerService(
        _build_retriever(gateway, settings),
        _EchoRewriter(),
        _CitingGenerator(),
        get_sessionmaker(),
        rewrite_enabled=True,
    )

    question = "How do I request access to core systems when I join?"
    answer = service.answer([ChatMessage(role="user", content=question)], scope="100")

    assert not answer.refused
    assert answer.citations
    assert answer.trace_id is not None
    for c in answer.citations:
        assert f"[{c.marker}]" in answer.text
        assert c.title

    with get_sessionmaker()() as s:
        row = s.execute(
            text("SELECT answer, rewritten_query, citations FROM query_trace WHERE id = :id"),
            {"id": int(answer.trace_id)},
        ).one()
    assert row.answer == answer.text
    assert row.rewritten_query == question
    assert row.citations["markers"]


def test_answer_service_refuses_when_source_scope_excludes_everything(
    gateway, settings: Settings
) -> None:
    _index_corpus(gateway, settings)
    service = AnswerService(
        _build_retriever(gateway, settings, allowed_sources=("confluence:nonexistent",)),
        _EchoRewriter(),
        _SilentGenerator(),
        get_sessionmaker(),
    )

    answer = service.answer(
        [ChatMessage(role="user", content="How do I request access to core systems?")], scope="100"
    )

    assert answer.refused
    assert answer.citations == []
    assert "no retrieved candidates" in (answer.refusal_reason or "")


def test_answer_service_refuses_when_generator_cites_nothing(gateway, settings: Settings) -> None:
    _index_corpus(gateway, settings)
    service = AnswerService(
        _build_retriever(gateway, settings), _EchoRewriter(), _SilentGenerator(), get_sessionmaker()
    )

    question = "How do I request access to core systems when I join?"
    answer = service.answer([ChatMessage(role="user", content=question)], scope="100")

    assert answer.refused
    assert answer.refusal_reason == "no claim in the generated answer survived citation enforcement"
    assert answer.trace_id is not None

    with get_sessionmaker()() as s:
        row = s.execute(
            text("SELECT answer FROM query_trace WHERE id = :id"), {"id": int(answer.trace_id)}
        ).one()
    assert row.answer != "This answer cites nothing."  # the raw ungrounded text is never persisted
