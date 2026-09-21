"""Incremental chunk diff for embedding reuse (pure domain).

Given the previously-indexed child chunks and the freshly planned ones, decide which embeddings
can be carried over untouched and which chunks must be (re-)embedded — the mechanism that keeps a
small edit from re-embedding the whole page (plan "stable identity + diff", ADR-0002).

Three passes, each consuming from the pool of not-yet-matched old chunks:

1. **exact** — same ``stable_key`` (position *and* content identical) → reuse embedding.
2. **moved** — same ``content_key`` at a different position → content is byte-identical, so the
   embedding is still valid → reuse.
3. **edited-in-slot** — same ``positional_key`` but different content → must re-embed (the old
   chunk is consumed, not deleted).

New chunks matched by none are inserts (re-embed); old chunks matched by none are deletes.
Inputs need only ``stable_key`` / ``positional_key`` / ``content_key`` attributes, so both planned
chunks and persisted ORM rows can be passed directly.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


class HasKeys(Protocol):
    stable_key: bytes
    positional_key: bytes
    content_key: bytes


@dataclass(frozen=True)
class ReuseMatch:
    new_index: int
    old_index: int
    reason: str  # "exact" | "moved"


@dataclass
class ChunkDiff:
    reuse: list[ReuseMatch] = field(default_factory=list)
    reembed_indexes: list[int] = field(default_factory=list)
    delete_old_indexes: list[int] = field(default_factory=list)

    @property
    def reuse_count(self) -> int:
        return len(self.reuse)

    @property
    def reembed_count(self) -> int:
        return len(self.reembed_indexes)


def diff_chunks(old: Sequence[HasKeys], new: Sequence[HasKeys]) -> ChunkDiff:
    remaining: set[int] = set(range(len(old)))
    matched_new: set[int] = set()
    diff = ChunkDiff()

    def pool(key: str) -> dict[bytes, deque[int]]:
        d: dict[bytes, deque[int]] = defaultdict(deque)
        for idx in sorted(remaining):
            d[getattr(old[idx], key)].append(idx)
        return d

    def take(dq: deque[int] | None) -> int | None:
        while dq:
            idx = dq.popleft()
            if idx in remaining:
                return idx
        return None

    # pass 1 — exact (position + content)
    exact = pool("stable_key")
    for i, c in enumerate(new):
        oi = take(exact.get(c.stable_key))
        if oi is not None:
            diff.reuse.append(ReuseMatch(i, oi, "exact"))
            remaining.discard(oi)
            matched_new.add(i)

    # pass 2 — moved (content identical, position changed)
    moved = pool("content_key")
    for i, c in enumerate(new):
        if i in matched_new:
            continue
        oi = take(moved.get(c.content_key))
        if oi is not None:
            diff.reuse.append(ReuseMatch(i, oi, "moved"))
            remaining.discard(oi)
            matched_new.add(i)

    # pass 3 — edited in slot (same position, content changed) → re-embed, consume the old chunk
    edited = pool("positional_key")
    for i, c in enumerate(new):
        if i in matched_new:
            continue
        oi = take(edited.get(c.positional_key))
        if oi is not None:
            diff.reembed_indexes.append(i)
            remaining.discard(oi)
            matched_new.add(i)

    # inserts — unmatched new chunks
    for i in range(len(new)):
        if i not in matched_new:
            diff.reembed_indexes.append(i)
    diff.reembed_indexes.sort()

    # deletes — unmatched old chunks
    diff.delete_old_indexes = sorted(remaining)
    return diff
