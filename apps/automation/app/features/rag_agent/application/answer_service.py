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
ever looks at message text. **Same gap, same reason, for the clarification branch below (PLAN 9.3):
its bypass also returns before image analysis runs, so an ambiguous query with an attached image
gets a clarifying question and the image is silently dropped.** Revisit either if raised as a real
product gap.

Ambiguity classification + clarification (PLAN 9.2/9.3, ADR-0008): checked right after small-talk,
before rewrite/retrieval — a message that is an exact small-talk match (e.g. "hi") is checked first
and never reaches this branch, which is this repo's explicit tie-break for the "hi, what's the
approval process?" case ADR-0008 flagged as needing one: `is_small_talk` requires the *whole*
message to match, so a real question glued onto a greeting still runs the clarification check
normally. When `enable_clarification_branch` is on and the classifier verdict is `is_ambiguous`,
this bypasses rewrite/retrieval/CRAG/refusal and returns a clarifying question (PLAN 9.3,
`generate_clarification`) instead — same shape as small-talk: no `query_trace` row, `refused`
stays False (`needs_clarification=True` is a still-open turn, not a refusal, per ADR-0008 decision
4). A non-ambiguous verdict is only logged (`clarification_decision`) and changes nothing — the
pipeline below runs exactly as it would with the branch disabled. When the flag is off (the
default), `decide_clarification` is never called at all — zero added cost or behavior change.

Differentiated refusal copy (PLAN 9.4, ADR-0008 decision 5): each of the three refusal-reason
categories (`no_candidates | weak_score | no_citations`, `domain/refusal.RefusalReason`) gets its
own honest, user-facing string (`_REFUSAL_COPY`) instead of one identical `_REFUSAL_TEXT` for all
three — a user can now tell "nothing like this exists" from "I found something too weak to trust"
from "my draft answer didn't hold up," while `refusal_reason` itself stays a stable category (not
a diagnostic string with an interpolated score) so it can be grouped on for fallback-rate reporting
(PLAN 9.7). Human hand-off (ADR-0008 decision 6) is still a stub this phase — every reason's copy
ends the same way, and no real integration exists yet.

