"""Fixed answer workflow (PLAN 4.2): small-talk short-circuit -> rewrite -> retrieve/rerank ->
CRAG retry -> refusal -> parent-context expansion -> grounded generation -> citation enforcement.

A plain function pipeline, not an agent loop (ADR-rerank-then-verify-cited-answers §5): every stage is deterministic given its
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

Image analysis (PLAN 7.3, ADR-vision-grounded-image-analysis; substep 3.6.7, panel r5-image): an image on the newest turn is
transcribed by a second, independent `generate_image_analysis` call (verbatim on-screen text + a
short UI description). Substep 3.6.7 moved this call to the very TOP of `answer()`, before every
short-circuit, and put it to work three ways: (1) the transcription FOLDS INTO the one search query
(`_fold_search_query`) so an attached screenshot DRIVES retrieval — an image-only turn now searches
on the transcription instead of building an empty result; (2) it rides to grounded generation as an
uncached CONTEXT block (`generate(..., image_analysis=...)`), never folded into the numbered
evidence, so it never gains a citation marker and never passes citation enforcement (never-bend
rule 7 holds — every answer sentence still cites a real retrieved chunk); (3) it still rides back
on `Answer.image_analysis`, delivered on `done`. It is NOT a retrieval read, so the two-read cap
(rule 8) is unchanged. Memory-only (C6, never-bend rule 10): the transcription is never logged,
never written to the `query_trace` row (the trace records only the text-only query, passed as
`trace_query`), and never persisted. Because the call runs before the short-circuits, a kept image
is no longer silently dropped on a small-talk / identity / clarification turn — those paths still
short-circuit, but the transcription rides back on `Answer.image_analysis` instead of being
discarded (closing the pre-3.6.7 disclosed gap). It still does not change `decide_refusal`'s
`has_image` gate (a text-empty-but-image-answerable turn does not refuse).

Ambiguity classification + clarification (PLAN 9.2/9.3, ADR-ambiguity-clarification-then-fallback-answer): checked right after small-talk,
before rewrite/retrieval — a message that is an exact small-talk match (e.g. "hi") is checked first
and never reaches this branch, which is this repo's explicit tie-break for the "hi, what's the
approval process?" case ADR-ambiguity-clarification-then-fallback-answer flagged as needing one: `is_small_talk` requires the *whole*
message to match, so a real question glued onto a greeting still runs the clarification check
normally. When `enable_clarification_branch` is on and the classifier verdict is `is_ambiguous`,
this bypasses rewrite/retrieval/CRAG/refusal and returns a clarifying question (PLAN 9.3,
`generate_clarification`) instead — same shape as small-talk: no `query_trace` row, `refused`
stays False (`needs_clarification=True` is a still-open turn, not a refusal, per ADR-ambiguity-clarification-then-fallback-answer decision
4). A non-ambiguous verdict is only logged (`clarification_decision`) and changes nothing — the
pipeline below runs exactly as it would with the branch disabled. When the flag is off (the
default), `decide_clarification` is never called at all — zero added cost or behavior change.

Differentiated refusal copy (PLAN 9.4, ADR-ambiguity-clarification-then-fallback-answer decision 5): each of the three refusal-reason
categories (`no_candidates | weak_score | no_citations`, `domain/refusal.RefusalReason`) gets its
own honest, user-facing string (`_REFUSAL_COPY`) instead of one identical `_REFUSAL_TEXT` for all
three — a user can now tell "nothing like this exists" from "I found something too weak to trust"
from "my draft answer didn't hold up," while `refusal_reason` itself stays a stable category (not
a diagnostic string with an interpolated score) so it can be grouped on for fallback-rate reporting
(PLAN 9.7). Human hand-off (ADR-ambiguity-clarification-then-fallback-answer decision 6) is still a stub this phase — every reason's copy
ends the same way, and no real integration exists yet.

Human hand-off logging (PLAN 9.6, ADR-ambiguity-clarification-then-fallback-answer decision 6): every `refused=True` answer (both branches
above) emits one additional `human_handoff` structured log record — `trace_id`, `raw_query`,
`refusal_reason` (`created_at` comes free from `configure_logging`'s `TimeStamper` processor, not a
manual field, matching every other log call in this module). `raw_query` is deliberately the user's
verbatim original text, not `rewritten` — a human triaging this queue needs what was actually asked,
not the internal search rewrite. This is a disclosed departure from `router.py`'s own `chat_request`
C9_audit line, which deliberately never logs raw query text; `query_trace.raw_query` (the DB column,
`retrieval/infrastructure/trace_repo.py`) already stores the same unredacted text keyed by this same
`trace_id`, so this log line does not introduce a new place that text is persisted, only a second
place it is readable from. The widget-side "connect me to a human" CTA (PLAN 9.6, `frontend`) is
static contact copy only — this log line is the entire hand-off mechanism this phase; no webhook,
ticket, or email integration is built (Salesforce is the noted eventual target, see
`docs/future-ideas/IDEAS.md` #1).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.features.rag_agent.application.auth_context import AuthContext
from app.features.rag_agent.application.chat_session import (
    ChatSessionError,
    load_chat_session,
    start_chat_session,
)
from app.features.rag_agent.domain.citations import enforce_citations
from app.features.rag_agent.domain.clarification import AmbiguityClassifier, decide_clarification
from app.features.rag_agent.domain.curated_knowledge import CuratedEntry, curated_entry_to_hit
from app.features.rag_agent.domain.identity import IdentityFacts, is_identity_question
from app.features.rag_agent.domain.prompt import build_evidence_block
from app.features.rag_agent.domain.refusal import RefusalReason, decide_refusal
from app.features.rag_agent.domain.small_talk import is_small_talk
from app.features.rag_agent.infrastructure.curated_knowledge_repo import fetch_curated_entries
from app.features.rag_agent.infrastructure.llm_client import AnswerGenerator, QueryRewriter
from app.features.rag_agent.schemas import Answer, ChatMessage, Citation
from app.features.retrieval import (
    ConnectionRecord,
    CustomerContext,
    HybridRetriever,
    RetrievalResult,
    eligibility_params,
    update_query_trace_answer,
)
from app.platform.config.product_catalog import ProductCatalog
from app.platform.logging import get_logger
from app.shared.hashing import sha256_text

log = get_logger("rag_agent.answer_service")

_NO_CITATIONS_REASON: RefusalReason = "no_citations"

# PLAN 9.4, ADR-ambiguity-clarification-then-fallback-answer decision 5: distinct, honest copy per refusal-reason category (drafted under
# copywriting-rules/ux-writing/anti-ai-writing) — previously all three rendered one identical
# string, so a user could not tell "nothing like this exists" from "I found something too weak to
# trust" from "my draft answer didn't hold up." All three still end on the same human-hand-off
# affordance (ADR-ambiguity-clarification-then-fallback-answer decision 6 is unchanged — still a stub, no real integration).
_REFUSAL_COPY: dict[RefusalReason, str] = {
    "no_candidates": (
        "I couldn't find anything about this in the documentation I can search — "
        "routing this to a human."
    ),
    # off_topic (2026-09-12): a genuinely unrelated question. Softer than the hand-off reasons —
    # steers back to the docs instead of "routing to a human," and the UI shows no hand-off CTA for
    # this reason. Still a refusal (no grounded answer). Copy drafted under copywriting-rules/
    # ux-writing/anti-ai-writing.
    "off_topic": (
        "I can only answer questions about your documentation, so I can't help with that one. "
        "Ask me something covered in the docs and I'll take a look."
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

# off_topic gets a friendly redirect and no human hand-off; every other refusal reason routes to a
# human and emits the `human_handoff` audit record (PLAN 9.6). Keeping this a set (not a bool on the
# decision) keeps the taxonomy the single source of truth for "does this route to a human."
_HANDOFF_REASONS: frozenset[RefusalReason] = frozenset(
    {"no_candidates", "weak_score", "no_citations"}
)


def _fold_search_query(text_query: str, image_analysis: str | None) -> str:
    """Substep 3.6.7 (panel r2-embed): combine the text question with the image transcription into
    the ONE standalone search query, so an attached screenshot DRIVES retrieval. Either part may be
    empty — an image-only turn folds just the transcription (so it now searches instead of building
    an empty result), a text-only turn folds just the question (byte-identical to pre-3.6.7). This
    is the query the search embeds/keyword-matches on; the trace row records only the text query
    (C6, memory-only transcription), passed separately as `trace_query`."""
    parts = [p for p in (text_query.strip(), (image_analysis or "").strip()) if p]
    return "\n\n".join(parts)


@runtime_checkable
class AnswerProvider(Protocol):
    """The shape `POST /chat` depends on — satisfied by `AnswerService` itself and by
    `answer_cache.CachingAnswerService`, which wraps one `AnswerProvider` around another.

    PLAN 11.1c (ADR-db-level-customer-scope-isolation-backstop): the read path is driven by a single frozen `AuthContext` (built from a
    verified edge JWT, or the general-only tokenless context) instead of a caller-reported
    `knowledge_scope` string — `auth.allowed_scopes` are the authoritative retrieval scopes and
    `auth.principal` the page-ACL identity (always `None` for embedded users in v1)."""

    def answer(self, history: Sequence[ChatMessage], auth: AuthContext) -> Answer: ...


class AnswerService:
    def __init__(
        self,
        retriever: HybridRetriever,
        rewriter: QueryRewriter,
        generator: AnswerGenerator,
        writer_sessionmaker: Callable[[], Session] | None = None,
        *,
        rewrite_enabled: bool = True,
        refusal_min_rerank_score: float = 0.05,
        offtopic_max_rerank_score: float = 0.035,
        crag_max_retries: int = 1,
        retrieve_k: int = 5,
        clarification_classifier: AmbiguityClassifier | None = None,
        enable_clarification_branch: bool = False,
        reader_sessionmaker: Callable[[], Session] | None = None,
        curated_knowledge_max_entries: int = 5,
        product_catalog: ProductCatalog | None = None,
        session_store_sessionmaker: Callable[[], Session] | None = None,
    ) -> None:
        self._retriever = retriever
        self._rewriter = rewriter
        self._generator = generator
        self._writer_sessionmaker = writer_sessionmaker
        self._rewrite_enabled = rewrite_enabled
        self._refusal_min_rerank_score = refusal_min_rerank_score
        self._offtopic_max_rerank_score = offtopic_max_rerank_score
        self._crag_max_retries = max(0, crag_max_retries)
        self._retrieve_k = retrieve_k
        self._clarification_classifier = clarification_classifier
        self._enable_clarification_branch = enable_clarification_branch
        # PLAN 10.6: `None` in any test/deployment that never wires a reader (mirrors
        # `writer_sessionmaker`'s own no-op-when-unset posture at `_persist`, below) — curated
        # entries are then simply never composed into evidence, not an error.
        self._reader_sessionmaker = reader_sessionmaker
        self._curated_knowledge_max_entries = curated_knowledge_max_entries
        # Substep 8.3.3 (panel mi-prompt): the committed product catalog, used ONLY to derive the
        # customer's actual connections (§D.4) for the answer prompt's integration-context block.
        # `None` in a test/deployment that never wires it — connections then fall back to the
        # context's own real records (empty at launch), so the prompt simply omits the connections
        # line rather than erroring. It never widens eligibility (the search already enforced that).
        self._product_catalog = product_catalog
        # Option A Stage 6 (substep 9.4.1, panel mi-session): the WRITER sessionmaker for the
        # directed-connection chat-session store. `None` in a test/deployment that never wires it —
        # a directed chat then degrades to no routing (general-only), never an error.
        self._session_store_sessionmaker = session_store_sessionmaker

    def _resolve_directed_routing(self, auth: AuthContext) -> tuple[list[str] | None, str | None]:
        """Option A Stage 6 (substep 9.4.1, panels mi-session/mi-hardfilter, ADR-directed-source-target-routing-labels): resolve the
        directed ``source → target`` chat's session ONCE and reuse it on every later question.

        Returns ``(session_labels, connection_block)``: the four routing labels feed the retrieval
        hard filter + the ``app.allowed_labels`` GUC; the connection block feeds the answer prompt.
        Chat-start (the one catalog lookup) runs only on the first question of a chat or on a
        partner switch (a different source/target); otherwise the stored row is reused, no lookup
        (never-bend rule 8 — the session read is a keyed lookup, not a corpus search). A
        legacy/slot/tokenless chat is NOT directed, so this returns ``(None, None)`` and the label
        filter is a no-op (labels are the relevance axis, not the access fence — locks 1-2 stand).
        The connection comes only from the verified token/session, never the request body (rules
        2-3)."""
        if auth.source_slug is None and auth.target_slug is None:
            return None, None  # not a directed-connection chat
        if self._product_catalog is None or self._session_store_sessionmaker is None:
            return None, None  # store/catalog not wired (an uncoupled test path)
        try:
            with self._session_store_sessionmaker() as session:
                row = load_chat_session(session, auth)
                if (
                    row is None
                    or row.source_slug != auth.source_slug
                    or row.target_slug != auth.target_slug
                ):
                    row = start_chat_session(
                        session,
                        auth,
                        source_system=auth.source_slug or "",
                        target_system=auth.target_slug or "",
                        business_id=auth.company_id or "",
                        catalog=self._product_catalog,
                    )
                labels = list(row.labels)
                connection_block = row.connection_block
                session.commit()
            return labels, connection_block
        except ChatSessionError:
            # a directed form always rides a verified token carrying subject + company; if either is
            # missing the session cannot be keyed -> degrade to general-only, never crash.
            return None, None

    def answer(self, history: Sequence[ChatMessage], auth: AuthContext) -> Answer:
        if not history or history[-1].role != "user":
            raise ValueError("history must be non-empty and end with a user turn")
        original_query = history[-1].content
        images = history[-1].images or []
        has_image = bool(images)

        # Substep 3.6.7 (panel r5-image): transcribe the image FIRST — before every short-circuit —
        # so (a) a kept image is never silently dropped on a small-talk/identity/clarification turn
        # (the transcription still rides back on `Answer.image_analysis`), and (b) on the grounded
        # path below the transcription can fold into the search query to DRIVE retrieval and ride to
        # the answer as context. This vision call is NOT a retrieval read — it never counts against
        # the two-read cap (never-bend rule 8). Memory-only (C6): the transcription is never logged,
        # written to the trace row, or persisted.
        image_analysis = (
            self._generator.generate_image_analysis(original_query, images) if has_image else None
        )

        if is_small_talk(original_query):
            text = self._generator.generate_small_talk(original_query)
            return Answer(
                text=text,
                citations=[],
                refused=False,
                trace_id=None,
                image_analysis=image_analysis,
            )

        # Per-user identity path (operator-requested 2026-09-12): checked right after small-talk,
        # before rewrite/retrieval. A basic identity question ("which integration do we use?",
        # "what company am I?") is not a retrieval failure — it was never going to match a document,
        # and the answer is already carried by the verified `auth` — so it short-circuits to a
        # dedicated ungrounded reply seeded with the token's identity facts (plus the operator's
        # static block, held by the generator) instead of running retrieval and refusing off_topic.
        # Same shape as small-talk: no rewrite/retrieval/CRAG/refusal/citation-enforcement, no
        # `query_trace` row, `refused=False`. `is_identity_question` is a closed exact-match set, so
        # a real content question that merely shares words still runs the full grounded pipeline.
        if is_identity_question(original_query):
            facts = IdentityFacts(
                integration=auth.integration,
                company_name=auth.company_name,
                company_id=auth.company_id,
            )
            text = self._generator.generate_identity(original_query, facts)
            return Answer(
                text=text,
                citations=[],
                refused=False,
                trace_id=None,
                image_analysis=image_analysis,
            )

        if self._enable_clarification_branch and self._clarification_classifier is not None:
            decision = decide_clarification(original_query, history, self._clarification_classifier)
            log.info(
                "clarification_decision",
                is_ambiguous=decision.is_ambiguous,
                reason=decision.reason,
            )
            if decision.is_ambiguous:
                # PLAN 9.3: bypass rewrite/retrieval/CRAG/refusal, same shape as small-talk above —
                # writes no `query_trace` row (ADR-ambiguity-clarification-then-fallback-answer decision 1). Substep 3.6.7 (panel r5-image):
                # a kept image is no longer silently dropped here — the transcription computed above
                # rides back on `Answer.image_analysis`.
                reply = self._generator.generate_clarification(original_query)
                return Answer(
                    text=reply.question,
                    citations=[],
                    refused=False,
                    trace_id=None,
                    needs_clarification=True,
                    clarification_question=reply.question,
                    clarification_options=reply.options,
                    image_analysis=image_analysis,
                )

        # ADR-routing-labels-sole-content-axis: the knowledge-scope axis is retired, so `auth.allowed_scopes` is empty and the
        # scope filter is inert (retrieval opts the scope GUC out; content is routed by labels).
        # This list is still threaded through so the curated layer's app-overlap query keeps its
        # shape (empty → the always-included empty-tag entries). `scope` is the page-ACL principal
        # (always None for embedded users in v1).
        allowed_scopes = list(auth.allowed_scopes)
        scope = auth.principal
        # Substep 8.3.1 (panel mi-filter): the VERIFIED slots + host platform become the one
        # CustomerContext retrieval filters eligibility by, inside the search SQL — never a
        # body value. Empty slots mean general-only eligibility; unstamped pages are unaffected
        # (absence never excludes). The CRAG retry below reuses this same context.
        customer_context = CustomerContext(
            slot_pos=auth.slot_pos,
            slot_pms=auth.slot_pms,
            slot_accounting=auth.slot_accounting,
            platform=auth.platform,
        )
        # Substep 9.4.1 (panels mi-session/mi-hardfilter, ADR-directed-source-target-routing-labels): resolve this directed chat's
        # session once (chat-start) and reuse it per question. The four routing labels feed the
        # retrieval hard filter below; the connection block feeds the answer prompt. A
        # legacy/slot/tokenless chat is not directed -> (None, None), so the filter is a no-op and
        # the prompt carries no connection block (pre-9.4.1 behavior). The CRAG retry reuses the
        # same labels, so the retry can never widen the connection.
        session_labels, connection_block = self._resolve_directed_routing(auth)
        # PLAN 11.1c (ADR-db-level-customer-scope-isolation-backstop): audit *who* asked as sha256(sub) — never the raw subject/token.
        subject_hash = sha256_text(auth.token_subject).hex() if auth.token_subject else None

        # The rewritten standalone question (text only). Rewrite is skipped when disabled or when
        # there is no text to rewrite (an image-only turn), so `rewritten` is then "".
        rewritten = (
            self._rewriter.rewrite(history)
            if self._rewrite_enabled and original_query.strip()
            else original_query
        )
        # Substep 3.6.7 (panels r2-embed/r5-image): the image transcription folds into the ONE
        # search query so it DRIVES retrieval. The search embeds/keyword-matches on the folded
        # query; the trace row records only the text-only query (`trace_query=rewritten`) — the
        # transcription is memory-only and never persisted (C6). An image-only turn's folded query
        # is the transcription alone, so it now SEARCHES instead of building an empty result.
        search_query = _fold_search_query(rewritten, image_analysis)
        # The CRAG fallback query folds the user's VERBATIM text (not the rewrite) with the same
        # transcription, and traces only the verbatim text.
        retry_search_query = _fold_search_query(original_query, image_analysis)
        if search_query:
            result = self._retriever.retrieve_with_context(
                search_query,
                scope,
                k=self._retrieve_k,
                knowledge_scopes=allowed_scopes,
                customer_context=customer_context,
                trace_query=rewritten,
                session_labels=session_labels,
            )
            result = self._apply_crag_retry(
                result,
                search_query,
                retry_search_query,
                original_query,
                scope,
                allowed_scopes,
                customer_context,
                session_labels,
            )
        else:
            # No text AND no transcription (e.g. an image whose vision call produced nothing) —
            # nothing to embed. Treat as no retrieved candidates; `has_image`'s decide_refusal gate
            # below means this does not force a refusal, the same degrade path a real
            # no-candidates-with-image turn takes.
            result = RetrievalResult()

        decision = decide_refusal(
            result.top_score,
            self._refusal_min_rerank_score,
            has_image,
            self._offtopic_max_rerank_score,
        )
        trace_id = str(result.trace_id) if result.trace_id is not None else None
        if decision.refuse and decision.reason is not None:
            # Score-level detail lives here, in the log, not in `refusal_reason` (a static,
            # templated category per router.py's own C9_audit contract, not a diagnostic string).
            log.info(
                "refusal",
                reason=decision.reason,
                top_score=result.top_score,
                threshold=self._refusal_min_rerank_score,
                offtopic_threshold=self._offtopic_max_rerank_score,
            )
            # off_topic is a friendly redirect, not a hand-off — emit a distinct audit record so
            # PLAN 9.7 fallback-rate reporting can tell "sent to a human" from "steered back to the
            # docs." The hand-off reasons keep the existing `human_handoff` record unchanged.
            if decision.reason in _HANDOFF_REASONS:
                log.info(
                    "human_handoff",
                    trace_id=trace_id,
                    raw_query=original_query,
                    refusal_reason=decision.reason,
                )
            else:
                log.info(
                    "off_topic_redirect",
                    trace_id=trace_id,
                    raw_query=original_query,
                    refusal_reason=decision.reason,
                )
            refusal_text = _REFUSAL_COPY[decision.reason]
            self._persist(result.trace_id, rewritten, refusal_text, [], subject_hash)
            return Answer(
                text=refusal_text,
                refused=True,
                refusal_reason=decision.reason,
                trace_id=trace_id,
                image_analysis=image_analysis,
            )

        # PLAN 10.6, ADR-knowledge-scope-tagging-and-filtering: curated entries are always-present, scope-filtered evidence that
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
        # Per-chat business context for the answer prompt comes from the verified auth context
        # only (never the request body). A missing value is passed through as None and omitted
        # downstream, never guessed. Response context only; access stays governed by search/DB.
        #
        # Substep 8.3.3 (panel mi-prompt, §D.7): the SAME verified context the search (8.3.1) and
        # reranker (8.3.2) already used is threaded into the answer prompt — slots + host platform
        # plus the customer's actual connections, derived through the catalog by the exact §D.4
        # derivation the search eligibility used (one semantics, two executors). When no catalog is
        # wired the connections fall back to the context's own real records. This is answer
        # guidance only — the backend alone enforces eligibility (rule 3); the prompt never widens
        # access.
        prompt_connections: tuple[ConnectionRecord, ...] = (
            eligibility_params(customer_context, self._product_catalog).connections
            if self._product_catalog is not None
            else customer_context.connections
        )
        raw_answer = self._generator.generate(
            rewritten,
            evidence,
            company_name=auth.company_name,
            integration=auth.integration,
            customer_context=customer_context,
            connections=prompt_connections,
            image_analysis=image_analysis,
            connection_block=connection_block,
        )
        cleaned, used_markers = enforce_citations(
            raw_answer, valid_markers=range(1, len(evidence_hits) + 1)
        )

        if not used_markers:
            # Every sentence was uncited/mis-cited -> nothing survived grounding. Returning the
            # empty string would be a broken response, and this fixed workflow does not retry
            # generation (only retrieval, via CRAG) — so this degrades to a refusal instead.
            # `image_analysis` (if any) still rides along — the citation-enforcement refusal is
            # about the grounded claim only and is unaffected by has_image (ADR-vision-grounded-image-analysis decision 3).
            log.info("refusal", reason=_NO_CITATIONS_REASON)
            log.info(
                "human_handoff",
                trace_id=trace_id,
                raw_query=original_query,
                refusal_reason=_NO_CITATIONS_REASON,
            )
            refusal_text = _REFUSAL_COPY[_NO_CITATIONS_REASON]
            self._persist(result.trace_id, rewritten, refusal_text, [], subject_hash)
            return Answer(
                text=refusal_text,
                refused=True,
                refusal_reason=_NO_CITATIONS_REASON,
                trace_id=trace_id,
                image_analysis=image_analysis,
            )

        # Substep 8.3.4 (panel mi-attrib, §D.13 keuze 3): the attribution the backend already
        # assembled on each hit (the §D.4 matcher reason, collapsed to the citation enum) rides
        # straight onto the Citation — the widget renders what the backend decided, never
        # recomputing eligibility (rule 3). A curated hit, a label-only page, or the no-context
        # path carries None, so the field is simply absent on the wire (unchanged from pre-8.3.4).
        # The Citation schema's Literal re-validates the value server-side (fail-closed).
        citations = [
            Citation(
                marker=m,
                page_id=evidence_hits[m - 1].page_id,
                title=evidence_hits[m - 1].title,
                url=evidence_hits[m - 1].url,
                attribution=evidence_hits[m - 1].attribution,
            )
            for m in used_markers
        ]
        self._persist(result.trace_id, rewritten, cleaned, citations, subject_hash)
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
        search_query: str,
        retry_search_query: str,
        retry_trace_query: str,
        scope: str | None,
        knowledge_scopes: Sequence[str],
        customer_context: CustomerContext | None = None,
        session_labels: Sequence[str] | None = None,
    ) -> RetrievalResult:
        """One corrective retry (PLAN 4.2 stage 6): if the rewrite may have hurt retrieval, retry
        with the user's verbatim query and keep whichever result scored higher. A no-op when
        rewrite is disabled/unchanged — retrying an identical query would return the same result.
        `knowledge_scopes` is the same allow-list `answer()` already resolved once (PLAN 10.5) —
        the retry must stay inside it too, never a second, unscoped search; `customer_context`
        is the same verified context (8.3.1), so the retry filters eligibility identically.
        `session_labels` is the same directed-connection label list (9.4.1), so the retry can never
        widen past this chat's four routing boxes (the hard filter + GUC apply identically).

        Substep 3.6.7: `search_query` / `retry_search_query` carry the same folded image
        transcription (when any), so the retry still DRIVES retrieval on the image; the retry
        traces only `retry_trace_query` (the verbatim text), never the transcription (C6). This is
        still a single retry — at most two reads total (never-bend rule 8)."""
        if self._crag_max_retries <= 0 or search_query == retry_search_query:
            return result
        if result.top_score is not None and result.top_score >= self._refusal_min_rerank_score:
            return result
        retry = self._retriever.retrieve_with_context(
            retry_search_query,
            scope,
            k=self._retrieve_k,
            knowledge_scopes=knowledge_scopes,
            customer_context=customer_context,
            trace_query=retry_trace_query,
            session_labels=session_labels,
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
        subject_hash: str | None = None,
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
                subject_hash=subject_hash,
            )
