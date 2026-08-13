"""Chat HTTP surface: `POST /chat` (SSE) + `PATCH /chat/{trace_id}/feedback` (PLAN 4.4).

Both an HTTP and an LLM surface (ADR-0005 §10) — the full `securing-http-and-llm-endpoints`
control set applies. `POST /chat` is STATE-MUTATING (writes/updates a `query_trace` row) AND
LLM-CALL (rewrite + generation), so it satisfies the union of both tiers' required controls.
`PATCH /chat/{trace_id}/feedback` is STATE-MUTATING only.

security_baseline (surface: POST /chat, tier STATE-MUTATING + LLM-CALL):
  C1_auth:        covered   - shared-secret `chat_api_key` via `Authorization: Bearer`,
                              constant-time compare; fail-closed (503) when unset. A second,
                              optional `chat_api_key_previous` is accepted in parallel (both
                              compares always run, never short-circuited) so a key can rotate
                              through a bounded overlap window without an outage — see
                              `docs/runbooks/chat-api-key-rotation.md` (PLAN 5).
  C2_rate_limit:  covered   - per-client-IP sliding window (chat_rate_limit_per_minute). Keyed on
                              IP only, never the caller-reported `principal` (PLAN 4.6.4 fix — a
                              principal-first key let a caller bypass the limit entirely by
                              rotating principal on every request).
  C3_input:       covered   - Pydantic body (extra=forbid); history non-empty + ends on a user
                              turn; per-turn length cap + history-length cap (chat_max_*); an
                              all-digit `principal` is rejected (PLAN 5.3 red-team finding — see
                              `ChatRequestBody`'s validator docstring). PLAN 7.3/7.4 (ADR-0009):
                              per-turn image count cap (chat_max_images_per_turn) + per-image byte
                              cap (chat_max_image_bytes), checked on every turn's `images`, not
                              just the newest — a caller could otherwise stuff an oversized image
                              on an older turn to dodge a newest-turn-only check.
  C4_timeout:     covered   - retrieval's embedder/reranker already carry timeout/retry/breaker
                              (3.5.2/3); the answer-runtime AnthropicMessagesClient now does too
                              (answer_timeout_seconds/max_retries/breaker_threshold, PLAN 4.4).
  C5_output_rate: covered   - generation is token-capped (llm_client.py); the streamed answer is
                              defensively re-capped (chat_output_max_answer_chars) and paced into
                              fixed-size SSE chunks (chat_token_chunk_chars/stream_interval_ms).
  C6_redaction:   covered   - `redact_pii` scrubs the assembled prompt before every rewrite/
                              generation call (llm_client.py); see rag_agent/domain/pii.py.
                              PLAN 7.3 (ADR-0009 decision 6): does NOT extend to image bytes on
                              `ChatMessage.images` — a disclosed, accepted gap, not a silent one;
                              see pii.py's module docstring addendum. PLAN 9.2/9.3 (ADR-0008): the
                              ambiguity classifier and clarification-question generation calls
                              redact the query text the same way — the latter's reply is shown
                              directly to the user (unlike the classifier's single-word verdict),
                              so its system prompt also carries a defensive instruction against
                              treating query-embedded text as an instruction to follow (mirroring
                              PLAN 7.3's image-analysis prompt); the required live-model
                              adversarial pass for this new path is PLAN 9.8, not this sub-step.
  C7_idempotency: covered   - optional `Idempotency-Key` header; a replay within the TTL window
                              returns the cached Answer without re-running retrieval/generation.
                              The cache key binds the header to a hash of (principal, history) —
                              not the raw header alone (PLAN 4.6.3 fix) — so a replayed key sent
                              with a different principal or history can never return another
                              caller's cached Answer; it is treated as a fresh request instead.
  C8_concurrency: opted_out - each request creates its own query_trace row; no shared-resource
                              read-modify-write.
  C9_audit:       covered   - one structured `chat_request` log line per call (conversation id,
                              trace id, refused, refusal reason, needs_clarification (PLAN 9.3),
                              citation count, latency) — never the raw message or answer text;
                              `refusal_reason` is one of the closed `no_candidates | weak_score |
                              no_citations` category strings (PLAN 9.4, ADR-0008 decision 4/type-
                              enforced by `RefusalReason`), never a free-text diagnostic and never
                              user query or retrieved content. PLAN 9.6 (ADR-0008 decision 6) adds
                              a second, disclosed exception to "never user query": on every
                              `refused=True` answer, `answer_service.py` emits one `human_handoff`
                              log line carrying `trace_id`/`raw_query`/`refusal_reason`, for the
                              stub human hand-off queue — `raw_query` is the verbatim user text,
                              not redacted, matching the pre-existing `query_trace.raw_query` DB
                              column already keyed by the same `trace_id` (not a new place this
                              text is persisted, only a second place it is read from).
  C10_abuse:      covered   - rate limit + history/message-length caps + the Anthropic client's
                              abuse cap (answer_max_input_chars) + circuit breaker. PLAN 7.3
                              (ADR-0009 decision 7): `generate_image_analysis` is a second,
                              unconditional LLM call whenever a turn has images — the per-turn
                              image-count/byte caps above are this call's own abuse control,
                              since `answer_max_input_chars` only ever measures text length.
                              PLAN 9.2/9.3 (ADR-0008): the ambiguity classifier + clarification-
                              question generation are two more bounded calls, gated behind
                              `enable_clarification_branch` (default off) and only reachable
                              through this already-rate-limited endpoint — no incremental abuse
                              surface beyond one more call per already-capped request.

security_baseline (surface: PATCH /chat/{trace_id}/feedback, tier STATE-MUTATING):
  C1_auth:        covered   - same shared-secret check (current + previous) as POST /chat.
  C2_rate_limit:  covered   - same limiter/key as POST /chat.
  C3_input:       covered   - feedback constrained to Literal[-1, 1].
  C4_timeout:     covered   - one bound UPDATE statement, no fan-out.
  C7_idempotency: covered   - the UPDATE is naturally idempotent: replaying the same feedback
                              value produces the same row state.
  C8_concurrency: opted_out - single UPDATE by primary key; last-write-wins is the correct
                              semantics for a thumbs up/down toggle, not a bug to fix with a lock.
  C9_audit:       covered   - structured `chat_feedback` log line (trace id, value).
  C10_abuse:      covered   - same rate limiter as POST /chat.

Known, documented limitation (not a bug): there is no end-user login system yet, so `principal`
is caller-self-reported, trusted only as far as C1 trusts the calling web proxy. Per ADR-0004's
default-deny model, an absent/unverified principal can only ever see *unrestricted* pages
(`PrincipalPermissionPolicy.allowed`) — it is never a blanket-access bypass. Real per-user identity
is a later phase; this endpoint is already safe in its absence.

PLAN 5.3 red-team finding (fixed here, not just documented): `PrincipalPermissionPolicy.allowed`
overloads the same `scope: str | None` type for two different trust levels — an all-digit scope is
treated as **space-level trust**, granting every page in that space regardless of its
`page_restriction` list (this is deliberate and still needed: it is how the eval harness scopes
`retrieval_smoke.json`, see `retrieval/domain/permission.py`'s docstring). Nothing in the domain
policy itself distinguishes "trusted internal space-scope caller" from "arbitrary HTTP caller who
happened to type a digit", so an unvalidated `principal` would let any caller claim space-wide
access by guessing a real `space_id` (small sequential integers, not a secret) — a genuine
blanket-access bypass the paragraph above assumed couldn't happen. Closed at the HTTP boundary
(`ChatRequestBody`'s validator below) rather than in the shared domain policy, since a real
production principal is never a bare digit string in this system (fixture identities are
`acct-alice`, `grp-hr`, etc.) and the eval harness never goes through this endpoint.

PLAN 5 addendum: `get_answer_service_dep` may return either the real `AnswerService` or
`answer_cache.CachingAnswerService` wrapping it (see `main.build_answer_service`'s call site).
Transparent to this module and to every control above — the cache is keyed by (full history,
principal), so a hit can never cross a principal boundary, and this function still logs one
`chat_request` line (near-zero `latency_ms`) per call either way, cache hit or miss, so C9 audit
coverage is unaffected.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.features.rag_agent.application.answer_service import AnswerProvider
from app.features.rag_agent.schemas import Answer, ChatMessage, Citation
from app.features.retrieval import update_query_trace_feedback
from app.platform.config import Settings
from app.platform.db.engine import session_scope
from app.platform.logging import get_logger
from app.shared.rate_limiter import SlidingWindowRateLimiter
from app.shared.ttl_cache import TTLCache

log = get_logger("rag_agent.chat")

router = APIRouter(tags=["chat"])

_AUTH_HEADER = "authorization"
_BEARER_PREFIX = "Bearer "
_IDEMPOTENCY_HEADER = "idempotency-key"


class ChatRequestBody(BaseModel):
    """`POST /chat` body. The caller owns conversation state and resends full turn history —
    the server is stateless per request (no server-side conversation store exists)."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = None
    history: list[ChatMessage] = Field(min_length=1)
    principal: str | None = None

    @field_validator("principal")
    @classmethod
    def _reject_numeric_principal(cls, value: str | None) -> str | None:
        """An all-digit `principal` would be read by `PrincipalPermissionPolicy.allowed` as a
        `space_id` and granted space-wide access, bypassing every page-level restriction (PLAN
        5.3 red-team finding — see this module's docstring). No real production principal is a
        bare digit string, so rejecting the shape closes the bypass without touching the shared
        domain policy the eval harness's legitimate numeric space-scoping still depends on."""
        if value is not None and value.isdigit():
            raise ValueError("principal must not be a bare digit string")
        return value


class FeedbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback: Literal[-1, 1]


# -- dependencies (settings read from app.state; answer_service/db overridable in tests via
# app.dependency_overrides or by mutating app.state directly) --------------------------


def get_settings_dep(request: Request) -> Settings:
    """Reads the `Settings` `main.create_app` stored on `app.state` for this app instance — not
    the process-global `get_settings()` cache — so a test's `create_app(settings=...)` call is
    the only override callers need (no `app.dependency_overrides` plumbing, and no cross-feature
    test import: `confluence_sync/tests/test_chat_endpoint.py` reuses this feature's DB fixture
    by construction, not by deep-importing rag_agent's internals)."""
    return request.app.state.settings


def get_answer_service_dep(request: Request) -> AnswerProvider:
    """The singleton `AnswerProvider` built once at app startup (`main.build_answer_service`,
    optionally wrapped in `answer_cache.CachingAnswerService`, PLAN 5)."""
    return request.app.state.answer_service


def get_writer_db() -> Iterator[Session]:
    with session_scope() as session:
        yield session


def _chat_rate_limiter(request: Request, settings: Settings) -> SlidingWindowRateLimiter:
    limiter = getattr(request.app.state, "chat_rate_limiter", None)
    if limiter is None:
        limiter = SlidingWindowRateLimiter(
            settings.chat_rate_limit_per_minute,
            max_tracked_keys=settings.chat_rate_limiter_max_tracked_keys,
        )
        request.app.state.chat_rate_limiter = limiter
    return limiter


