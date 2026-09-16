"""PLAN 9.7 (ADR-0008 decision 7): real, wiring-level proof that `ambiguity.json`'s cases and a
genuinely out-of-corpus question each correctly fall back — one to a clarifying question, the
other to a refusal, neither to a fabricated answer — against the real indexed fixture corpus, plus
the new `fallback_rate`/`citation_grounding_rate` metrics computed over real `AnswerService`
outcomes rather than synthetic inputs. Only the LLM stages are faked (rewrite/generation/
classification), matching `test_answer_workflow.py`'s own discipline, so this suite stays
network-free and deterministic.
"""

from __future__ import annotations

import pytest

from app.features.evaluation import (
    citation_grounding_rate,
    datasets_dir,
    fallback_rate,
    load_dataset,
)
from app.features.rag_agent import AnswerService, AuthContext, ChatMessage, ClarificationReply
from app.platform.config import Settings
from app.platform.db.engine import get_sessionmaker

from .test_answer_workflow import _build_retriever, _CitingGenerator, _EchoRewriter
from .test_retrieval_eval import _index_corpus

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest


def _auth(principal: str | None = None) -> AuthContext:
    return AuthContext(
        None, None, None, ("obi-general-test",), ("confluence:default",), principal, None
    )


_DATASETS = datasets_dir()


class _AlwaysAmbiguousClassifier:
    """Fake: every query is judged too vague to search well. The classifier's real accuracy is
    covered by `test_clarification.py`/`test_llm_client.py` against fakes and the real
    Anthropic-backed collaborator (PLAN 9.2's own disclosed deviation) — this proves only that
    `AnswerService` correctly wires an `is_ambiguous=True` verdict into `needs_clarification`
    against a real, fully-indexed corpus, not that the real classifier judges these 3 questions
    ambiguous."""

    def classify(self, query: str) -> bool:
        return True


class _ClarifyingGenerator(_CitingGenerator):
    """Like `_CitingGenerator`, but answers `generate_clarification` instead of asserting it is
    never called — the tests here deliberately exercise that branch."""

    def generate_clarification(self, query: str) -> ClarificationReply:
        return ClarificationReply(
            question=f"Which do you mean: {query}", options=["Option A", "Option B"]
        )


def test_ambiguity_dataset_cases_trigger_clarification_end_to_end(
    gateway, settings: Settings
) -> None:
    """`ambiguity.json`'s cases previously only fed the pure retrieval-metrics harness (recall/mrr
    against `relevant_chunk_ids`) — nothing asserted the clarification behavior those cases exist
    to represent. This runs every case through the real `AnswerService`, against the real indexed
    fixture corpus, with the clarification branch enabled, and proves each one bypasses
    retrieval/generation entirely and returns `needs_clarification=True`."""
    _index_corpus(gateway, settings)
    dataset = load_dataset(_DATASETS / "ambiguity.json")
    assert dataset.cases  # guard against a silently-emptied fixture

    service = AnswerService(
        _build_retriever(gateway, settings),
        _EchoRewriter(),
        _ClarifyingGenerator(),
        get_sessionmaker(),
        clarification_classifier=_AlwaysAmbiguousClassifier(),
        enable_clarification_branch=True,
    )

    fell_back: list[bool] = []
    for case in dataset.cases:
        answer = service.answer(
            [ChatMessage(role="user", content=case.question)], _auth(principal=case.scope)
        )
        assert answer.needs_clarification is True, case.id
        assert answer.clarification_question
        assert answer.refused is False
        assert answer.citations == []
        assert answer.trace_id is None  # not a retrieval event, per ADR-0008 decision 1
        fell_back.append(answer.needs_clarification or answer.refused)

    assert fallback_rate(fell_back) == 1.0  # every ambiguity case is a fallback, by construction


def test_out_of_corpus_case_refuses_not_clarifies_or_hallucinates(
    gateway, settings: Settings
) -> None:
    """A genuinely out-of-corpus question (nothing in this corpus answers a trademark-registration
    question) must refuse, not clarify or fabricate an answer. CI runs against `FakeReranker`
    (`platform/clients/reranker_client.py`), which fabricates a score from candidate *rank*, not
    relevance (`float(n - i)`, always >= 1.0 for any non-empty result) — it can never produce a
    genuinely low score, so it cannot prove the *weak_score* refusal path on real content, the same
    limitation `test_rerank_lift_before_vs_after` already discloses for the same reason. What CI
    *can* prove deterministically, and what this asserts, is the *no_candidates* path once the
    corpus is confirmed to hold nothing indexed for this query's source scope — the same real
    mechanism a live reranker would fall through to at a genuinely low score.
    """
    _index_corpus(gateway, settings)
    dataset = load_dataset(_DATASETS / "out_of_corpus.json")
    case = dataset.cases[0]
    assert case.relevant_chunk_ids == []  # ADR-0008 decision 7: empty relevant set, not a new kind

    service = AnswerService(
        _build_retriever(gateway, settings, allowed_sources=("confluence:nonexistent",)),
        _EchoRewriter(),
        _ClarifyingGenerator(),
        get_sessionmaker(),
        # Clarification branch stays off, matching the production default: ADR-0008 decision 7 is
        # explicit that this case is "no clarification, no match anywhere" — it must resolve to a
        # refusal, not get relabelled as ambiguous just because the query happens to be short.
    )

    answer = service.answer(
        [ChatMessage(role="user", content=case.question)], _auth(principal=case.scope)
    )

    assert answer.refused is True
    assert answer.refusal_reason == "no_candidates"
    assert answer.needs_clarification is False
    assert answer.citations == []


def test_citation_grounding_rate_on_a_real_grounded_answer(gateway, settings: Settings) -> None:
    """The faithfulness/hallucination-rate proxy against a real, grounded `AnswerService` answer —
    proves the metric's wiring against real citation output, not synthetic ids."""
    _index_corpus(gateway, settings)
    dataset = load_dataset(_DATASETS / "retrieval_smoke.json")
    case = next(c for c in dataset.cases if c.id == "rs-01")

    service = AnswerService(
        _build_retriever(gateway, settings),
        _EchoRewriter(),
        _CitingGenerator(),
        get_sessionmaker(),
        retrieve_k=1,  # rs-01 has exactly one relevant page; keep evidence tight so the fake
        # generator's "cite every marker in the evidence block" behavior stays a fair proxy for a
        # real generator that only cites what it was actually given.
    )
    answer = service.answer(
        [ChatMessage(role="user", content=case.question)], _auth(principal=case.scope)
    )

    assert not answer.refused
    cited_ids = [c.page_id for c in answer.citations]
    assert citation_grounding_rate(cited_ids, case.relevant_chunk_ids) == 1.0