Human hand-off logging (PLAN 9.6, ADR-0008 decision 6): every `refused=True` answer (both branches
above) emits one additional `human_handoff` structured log record — `trace_id`, `raw_query`,
`refusal_reason` (`created_at` comes free from `configure_logging`'s `TimeStamper` processor, not a
manual field, matching every other log call in this module). `raw_query` is deliberately the user's
verbatim original text, not `rewritten` — a human triaging this queue needs what was actually asked,
not the internal search rewrite. This is a disclosed departure from `router.py`'s own `chat_request`
C9_audit line, which deliberately never logs raw query text; `query_trace.raw_query` (the DB column,
`retrieval/infrastructure/trace_repo.py`) already stores the same unredacted text keyed by this same
`trace_id`, so this log line does not introduce a new place that text is persisted, only a second
place it is readable from. The widget-side "connect me to a human" CTA (PLAN 9.6, `apps/web`) is
static contact copy only — this log line is the entire hand-off mechanism this phase; no webhook,
ticket, or email integration is built (Salesforce is the noted eventual target, see
`docs/future-ideas/IDEAS.md` #1).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.features.rag_agent.domain.citations import enforce_citations
from app.features.rag_agent.domain.clarification import AmbiguityClassifier, decide_clarification
from app.features.rag_agent.domain.curated_knowledge import CuratedEntry, curated_entry_to_hit
from app.features.rag_agent.domain.prompt import build_evidence_block
from app.features.rag_agent.domain.refusal import RefusalReason, decide_refusal
from app.features.rag_agent.domain.small_talk import is_small_talk
from app.features.rag_agent.infrastructure.curated_knowledge_repo import fetch_curated_entries
from app.features.rag_agent.infrastructure.llm_client import AnswerGenerator, QueryRewriter
from app.features.rag_agent.schemas import Answer, ChatMessage, Citation
from app.features.retrieval import (
    HybridRetriever,
    RetrievalResult,
    resolve_allowed_scopes,
    update_query_trace_answer,
)
from app.platform.logging import get_logger

log = get_logger("rag_agent.answer_service")

_NO_CITATIONS_REASON: RefusalReason = "no_citations"

# PLAN 9.4, ADR-0008 decision 5: distinct, honest copy per refusal-reason category (drafted under
# copywriting-rules/ux-writing/anti-ai-writing) — previously all three rendered one identical
# string, so a user could not tell "nothing like this exists" from "I found something too weak to
# trust" from "my draft answer didn't hold up." All three still end on the same human-hand-off
# affordance (ADR-0008 decision 6 is unchanged — still a stub, no real integration).
_REFUSAL_COPY: dict[RefusalReason, str] = {
    "no_candidates": (
        "I couldn't find anything about this in the documentation I can search — "
        "routing this to a human."
    ),
    "weak_score": (
        "I found a few possible matches, but none of them look reliable enough to trust — "
        "routing this to a human."
    ),
    "no_citations": (
        "I put together an answer, but couldn't back every part of it with a real source — "
        "routing this to a human."
    ),
}


@runtime_checkable
class AnswerProvider(Protocol):
    """The shape `POST /chat` depends on — satisfied by `AnswerService` itself and by
    `answer_cache.CachingAnswerService`, which wraps one `AnswerProvider` around another."""

    def answer(
        self, history: Sequence[ChatMessage], scope: str | None, knowledge_scope: str | None = None
    ) -> Answer: ...


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
        recognized_knowledge_scopes: frozenset[str] = frozenset({"general"}),
        default_knowledge_scope: str | None = None,
        reader_sessionmaker: Callable[[], Session] | None = None,
        curated_knowledge_max_entries: int = 5,
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
        self._recognized_knowledge_scopes = recognized_knowledge_scopes
        self._default_knowledge_scope = default_knowledge_scope
        # PLAN 10.6: `None` in any test/deployment that never wires a reader (mirrors
        # `writer_sessionmaker`'s own no-op-when-unset posture at `_persist`, below) — curated
        # entries are then simply never composed into evidence, not an error.
        self._reader_sessionmaker = reader_sessionmaker
        self._curated_knowledge_max_entries = curated_knowledge_max_entries

    def answer(
        self,
        history: Sequence[ChatMessage],
        scope: str | None,
        knowledge_scope: str | None = None,
    ) -> Answer:
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
            if decision.is_ambiguous:
                # PLAN 9.3: bypass rewrite/retrieval/CRAG/refusal, same shape as small-talk above —
                # writes no `query_trace` row (ADR-0008 decision 1), and an image on this turn is
                # silently dropped (see module docstring's disclosed gap, extended from small-talk).
                reply = self._generator.generate_clarification(original_query)
                return Answer(
                    text=reply.question,
                    citations=[],
                    refused=False,
                    trace_id=None,
                    needs_clarification=True,
                    clarification_question=reply.question,
                    clarification_options=reply.options,
                )

        # PLAN 10.5, ADR-0011 decision 6: resolved once per request, not per-retrieval-attempt — the
        # CRAG retry below reuses the same allow-list, it never re-resolves it. Hoisted above the
        # query/no-query split (PLAN 10.6): the always-present curated layer needs it on the
        # text-empty/image-only path too, which never retrieves but still composes curated evidence.
        allowed_scopes = resolve_allowed_scopes(
            knowledge_scope, self._recognized_knowledge_scopes, self._default_knowledge_scope
        )
        requested_scope_unrecognized = (
            knowledge_scope is not None
            and knowledge_scope.lower() not in self._recognized_knowledge_scopes
        )
        if requested_scope_unrecognized:
            # `resolve_allowed_scopes`'s own docstring: "The caller logs the degradation."
            log.info(
                "knowledge_scope_unrecognized",
                requested=knowledge_scope,
                resolved_scopes=allowed_scopes,
            )

        if original_query.strip():
            rewritten = self._rewriter.rewrite(history) if self._rewrite_enabled else original_query
            result = self._retriever.retrieve_with_context(
                rewritten, scope, k=self._retrieve_k, knowledge_scopes=allowed_scopes
            )
            result = self._apply_crag_retry(
                result, original_query, rewritten, scope, allowed_scopes
            )
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
        if decision.refuse and decision.reason is not None:
            # Score-level detail lives here, in the log, not in `refusal_reason` (a static,
            # templated category per router.py's own C9_audit contract, not a diagnostic string).
            log.info(
                "refusal",
                reason=decision.reason,
                top_score=result.top_score,
                threshold=self._refusal_min_rerank_score,
            )
            log.info(
                "human_handoff",
                trace_id=trace_id,
                raw_query=original_query,
                refusal_reason=decision.reason,
            )
            refusal_text = _REFUSAL_COPY[decision.reason]
            self._persist(result.trace_id, rewritten, refusal_text, [])
            return Answer(
                text=refusal_text,
                refused=True,
                refusal_reason=decision.reason,
                trace_id=trace_id,
                image_analysis=image_analysis,
            )

        # PLAN 10.6, ADR-0011: curated entries are always-present, scope-filtered evidence that
        # rides through the exact same numbered evidence/citation machinery a real retrieved hit
        # already uses — curated markers [1..k], retrieved markers [k+1..n] (build_evidence_block
        # numbers `evidence_hits` in order, unchanged itself). Fetched fresh per request (tags can
        # change between requests) and capped so curated content can never crowd out all retrieval
        # evidence.
        curated_entries = self._fetch_curated_entries(allowed_scopes)
        curated_hits = [curated_entry_to_hit(e) for e in curated_entries]
        evidence_hits = [*curated_hits, *result.hits]
        parent_texts = self._retriever.fetch_parent_texts([h.chunk_id for h in result.hits])
        parent_texts = {
            **parent_texts,
            **{
                hit.chunk_id: entry.body
                for hit, entry in zip(curated_hits, curated_entries, strict=True)
            },
        }
        evidence = build_evidence_block(evidence_hits, parent_texts)
        raw_answer = self._generator.generate(rewritten, evidence)
        cleaned, used_markers = enforce_citations(
            raw_answer, valid_markers=range(1, len(evidence_hits) + 1)
        )

        if not used_markers:
            # Every sentence was uncited/mis-cited -> nothing survived grounding. Returning the
            # empty string would be a broken response, and this fixed workflow does not retry
            # generation (only retrieval, via CRAG) — so this degrades to a refusal instead.
            # `image_analysis` (if any) still rides along — the citation-enforcement refusal is
            # about the grounded claim only and is unaffected by has_image (ADR-0009 decision 3).
            log.info("refusal", reason=_NO_CITATIONS_REASON)
            log.info(
                "human_handoff",
                trace_id=trace_id,
                raw_query=original_query,
                refusal_reason=_NO_CITATIONS_REASON,
            )
            refusal_text = _REFUSAL_COPY[_NO_CITATIONS_REASON]
            self._persist(result.trace_id, rewritten, refusal_text, [])
            return Answer(
                text=refusal_text,
                refused=True,
                refusal_reason=_NO_CITATIONS_REASON,
                trace_id=trace_id,
                image_analysis=image_analysis,
            )

        citations = [
            Citation(
                marker=m,
                page_id=evidence_hits[m - 1].page_id,
                title=evidence_hits[m - 1].title,
                url=evidence_hits[m - 1].url,
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
        knowledge_scopes: Sequence[str],
    ) -> RetrievalResult:
        """One corrective retry (PLAN 4.2 stage 6): if the rewrite may have hurt retrieval, retry
        with the user's verbatim query and keep whichever result scored higher. A no-op when
        rewrite is disabled/unchanged — retrying an identical query would return the same result.
        `knowledge_scopes` is the same allow-list `answer()` already resolved once (PLAN 10.5) —
        the retry must stay inside it too, never a second, unscoped search."""
        if self._crag_max_retries <= 0 or rewritten_query == original_query:
            return result
        if result.top_score is not None and result.top_score >= self._refusal_min_rerank_score:
            return result
        retry = self._retriever.retrieve_with_context(
            original_query, scope, k=self._retrieve_k, knowledge_scopes=knowledge_scopes
        )
        if retry.top_score is not None and (
            result.top_score is None or retry.top_score > result.top_score
        ):
            return retry
        return result

    def _fetch_curated_entries(self, allowed_scopes: Sequence[str]) -> list[CuratedEntry]:
        """PLAN 10.6: `[]` when no reader is wired — same no-op posture as `_persist` below when
        `writer_sessionmaker` is unset, so a test/deployment that never configures curated
        knowledge sees zero behavior change."""
        if self._reader_sessionmaker is None:
            return []
        with self._reader_sessionmaker() as session:
            return fetch_curated_entries(
                session, allowed_scopes, self._curated_knowledge_max_entries
            )

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
