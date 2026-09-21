"""Fallback and faithfulness signal metrics (PLAN 9.7, ADR-0008 decision 7).

Both are lightweight proxies, not an LLM-judge — that would need a live model call this DB-free
harness deliberately avoids (matching every other metric here). ``fallback_rate`` counts how often
the pipeline diverted away from a grounded answer (refused or asked for clarification) instead of
answering; ``citation_grounding_rate`` is a cheap faithfulness/hallucination-rate proxy — the
fraction of an answer's cited ids that fall within the eval case's own labelled-relevant set. It
does not check the generated text against the evidence word-for-word (that needs a judge), only
that every citation the model emitted points to a source the case's ground truth calls relevant,
catching a citation that leans on an off-topic chunk that merely rode along in the evidence block.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def fallback_rate(fell_back: Sequence[bool]) -> float:
    """Fraction of cases where the pipeline fell back (refused or needs_clarification) instead of
    returning a grounded answer. Returns 0.0 for an empty sequence (nothing measured, not
    undefined) — same convention as the retrieval metrics' empty-relevant-set case."""
    if not fell_back:
        return 0.0
    return sum(1 for case in fell_back if case) / len(fell_back)


def citation_grounding_rate(cited_ids: Iterable[str], relevant_ids: Iterable[str]) -> float:
    """Fraction of ``cited_ids`` that are within ``relevant_ids``. Returns 0.0 when nothing was
    cited (nothing to be faithful about, not vacuously "fully grounded")."""
    cited = list(cited_ids)
    if not cited:
        return 0.0
    relevant = set(relevant_ids)
    hits = sum(1 for cid in cited if cid in relevant)
    return hits / len(cited)


__all__ = ["fallback_rate", "citation_grounding_rate"]