def _idempotency_cache(request: Request, settings: Settings) -> TTLCache[str, Answer]:
    cache = getattr(request.app.state, "chat_idempotency_cache", None)
    if cache is None:
        cache = TTLCache[str, Answer](
            settings.chat_idempotency_ttl_seconds,
            max_entries=settings.chat_idempotency_cache_max_entries,
        )
        request.app.state.chat_idempotency_cache = cache
    return cache


def _verify_api_key(request: Request, settings: Settings) -> None:
    configured = settings.chat_api_key
    if not configured:
        # fail closed: an unconfigured secret means the endpoint is not safe to accept
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "chat API key not configured")
    header = request.headers.get(_AUTH_HEADER, "")
    token = header[len(_BEARER_PREFIX) :] if header.startswith(_BEARER_PREFIX) else ""
    # rotation overlap window (PLAN 5): both compares always run (not short-circuited on the
    # first match) so a caller can't distinguish "matched current" from "matched previous" by
    # timing; chat_api_key_previous empty -> compare_digest("", token) is just another mismatch.
    matches_current = bool(token) and hmac.compare_digest(token, configured)
    matches_previous = bool(token) and hmac.compare_digest(token, settings.chat_api_key_previous)
    if not (matches_current or matches_previous):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing API key")


def _rate_limit_key(request: Request) -> str:
    """Client IP only (PLAN 4.6.4 fix). A caller-reported `principal` is untrusted free text — an
    earlier version keyed on it when present, so any caller could defeat the limit outright by
    sending a different `principal` on every request; IP is the one dimension the caller cannot
    freely rotate at will."""
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


