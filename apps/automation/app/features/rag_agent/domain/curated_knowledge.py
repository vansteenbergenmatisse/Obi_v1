"""Curated-knowledge domain shapes (PLAN 10.6, ADR-0011): hand-authored entries always eligible
for citation, independent of any retrieved Confluence chunk.

Pure data plus the adapter that lets a `CuratedEntry` ride through the exact same evidence/citation
machinery a real retrieved hit already uses (`prompt.py::build_evidence_block`'s `_EvidenceHit`
protocol, `answer_service.py`'s `Citation` construction) — no I/O here, matching every other module
in this package (`citations.py`, `clarification.py`, `refusal.py`, `small_talk.py`, `prompt.py`).
`infrastructure/curated_knowledge_repo.py` owns the actual query, mirroring `retrieval`'s own
domain/infrastructure split for the identical problem (PLAN 10.4's `knowledge_scope.py` vs.
`search_repo.py`) — a deliberate correction of this sub-step's plan text, which named a single
`domain/curated_knowledge.py` file for both the pure shapes and the session-taking query function;
every other `domain/` module in this repo is I/O-free, so the query moved out rather than becoming
the one exception.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CuratedEntry:
    """One `curated_knowledge_entry` row, decoupled from the ORM (mirrors `RetrievedHit`'s role
    for retrieval). Empty `tags` means "applies to every scope" (matches the table's own semantics,
    PLAN 10.3)."""

    id: int
    tags: tuple[str, ...]
    title: str
    body: str


@dataclass(frozen=True)
class CuratedHit:
    """Adapts a `CuratedEntry` to the same shape `AnswerService` already builds a `Citation` from
    (`page_id`/`chunk_id`/`title`/`url`) and structurally satisfies `prompt.py`'s `_EvidenceHit`
    protocol (`chunk_id`/`title`).

    `chunk_id` is negative and `page_id` is namespaced `curated:<id>` so neither can ever collide
    with a real retrieved chunk/page id (real chunk ids are positive serial PKs) — a curated
    citation is never confused with a live Confluence page link at the data level. `url` stays
    empty; `packages/contracts`' `Citation.url` already documents empty as "unavailable if not
    known" (10.6 deliberately does not invent a distinct "Source: curated knowledge" display
    treatment here — that is a UI/contract decision the plan itself flags as out of scope for this
    backend-only sub-step; a future sub-step wires it once the widget side is designed)."""

    page_id: str
    chunk_id: int
    title: str
    url: str = ""


def curated_entry_to_hit(entry: CuratedEntry) -> CuratedHit:
    return CuratedHit(page_id=f"curated:{entry.id}", chunk_id=-entry.id, title=entry.title)
