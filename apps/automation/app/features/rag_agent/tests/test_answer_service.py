"""AnswerService orchestration, unit-tested with fake collaborators — no network, no DB.

Each stage of the fixed workflow (rewrite -> retrieve/rerank -> CRAG retry -> refusal ->
parent expansion -> generation -> citation enforcement) is exercised through the same public
`answer()` entry point, asserting on the resulting `Answer` DTO and on which collaborators were
actually called (e.g. the generator must never be called once refusal is decided).
"""

from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from app.features.rag_agent.application.answer_service import (
    _NO_GROUNDED_CLAIM_REASON,
    _REFUSAL_TEXT,
    AnswerService,
)
from app.features.rag_agent.schemas import ChatMessage
from app.features.retrieval import RetrievalResult, RetrievedHit

_HIT_A = RetrievedHit(page_id="101", chunk_id=501, score=0.9, title="Onboarding Guide", url="u/101")
_HIT_B = RetrievedHit(page_id="102", chunk_id=502, score=0.5, title="Access Policy", url="u/102")


class _FakeRetriever:
    def __init__(self, results_by_query: dict[str, RetrievalResult], parent_texts: dict[int, str]):
        self._results = results_by_query
        self._parents = parent_texts
        self.retrieve_calls: list[tuple[str, str | None, int]] = []

    def retrieve_with_context(self, query: str, scope: str | None, k: int = 5) -> RetrievalResult:
        self.retrieve_calls.append((query, scope, k))
        return self._results[query]

    def fetch_parent_texts(self, chunk_ids):
        return {cid: self._parents[cid] for cid in chunk_ids if cid in self._parents}


class _FakeRewriter:
    def __init__(self, rewritten: str) -> None:
        self._rewritten = rewritten
        self.called = False

    def rewrite(self, history) -> str:
        self.called = True
        return self._rewritten


class _RaisingRewriter:
    def rewrite(self, history) -> str:
        raise AssertionError("rewriter must not be called when rewrite_enabled=False")


class _FakeGenerator:
    def __init__(self, text: str) -> None:
        self._text = text
        self.called_with: list[tuple[str, str]] = []

    def generate(self, query: str, evidence_block: str) -> str:
        self.called_with.append((query, evidence_block))
        return self._text


class _RaisingGenerator:
    def generate(self, query: str, evidence_block: str) -> str:
        raise AssertionError("generator must not be called once refusal is decided")


class _FakeTraceRow:
    def __init__(self) -> None:
        self.rewritten_query: str | None = None
        self.answer: str | None = None
        self.citations: object | None = None


class _FakeSession:
    def __init__(self, row: _FakeTraceRow) -> None:
        self._row = row
        self.committed = False
        self.got_pk: int | None = None

    def get(self, _model, pk):
        self.got_pk = pk
        return self._row

    def commit(self) -> None:
        self.committed = True

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *exc) -> None:
        return None


def _service(
    retriever, rewriter, generator, row=None, **kwargs
) -> tuple[AnswerService, _FakeSession | None]:
    session = _FakeSession(row) if row is not None else None
    # cast: _FakeSession is a test double, not a real Session — structurally it only needs to
    # support what update_query_trace_answer actually calls (get/commit/context-manager).
    writer_sessionmaker = (lambda: cast(Session, session)) if session is not None else None
    service = AnswerService(retriever, rewriter, generator, writer_sessionmaker, **kwargs)
    return service, session


def test_grounded_answer_with_rewrite_and_persisted_trace() -> None:
    retriever = _FakeRetriever(
        {"rewritten q": RetrievalResult(hits=[_HIT_A, _HIT_B], trace_id=7)},
        parent_texts={
            501: "Request access via the onboarding portal.",
            502: "Access is role-based.",
        },
    )
    rewriter = _FakeRewriter("rewritten q")
    generator = _FakeGenerator("You request access via the portal [1]. Access is role-based [2].")
    row = _FakeTraceRow()
    service, session = _service(retriever, rewriter, generator, row=row)

    history = [ChatMessage(role="user", content="how do I get access?")]
    result = service.answer(history, scope="100")

    assert rewriter.called
    assert retriever.retrieve_calls == [("rewritten q", "100", 5)]
    assert generator.called_with == [
        (
            "rewritten q",
            "[1] Onboarding Guide\nRequest access via the onboarding portal.\n\n"
            "[2] Access Policy\nAccess is role-based.",
        )
    ]
    assert not result.refused
    assert result.trace_id == "7"
    assert [c.marker for c in result.citations] == [1, 2]
    assert result.citations[0].page_id == "101"
    assert session is not None and session.committed
    assert row.answer == result.text
    assert row.rewritten_query == "rewritten q"