def _validate_history(body: ChatRequestBody, settings: Settings) -> None:
    if len(body.history) > settings.chat_max_history_turns:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"history exceeds {settings.chat_max_history_turns} turns",
        )
    for turn in body.history:
        if len(turn.content) > settings.chat_max_message_chars:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"a turn exceeds {settings.chat_max_message_chars} characters",
            )
        # PLAN 7.4 (ADR-0009 decision 7): checked on every turn, not just the newest — the
        # pipeline only ever *analyzes* the newest turn's images (ADR-0009 decision 2), but an
        # unvalidated older turn would still let a caller smuggle an oversized payload through.
        images = turn.images or []
        if len(images) > settings.chat_max_images_per_turn:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"a turn exceeds {settings.chat_max_images_per_turn} images",
            )
        for image in images:
            if len(image.data) > settings.chat_max_image_bytes:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"an image exceeds {settings.chat_max_image_bytes} bytes",
                )
    if body.history[-1].role != "user":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "history must end with a user turn")


def _idempotency_cache_key(
    idempotency_key: str, principal: str | None, history: list[ChatMessage]
) -> str:
    """Binds the caller-supplied `Idempotency-Key` header to a hash of `(principal, history)` so a
    replay of the same header value with a *different* principal or history is never served the
    first caller's cached `Answer` (PLAN 4.6.3 fix — mirrors `answer_cache._cache_key`'s same
    binding, without which the raw header alone was the whole cache key)."""
    turns = [(m.role, m.content) for m in history]
    payload = (
        idempotency_key + "|" + json.dumps(turns, separators=(",", ":")) + "|" + (principal or "")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _wire_citations(citations: list[Citation]) -> list[dict]:
    return [
        {"id": str(c.marker), "pageId": c.page_id, "title": c.title, "url": c.url or ""}
        for c in citations
    ]


async def _stream_answer(
    conversation_id: str,
    body: ChatRequestBody,
    service: AnswerProvider,
    settings: Settings,
    cache: TTLCache[str, Answer],
    idempotency_key: str | None,
) -> AsyncIterator[str]:
    yield _sse({"type": "start", "conversationId": conversation_id})

    cache_key = (
        _idempotency_cache_key(idempotency_key, body.principal, body.history)
        if idempotency_key
        else None
    )
    cached = cache.get(cache_key) if cache_key else None
    if cached is not None:
        answer = cached
        log.info(
            "chat_request_replayed",
            conversation_id=conversation_id,
            trace_id=answer.trace_id,
            idempotency_key=idempotency_key,
        )
    else:
        started = time.perf_counter()
        try:
            answer = service.answer(body.history, body.principal)
        except Exception as exc:  # generation failure surfaces as an SSE error, not a 5xx —
            # the stream already committed to a 200 response by the time this runs.
            log.error("chat_answer_failed", conversation_id=conversation_id, error=str(exc))
            yield _sse({"type": "error", "error": "answer generation failed"})
            return
        latency_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "chat_request",
            conversation_id=conversation_id,
            trace_id=answer.trace_id,
            refused=answer.refused,
            refusal_reason=answer.refusal_reason,
            needs_clarification=answer.needs_clarification,
            citation_count=len(answer.citations),
            latency_ms=latency_ms,
        )
        if cache_key:
            cache.set(cache_key, answer)

    text = answer.text[: settings.chat_output_max_answer_chars]  # C5 defensive size cap
    chunk_size = max(1, settings.chat_token_chunk_chars)
    delay_seconds = settings.chat_stream_interval_ms / 1000
    for i in range(0, len(text), chunk_size):
        yield _sse({"type": "token", "delta": text[i : i + chunk_size]})
        if delay_seconds:
            await asyncio.sleep(delay_seconds)  # C5 pacing: bounds bytes/sec streamed

    wire_citations = _wire_citations(answer.citations)
    # PLAN 7.3 (ADR-0009 decision 5): imageAnalysis rides only on `done`, not as extra `token`
    # events — streaming it as more token deltas would make `done.answer` (the grounded text
    # alone) diverge from what a token-accumulating client sees, a real client/server mismatch.
    # The widget renders it as its own labeled block straight from this field (PLAN 7.5).
    image_analysis = (
        answer.image_analysis[: settings.chat_output_max_answer_chars]  # C5, same cap as `text`
        if answer.image_analysis
        else None
    )
    yield _sse({"type": "citations", "citations": wire_citations})
    yield _sse(
        {
            "type": "done",
            "answer": text,
            "citations": wire_citations,
            "traceId": answer.trace_id,
            "refused": answer.refused,
            "imageAnalysis": image_analysis,
            # PLAN 9.3, ADR-0008 decision 3: additive fields only, no new SSE event type.
            # `needsClarification=False`/`null` on every pre-existing response shape.
            "needsClarification": answer.needs_clarification,
            "clarificationQuestion": answer.clarification_question,
            "clarificationOptions": answer.clarification_options,
        }
    )


