"""Citation enforcement (pure): strip uncited claims before an answer is returned.

Groundedness is enforced in code, not merely prompted (ADR-0005 §6). The generator is
told to cite every claim with a numbered marker (``[1]``, ``[2]``, …) that indexes a
retrieved page. This pass is the enforcement:

* a sentence survives only if it cites **at least one valid marker**;
* a marker pointing at a page that was not retrieved is dropped (a hallucinated source),
  and if that leaves the sentence with no valid citation, the whole sentence is stripped.

The unit of a "claim" is a sentence — coarse but predictable, and it keeps the answer
readable. Returns the cleaned text and the sorted markers actually used (so the caller
can build the citation list from exactly the sources that survived).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_MARKER_RE = re.compile(r"\[(\d+)\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.!?,;:])")
_MULTISPACE_RE = re.compile(r"\s{2,}")


def enforce_citations(answer_text: str, valid_markers: Iterable[int]) -> tuple[str, list[int]]:
    """Strip uncited / mis-cited claims.

    ``valid_markers`` are the marker numbers backed by a real retrieved page. A sentence
    is kept iff it cites one of them; invalid markers inside a kept sentence are removed.
    """
    valid = {int(m) for m in valid_markers}
    used: set[int] = set()
    kept: list[str] = []
    for sentence in _split_sentences(answer_text):
        cited = {int(m) for m in _MARKER_RE.findall(sentence)}
        cited_valid = cited & valid
        if not cited_valid:
            continue  # uncited, or only cites pages that were never retrieved
        used |= cited_valid
        kept.append(_drop_invalid_markers(sentence, valid))
    return " ".join(kept).strip(), sorted(used)


def _split_sentences(text: str) -> list[str]:
    return [s for s in (part.strip() for part in _SENTENCE_SPLIT_RE.split(text)) if s]


def _drop_invalid_markers(sentence: str, valid: set[int]) -> str:
    def repl(match: re.Match[str]) -> str:
        return match.group(0) if int(match.group(1)) in valid else ""

    cleaned = _MARKER_RE.sub(repl, sentence)
    cleaned = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", cleaned)
    return _MULTISPACE_RE.sub(" ", cleaned).strip()
