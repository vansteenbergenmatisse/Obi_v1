"""Fixed answer workflow (PLAN 4.2): rewrite -> retrieve/rerank -> CRAG retry -> refusal ->
parent-context expansion -> grounded generation -> citation enforcement.

A plain function pipeline, not an agent loop (ADR-0005 §5): every stage is deterministic given its
inputs, so latency is bounded and each stage is unit-testable with a fake collaborator. The one
non-obvious ordering choice: CRAG's corrective retry runs BETWEEN retrieval and the refusal check —
a weak result gets one retry before refusal is decided — even though DESIGN.md's stage table lists
refusal (5) before CRAG (6). That table enumerates concerns, not call order; refusing before ever
retrying would defeat the point of a corrective retry.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from app.features.rag_agent.domain.citations import enforce_citations
from app.features.rag_agent.domain.prompt import build_evidence_block
from app.features.rag_agent.domain.refusal import decide_refusal
from app.features.rag_agent.infrastructure.llm_client import AnswerGenerator, QueryRewriter
from app.features.rag_agent.schemas import Answer, ChatMessage, Citation
from app.features.retrieval import HybridRetriever, RetrievalResult, update_query_trace_answer

_REFUSAL_TEXT = "I don't have that in the documentation I can search — routing this to a human."
_NO_GROUNDED_CLAIM_REASON = "no claim in the generated answer survived citation enforcement"


class AnswerService:
    def __init__(
        self,
        retriever: HybridRetriever,
        rewriter: QueryRewriter,
        generator: AnswerGenerator,
        writer_sessionmaker: Callable[[], Session] | None = None,
        *,
        rewrite_enabled: bool = True,
        refusal_min_rerank_score: float = 0.10,
        crag_max_retries: int = 1,
        retrieve_k: int = 5,
    ) -> None:
        self._retriever = retriever
        self._rewriter = rewriter
        self._generator = generator
        self._writer_sessionmaker = writer_sessionmaker
        self._rewrite_enabled = rewrite_enabled
        self._refusal_min_rerank_score = refusal_min_rerank_score
        self._crag_max_retries = max(0, crag_max_retries)
        self._retrieve_k = retrieve_k

    def answer(self, history: Sequence[ChatMessage], scope: str | None) -> Answer:
        if not history or history[-1].role != "user":
            raise ValueError("history must be non-empty and end with a user turn")
        original_query = history[-1].content
        rewritten = self._rewriter.rewrite(history) if self._rewrite_enabled else original_query

        result = self._retriever.retrieve_with_context(rewritten, scope, k=self._retrieve_k)
        result = self._apply_crag_retry(result, original_query, rewritten, scope)

        decision = decide_refusal(result.top_score, self._refusal_min_rerank_score)
        trace_id = str(result.trace_id) if result.trace_id is not None else None
        if decision.refuse:
            self._persist(result.trace_id, rewritten, _REFUSAL_TEXT, [])
            return Answer(
                text=_REFUSAL_TEXT, refused=True, refusal_reason=decision.reason, trace_id=trace_id
            )

        parent_texts = self._retriever.fetch_parent_texts([h.chunk_id for h in result.hits])
        evidence = build_evidence_block(result.hits, parent_texts)
        raw_answer = self._generator.generate(rewritten, evidence)
        cleaned, used_markers = enforce_citations(
            raw_answer, valid_markers=range(1, len(result.hits) + 1)
        )

        if not used_markers:
            # Every sentence was uncited/mis-cited -> nothing survived grounding. Returning the
            # empty string would be a broken response, and this fixed workflow does not retry
            # generation (only retrieval, via CRAG) — so this degrades to a refusal instead.
            self._persist(result.trace_id, rewritten, _REFUSAL_TEXT, [])
            return Answer(
                text=_REFUSAL_TEXT,
                refused=True,
                refusal_reason=_NO_GROUNDED_CLAIM_REASON,
                trace_id=trace_id,
            )

        citations = [
            Citation(
                marker=m,
                page_id=result.hits[m - 1].page_id,
                title=result.hits[m - 1].title,
                url=result.hits[m - 1].url,
            )
            for m in used_markers
        ]
        self._persist(result.trace_id, rewritten, cleaned, citations)
        return Answer(text=cleaned, citations=citations, refused=False, trace_id=trace_id)

    def _apply_crag_retry(
        self,
        result: RetrievalResult,
        original_query: str,
        rewritten_query: str,
        scope: str | None,
    ) -> RetrievalResult:
        """One corrective retry (PLAN 4.2 stage 6): if the rewrite may have hurt retrieval, retry
        with the user's verbatim query and keep whichever result scored higher. A no-op when
        rewrite is disabled/unchanged — retrying an identical query would return the same result."""
        if self._crag_max_retries <= 0 or rewritten_query == original_query:
            return result
        if result.top_score is not None and result.top_score >= self._refusal_min_rerank_score:
            return result
        retry = self._retriever.retrieve_with_context(original_query, scope, k=self._retrieve_k)
        if retry.top_score is not None and (
            result.top_score is None or retry.top_score > result.top_score
        ):
            return retry
        return result

    def _persist(
        self,
        trace_id: int | None,
        rewritten_query: str,
        answer_text: str,
        citations: list[Citation],
    ) -> None:
        if trace_id is None or self._writer_sessionmaker is None:
            return
        with self._writer_sessionmaker() as session:
            update_query_trace_answer(
                session,
                trace_id,
                rewritten_query=rewritten_query,
                answer=answer_text,
                citations=[c.model_dump() for c in citations],
            )