@router.post("/chat")
async def post_chat(
    request: Request,
    body: ChatRequestBody,
    settings: Settings = Depends(get_settings_dep),  # noqa: B008 — FastAPI dependency idiom
    service: AnswerProvider = Depends(get_answer_service_dep),  # noqa: B008
) -> StreamingResponse:
    _verify_api_key(request, settings)

    limiter = _chat_rate_limiter(request, settings)
    if not limiter.allow(_rate_limit_key(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limited")

    _validate_history(body, settings)

    conversation_id = body.conversation_id or _new_conversation_id()
    idempotency_key = request.headers.get(_IDEMPOTENCY_HEADER)
    cache = _idempotency_cache(request, settings)

    return StreamingResponse(
        _stream_answer(conversation_id, body, service, settings, cache, idempotency_key),
        media_type="text/event-stream",
    )


@router.patch("/chat/{trace_id}/feedback")
async def patch_chat_feedback(
    trace_id: int,
    body: FeedbackBody,
    request: Request,
    settings: Settings = Depends(get_settings_dep),  # noqa: B008
    session: Session = Depends(get_writer_db),  # noqa: B008
) -> dict:
    _verify_api_key(request, settings)

    limiter = _chat_rate_limiter(request, settings)
    if not limiter.allow(_rate_limit_key(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limited")

    update_query_trace_feedback(session, trace_id, body.feedback)
    log.info("chat_feedback", trace_id=trace_id, feedback=body.feedback)
    return {"ok": True}


def _new_conversation_id() -> str:
    return uuid.uuid4().hex
