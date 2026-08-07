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


class ChatMessage(BaseModel):
    """One turn of conversation history fed to the query rewrite stage."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str


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
    refusal_reason: str | None = None
    trace_id: str | None = None
