"""Public DTOs for the answer runtime (Pydantic v2).

These are the types that cross the `rag_agent` boundary: the conversation turns the
caller sends in, and the grounded `Answer` the runtime returns. They carry no behaviour
and read no clock — the trace id and any timestamps are supplied by the caller, so the
contract stays deterministic and serialisable straight onto the `POST /chat` surface.

The answer workflow itself (rewrite → retrieve → rerank → ground → refuse → CRAG) lands
in Phase 4.2; this module is the stable shape that workflow fills in.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.features.rag_agent.domain.refusal import RefusalReason


class ImageAttachment(BaseModel):
    """One inline image attached to a chat turn (PLAN 7.2/7.3, ADR-0009). ``data`` is
    base64-encoded, no data URI prefix. Field name uses the wire's camelCase (``mediaType``) via
    alias — `apps/web`'s proxy passes turn content straight through without renaming nested
    fields (unlike ``conversationId`` -> ``conversation_id``, which it does translate), so this
    model must accept the same casing `packages/contracts`' ``ImageAttachment`` sends.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    media_type: str = Field(alias="mediaType")
    data: str


class ChatMessage(BaseModel):
    """One turn of conversation history fed to the query rewrite stage."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str
    images: list[ImageAttachment] | None = Field(
        default=None,
        description=(
            "Images attached to this turn (ADR-0009). By convention only the newest turn ever "
            "carries these (decision 2) — AnswerService.answer only reads history[-1].images; "
            "an older turn's images is accepted, not rejected, but never analyzed."
        ),
    )


class Citation(BaseModel):
    """A numbered source marker (`[marker]`) pointing at one retrieved page."""

    model_config = ConfigDict(extra="forbid")

    marker: int = Field(ge=1)
    page_id: str
    title: str
    url: str | None = None


class Answer(BaseModel):
    """The grounded result the runtime returns.

    On refusal, ``refused`` is true, ``text`` is the caller-facing refusal message, and
    ``citations`` is empty. Otherwise ``text`` is the citation-enforced answer (every
    surviving claim cites a marker in ``citations``). ``trace_id`` links back to the
    ``query_trace`` row so feedback can update it.
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False
    refusal_reason: RefusalReason | None = Field(
        default=None,
        description=(
            "One of the closed taxonomy `no_candidates | weak_score | no_citations` (PLAN 9.4, "
            "ADR-0008 decision 4) — never a free-text diagnostic. Not sent over the `/chat` SSE "
            "wire today; surfaced here so callers (and the `chat_request` audit log line) have a "
            "stable, groupable category rather than the interpolated-score string this used to be."
        ),
    )
    trace_id: str | None = None
    image_analysis: str | None = Field(
        default=None,
        description=(
            "Vision-analysis text for any images on the turn (ADR-0009 decision 4/5), from a "
            "second, independent generation call that never enters citation enforcement. Kept "
            "separate from `text` on purpose, not appended into it, so the widget can render it "
            "as its own labeled block (decision 5)."
        ),
    )
    needs_clarification: bool = Field(
        default=False,
        description=(
            "True when the query was judged too vague to search well (PLAN 9.3, ADR-0008 "
            "decision 3) and the pipeline bypassed rewrite/retrieval/refusal to ask a clarifying "
            "question instead. A still-open conversation turn, not a refusal — `refused` stays "
            "False on this path."
        ),
    )
    clarification_question: str | None = Field(
        default=None,
        description=(
            "The clarifying question, identical to `text` on this path (ADR-0008 decision 3) — "
            "present as its own field so a client can distinguish a clarification turn without "
            "string-matching `text`."
        ),
    )
    clarification_options: list[str] | None = Field(
        default=None,
        description=(
            "2-4 concrete options the clarifying question offers, for a client to render as "
            "quick-reply chips (PLAN 9.5). Absent/null when the turn is not a clarification turn."
        ),
    )
