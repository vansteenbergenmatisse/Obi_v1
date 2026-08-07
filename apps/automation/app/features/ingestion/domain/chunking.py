"""Token-aware parent/child chunking (pure domain).

Produces two chunk tiers per page, following the plan's sizing and split priority:

* **Parent** chunks group a section's blocks into ~``parent_target`` (hard cap ``parent_max``)
  token spans — the context unit expanded around a matched child at retrieval time.
* **Child** chunks are ~``child_target`` (``child_min``..``child_max``) token windows within a
  single parent, with ``child_overlap_ratio`` overlap — the precise embedding/match unit.

Splitting descends structural boundaries: page -> heading section -> block (table/code kept whole)
-> paragraph -> sentence/word -> token (only an over-long token-less blob is cut mid-word). Each
chunk carries the three keys the incremental diff relies on (ADR-0002 / plan "stable identity"):

* ``section_key``  — identity of the owning section, independent of edits to *other* sections;
* ``positional_key`` — where the chunk sits (section + ordinals), independent of its text;
* ``content_key``  — hash of the chunk's own text.

``stable_key`` combines position + content and is unique per doc version.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.features.ingestion.domain import normalization as norm
from app.features.ingestion.domain.change_detection import section_stable_key
from app.features.ingestion.domain.tokenization import TokenCounter
from app.platform.hashing import sha256_bytes, sha256_text


@dataclass(frozen=True)
class ChunkConfig:
    child_target: int = 400
    child_min: int = 150
    child_max: int = 750
    child_overlap_ratio: float = 0.12
    parent_target: int = 1200
    parent_max: int = 2000


@dataclass
class PlannedChunk:
    """One chunk the indexer will persist. Domain-only: no ORM, no embeddings yet."""

    heading_path: list[str]
    text: str
    tokens: int
    section_key: bytes
    positional_key: bytes
    content_key: bytes
    stable_key: bytes
    location: dict
    ordinal: int


@dataclass
class PlannedParent:
    parent: PlannedChunk
    children: list[PlannedChunk] = field(default_factory=list)


def plan_chunks(
    *,
    page_id: int,
    blocks: list[norm.Block],
    config: ChunkConfig,
    counter: TokenCounter,
) -> list[PlannedParent]:
    """Plan parent+child chunks for a page's normalized blocks. Deterministic."""
    result: list[PlannedParent] = []
    for section in norm.build_sections(blocks):
        units = _section_units(section)
        if not units:
            continue
        sec_key = section_stable_key(page_id, section)
        section_str = ">".join(section.heading_path)
        child_ordinal = 0
        for p_idx, parent_text in enumerate(_pack_parents(units, config, counter)):
            p_content = sha256_text(parent_text)
            parent = PlannedChunk(
                heading_path=list(section.heading_path),
                text=parent_text,
                tokens=counter.count(parent_text),
                section_key=sec_key,
                positional_key=sha256_bytes(sec_key, b"parent", str(p_idx).encode()),
                content_key=p_content,
                stable_key=sha256_bytes(sec_key, b"parent", str(p_idx).encode(), p_content),
                location={"section": section_str, "parent_ordinal": p_idx},
                ordinal=p_idx,
            )
            children: list[PlannedChunk] = []
            for child_text in _split_children(parent_text, config, counter):
                c_content = sha256_text(child_text)
                children.append(
                    PlannedChunk(
                        heading_path=list(section.heading_path),
                        text=child_text,
                        tokens=counter.count(child_text),
                        section_key=sec_key,
                        positional_key=sha256_bytes(
                            sec_key, str(p_idx).encode(), str(child_ordinal).encode()
                        ),
                        content_key=c_content,
                        stable_key=sha256_bytes(
                            sec_key, str(p_idx).encode(), str(child_ordinal).encode(), c_content
                        ),
                        location={
                            "section": section_str,
                            "parent_ordinal": p_idx,
                            "ordinal": child_ordinal,
                        },
                        ordinal=child_ordinal,
                    )
                )
                child_ordinal += 1
            result.append(PlannedParent(parent=parent, children=children))
    return result


def _section_units(section: norm.Section) -> list[str]:
    """A section's atomic text units; a heading-only section contributes its title."""
    units = [b.text for b in section.blocks if b.text]
    if units:
        return units
    title = section.heading_path[-1] if section.heading_path else ""
    return [title] if title else []


def _pack_parents(units: list[str], cfg: ChunkConfig, counter: TokenCounter) -> list[str]:
    """Pack section units into parent spans <= parent_target; an oversize unit is token-split."""
    groups: list[list[str]] = []
    cur: list[str] = []
    for text in units:
        if counter.count(text) > cfg.parent_max:
            if cur:
                groups.append(cur)
                cur = []
            groups.extend([piece] for piece in counter.split(text, max_tokens=cfg.parent_target))
            continue
        if cur and counter.count("\n".join([*cur, text])) > cfg.parent_target:
            groups.append(cur)
            cur = [text]
        else:
            cur.append(text)
    if cur:
        groups.append(cur)
    return ["\n".join(g) for g in groups]


def _split_children(parent_text: str, cfg: ChunkConfig, counter: TokenCounter) -> list[str]:
    """Split a parent span into overlapping child windows; merge a too-small trailing window."""
    if counter.count(parent_text) <= cfg.child_max:
        return [parent_text]
    overlap = int(cfg.child_target * cfg.child_overlap_ratio)
    windows = counter.split(parent_text, max_tokens=cfg.child_target, overlap_tokens=overlap)
    if len(windows) >= 2 and counter.count(windows[-1]) < cfg.child_min:
        windows[-2] = windows[-2] + " " + windows[-1]
        windows.pop()
    return windows
