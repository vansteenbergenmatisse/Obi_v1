"""Fixed answer workflow (PLAN 4.2): small-talk short-circuit -> rewrite -> retrieve/rerank ->
CRAG retry -> refusal -> parent-context expansion -> grounded generation -> citation enforcement.

A plain function pipeline, not an agent loop (ADR-0005 §5): every stage is deterministic given its
inputs, so latency is bounded and each stage is unit-testable with a fake collaborator. The one
non-obvious ordering choice: CRAG's corrective retry runs BETWEEN retrieval and the refusal check —
a weak result gets one retry before refusal is decided — even though DESIGN.md's stage table lists
refusal (5) before CRAG (6). That table enumerates concerns, not call order; refusing before ever
retrying would defeat the point of a corrective retry.

Small-talk short-circuit (added after 4.6): a greeting or meta question ("hi", "what can you do")
is not a retrieval failure — it was never going to match a document — so refusing it as if the
corpus lacked an answer is the wrong behavior, not a safe default. `domain/small_talk.is_small_talk`
is a narrow, closed exact-match classifier (never fuzzy/substring/LLM-based) so a real content
question is never misrouted here; anything that doesn't match runs the full grounded pipeline below,
refusal included. This path skips rewrite, retrieval, CRAG, refusal, and citation enforcement
entirely, and writes no `query_trace` row — it isn't a retrieval event.

Image analysis (PLAN 7.3, ADR-0009): unlike small-talk, an image on the newest turn does not skip
retrieval — a query can legitimately need both Confluence evidence and image content. What it does
change is `decide_refusal`'s `has_image` gate (a text-empty-but-image-answerable turn should not
refuse) and adds a second, independent `generate_image_analysis` call whose output rides alongside
`text` on `Answer.image_analysis`, never merged into it and never passed through citation
enforcement. **Disclosed gap, not decided by ADR-0009:** a turn classified as small-talk still
short-circuits before this logic even runs, so a greeting with an attached image ("hi" + a
screenshot) gets the small-talk reply and the image is silently dropped — `is_small_talk` only
ever looks at message text. Revisit if this is raised as a real product gap.

Ambiguity classification (PLAN 9.2, ADR-0008): checked right after small-talk, before
rewrite/retrieval — a message that is an exact small-talk match (e.g. "hi") is checked first and
never reaches this branch, which is this repo's explicit tie-break for the "hi, what's the approval
process?" case ADR-0008 flagged as needing one: `is_small_talk` requires the *whole* message to
match, so a real question glued onto a greeting still runs the clarification check normally.
**PLAN 9.2's own scope is the classifier only** — when `enable_clarification_branch` is on, the
decision is computed and logged for tuning against `evaluation/datasets/ambiguity.json`, but it
does not change `Answer` or skip any pipeline stage; the actual bypass + clarifying-question
generation is PLAN 9.3. When the flag is off (the default), `decide_clarification` is never called
at all — zero added cost or behavior change.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.features.rag_agent.domain.citations import enforce_citations
from app.features.rag_agent.domain.clarification import AmbiguityClassifier, decide_clarification
from app.features.rag_agent.domain.prompt import build_evidence_block
from app.features.rag_agent.domain.refusal import decide_refusal
from app.features.rag_agent.domain.small_talk import is_small_talk
from app.features.rag_agent.infrastructure.llm_client import AnswerGenerator, QueryRewriter
from app.features.rag_agent.schemas import Answer, ChatMessage, Citation
from app.features.retrieval import HybridRetriever, RetrievalResult, update_query_trace_answer
from app.platform.logging import get_logger

log = get_logger("rag_agent.answer_service")

_REFUSAL_TEXT = "I don't have that in the documentation I can search — routing this to a human."
_NO_GROUNDED_CLAIM_REASON = "no claim in the generated answer survived citation enforcement"


@runtime_checkable
class AnswerProvider(Protocol):
    """The shape `POST /chat` depends on — satisfied by `AnswerService` itself and by
    `answer_cache.CachingAnswerService`, which wraps one `AnswerProvider` around another."""

    def answer(self, history: Sequence[ChatMessage], scope: str | None) -> Answer: ...


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
        clarification_classifier: AmbiguityClassifier | None = None,
        enable_clarification_branch: bool = False,
    ) -> None:
        self._retriever = retriever
        self._rewriter = rewriter
        self._generator = generator
        self._writer_sessionmaker = writer_sessionmaker
        self._rewrite_enabled = rewrite_enabled
        self._refusal_min_rerank_score = refusal_min_rerank_score
        self._crag_max_retries = max(0, crag_max_retries)
        self._retrieve_k = retrieve_k
        self._clarification_classifier = clarification_classifier
        self._enable_clarification_branch = enable_clarification_branch

    def answer(self, history: Sequence[ChatMessage], scope: str | None) -> Answer:
        if not history or history[-1].role != "user":
            raise ValueError("history must be non-empty and end with a user turn")
        original_query = history[-1].content
        images = history[-1].images or []
        has_image = bool(images)

        if is_small_talk(original_query):
            text = self._generator.generate_small_talk(original_query)
            return Answer(text=text, citations=[], refused=False, trace_id=None)

        if self._enable_clarification_branch and self._clarification_classifier is not None:
            decision = decide_clarification(original_query, history, self._clarification_classifier)
            log.info(
                "clarification_decision",
                is_ambiguous=decision.is_ambiguous,
                reason=decision.reason,
            )
            # PLAN 9.2 scope ends here: observe and tune the classifier only. PLAN 9.3 adds the
            # actual bypass + clarifying-question generation once `is_ambiguous` verdicts are
            # trusted — until then, the pipeline below always runs regardless of `decision`.

        if original_query.strip():
            rewritten = self._rewriter.rewrite(history) if self._rewrite_enabled else original_query
            result = self._retriever.retrieve_with_context(rewritten, scope, k=self._retrieve_k)
            result = self._apply_crag_retry(result, original_query, rewritten, scope)
        else:
            # A genuinely text-empty, image-only turn (PLAN 7.8) — there is no query to rewrite or
            # embed; the embedding provider rejects an empty string outright (OpenAI: 400 "input
            # cannot be an empty string"). Treat as no retrieved candidates instead of calling it —
            # `has_image`'s decide_refusal gate below already means this does not force a refusal,
            # so this takes the exact same degrade path a real no-candidates-with-image turn does.
            rewritten = original_query
            result = RetrievalResult()

        image_analysis = (
            self._generator.generate_image_analysis(original_query, images) if has_image else None
        )

        decision = decide_refusal(result.top_score, self._refusal_min_rerank_score, has_image)
        trace_id = str(result.trace_id) if result.trace_id is not None else None
        if decision.refuse:
            self._persist(result.trace_id, rewritten, _REFUSAL_TEXT, [])
            return Answer(
                text=_REFUSAL_TEXT,
                refused=True,
                refusal_reason=decision.reason,
                trace_id=trace_id,
                image_analysis=image_analysis,
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
            # `image_analysis` (if any) still rides along — the citation-enforcement refusal is
            # about the grounded claim only and is unaffected by has_image (ADR-0009 decision 3).
            self._persist(result.trace_id, rewritten, _REFUSAL_TEXT, [])
            return Answer(
                text=_REFUSAL_TEXT,
                refused=True,
                refusal_reason=_NO_GROUNDED_CLAIM_REASON,
                trace_id=trace_id,
                image_analysis=image_analysis,
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
        return Answer(
            text=cleaned,
            citations=citations,
            refused=False,
            trace_id=trace_id,
            image_analysis=image_analysis,
        )

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