def test_rewrite_disabled_skips_rewriter_and_uses_verbatim_query() -> None:
    retriever = _FakeRetriever(
        {"verbatim q": RetrievalResult(hits=[_HIT_A], trace_id=None)},
        parent_texts={501: "Some grounding text."},
    )
    generator = _FakeGenerator("Answer with a citation [1].")
    service, _ = _service(retriever, _RaisingRewriter(), generator, rewrite_enabled=False)

    result = service.answer([ChatMessage(role="user", content="verbatim q")], scope=None)

    assert retriever.retrieve_calls == [("verbatim q", None, 5)]
    assert not result.refused
    assert result.trace_id is None  # no trace row -> nothing to persist, no crash


def test_no_candidates_refuses_without_calling_generator() -> None:
    retriever = _FakeRetriever({"q": RetrievalResult(hits=[], trace_id=3)}, parent_texts={})
    row = _FakeTraceRow()
    service, session = _service(retriever, _FakeRewriter("q"), _RaisingGenerator(), row=row)

    result = service.answer([ChatMessage(role="user", content="q")], scope=None)

    assert result.refused
    assert "no retrieved candidates" in (result.refusal_reason or "")
    assert result.citations == []
    assert session is not None and session.committed
    assert row.answer == _REFUSAL_TEXT


def test_weak_result_retries_once_and_succeeds_on_original_query() -> None:
    weak = RetrievalResult(hits=[RetrievedHit("101", 501, 0.05, "Weak", "u")], trace_id=1)
    strong = RetrievalResult(hits=[_HIT_A], trace_id=1)
    retriever = _FakeRetriever(
        {"rewritten q": weak, "original q": strong}, parent_texts={501: "text"}
    )
    generator = _FakeGenerator("Grounded [1].")
    service, _ = _service(
        retriever, _FakeRewriter("rewritten q"), generator, refusal_min_rerank_score=0.10
    )

    result = service.answer([ChatMessage(role="user", content="original q")], scope=None)

    assert retriever.retrieve_calls == [("rewritten q", None, 5), ("original q", None, 5)]
    assert not result.refused  # the retry's stronger score (0.9) cleared the threshold


def test_weak_result_still_weak_after_retry_refuses() -> None:
    weak1 = RetrievalResult(hits=[RetrievedHit("101", 501, 0.02, "Weak", "u")], trace_id=1)
    weak2 = RetrievalResult(hits=[RetrievedHit("101", 501, 0.05, "Weak", "u")], trace_id=1)
    retriever = _FakeRetriever({"rewritten q": weak1, "original q": weak2}, parent_texts={})
    service, _ = _service(
        retriever, _FakeRewriter("rewritten q"), _RaisingGenerator(), refusal_min_rerank_score=0.10
    )

    result = service.answer([ChatMessage(role="user", content="original q")], scope=None)

    assert retriever.retrieve_calls == [("rewritten q", None, 5), ("original q", None, 5)]
    assert result.refused
    assert "below refusal threshold" in (result.refusal_reason or "")


def test_crag_max_retries_zero_never_retries() -> None:
    weak = RetrievalResult(hits=[RetrievedHit("101", 501, 0.02, "Weak", "u")], trace_id=1)
    retriever = _FakeRetriever({"rewritten q": weak}, parent_texts={})
    service, _ = _service(
        retriever, _FakeRewriter("rewritten q"), _RaisingGenerator(), crag_max_retries=0
    )

    result = service.answer([ChatMessage(role="user", content="original q")], scope=None)

    assert retriever.retrieve_calls == [("rewritten q", None, 5)]  # no retry attempted
    assert result.refused


def test_no_surviving_citation_degrades_to_refusal() -> None:
    retriever = _FakeRetriever(
        {"q": RetrievalResult(hits=[_HIT_A], trace_id=9)}, parent_texts={501: "text"}
    )
    generator = _FakeGenerator("This sentence cites nothing at all.")
    row = _FakeTraceRow()
    service, session = _service(retriever, _FakeRewriter("q"), generator, row=row)

    result = service.answer([ChatMessage(role="user", content="q")], scope=None)

    assert result.refused
    assert result.refusal_reason == _NO_GROUNDED_CLAIM_REASON
    assert session is not None and row.answer == _REFUSAL_TEXT


def test_rejects_history_not_ending_in_user_turn() -> None:
    retriever = _FakeRetriever({}, {})
    service, _ = _service(retriever, _FakeRewriter("x"), _RaisingGenerator())
    try:
        service.answer([ChatMessage(role="assistant", content="hi")], scope=None)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for history not ending in a user turn")


def test_rejects_empty_history() -> None:
    retriever = _FakeRetriever({}, {})
    service, _ = _service(retriever, _FakeRewriter("x"), _RaisingGenerator())
    try:
        service.answer([], scope=None)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty history")
