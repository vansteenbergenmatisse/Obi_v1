"""Prompt assembly for the answer workflow (pure).

Three plain string templates — no LLM call, no DB, no clock — so they are trivially testable and
the same rendering drives both the real runtime and its tests:

* ``build_rewrite_prompt`` — multi-turn history -> a request for one standalone question.
* ``build_evidence_block`` — numbered, cited evidence from the *parent* text of each retrieved hit
  (children retrieve, parents ground — PLAN 4.2 stage 3); marker ``n`` is the hit's 1-based
  position, matching the marker ``enforce_citations`` (domain/citations.py) later validates against.
* ``build_answer_prompt`` — the question + evidence block, with the citation instruction repeated
  inline (belt-and-suspenders alongside ``ANSWER_SYSTEM_PROMPT``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from app.features.rag_agent.schemas import ChatMessage

ANSWER_SYSTEM_PROMPT = (
    "You are a support assistant that answers ONLY from the numbered evidence blocks provided. "
    "Cite every factual claim with its matching numbered marker, e.g. [1], [2] — an uncited claim "
    "is discarded before the user sees it, and a marker not present in the evidence is invalid. "
    "If the evidence does not answer the question, say so plainly instead of guessing."
)


def build_rewrite_prompt(history: Sequence[ChatMessage]) -> str:
    """Ask for one standalone question resolving pronouns/references from the prior turns."""
    turns = "\n".join(f"{m.role}: {m.content}" for m in history)
    return (
        "Rewrite the final user message below into one standalone question that makes sense "
        "without the earlier turns — resolve pronouns and implicit references from the "
        "conversation. Reply with only the rewritten question, no preamble.\n\n" + turns
    )


class _EvidenceHit(Protocol):
    """Structural shape this module needs from a hit — decouples it from `retrieval`'s internals.

    Declared as read-only properties (not plain attributes) so a frozen dataclass like
    `RetrievedHit` structurally satisfies it — Protocol attribute annotations default to
    read-write, which a frozen dataclass's read-only fields do not match.
    """

    @property
    def chunk_id(self) -> int: ...

    @property
    def title(self) -> str: ...


def build_evidence_block(hits: Sequence[_EvidenceHit], parent_texts: Mapping[int, str]) -> str:
    """Render ``[1] <title>\n<parent text>`` blocks in hit order."""
    blocks = []
    for marker, hit in enumerate(hits, start=1):
        body = parent_texts.get(hit.chunk_id, "")
        blocks.append(f"[{marker}] {hit.title}\n{body}".rstrip())
    return "\n\n".join(blocks)


def build_answer_prompt(query: str, evidence_block: str) -> str:
    return (
        f"Question: {query}\n\n"
        f"Evidence:\n{evidence_block}\n\n"
        "Answer the question using only the evidence above. Cite every claim with its marker "
        "(e.g. [1]); never cite a marker not shown above."
    )
