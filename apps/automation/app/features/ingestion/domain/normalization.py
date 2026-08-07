"""Deterministic normalization of Confluence storage-format bodies into structural blocks.

Phase 2 uses this to compute stable content/structure/section hashes for change detection.
Phase 3 reuses the same block tree for token-aware chunking, so the representation is designed
to preserve H1-H6 hierarchy, paragraphs, lists, tables, code and panels rather than flatten them.

The parser is intentionally dependency-light (stdlib ``html.parser``) and lenient: Confluence
storage format is XHTML-ish with ``ac:``/``ri:`` macro tags. We keep meaning, drop volatile
presentation attributes, and never raise on unknown tags.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from app.platform.hashing import normalize_text, sha256_text

HEADING_TAGS = {f"h{i}": i for i in range(1, 7)}
_BLOCK_BREAK = {"p", "li", "tr", "br", "pre", "table", "ul", "ol"}


@dataclass
class Block:
    """One normalized content block under its nearest heading."""

    kind: str  # heading | paragraph | list | table | code | panel | other
    level: int  # heading level for kind==heading, else 0
    text: str  # normalized text content
    heading_path: list[str] = field(default_factory=list)

    def content_hash(self) -> bytes:
        return sha256_text(self.kind, str(self.level), self.text)


@dataclass
class Section:
    """A heading and its following blocks up to the next equal-or-higher heading."""

    heading_path: list[str]
    level: int
    sibling_ordinal: int  # disambiguates duplicate heading texts at the same path
    blocks: list[Block] = field(default_factory=list)

    def content_text(self) -> str:
        return "\n".join(b.text for b in self.blocks if b.text)


class _StorageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._buf: list[str] = []
        self._tag_stack: list[str] = []
        self._cur_kind = "paragraph"
        self._macro_name: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._tag_stack.append(tag)
        if tag in HEADING_TAGS:
            self._flush()
            self._cur_kind = "heading"
        elif tag in ("ul", "ol"):
            self._flush()
            self._cur_kind = "list"
        elif tag == "table":
            self._flush()
            self._cur_kind = "table"
        elif tag == "ac:structured-macro":
            name = dict(attrs).get("ac:name", "")
            self._macro_name = name
            if name == "code":
                self._flush()
                self._cur_kind = "code"
            elif name in ("info", "note", "warning", "tip", "panel"):
                self._flush()
                self._cur_kind = "panel"

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in HEADING_TAGS:
            self._flush(level=HEADING_TAGS[tag])
            self._cur_kind = "paragraph"
        elif tag in ("ul", "ol", "table"):
            self._flush()
            self._cur_kind = "paragraph"
        elif tag == "ac:structured-macro":
            self._flush()
            self._cur_kind = "paragraph"
            self._macro_name = None
        elif tag == "p":
            self._flush()
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._buf.append(data)
        elif self._buf:
            self._buf.append(" ")

    def _flush(self, level: int = 0) -> None:
        text = normalize_text(" ".join(self._buf))
        self._buf.clear()
        if not text:
            return
        kind = self._cur_kind if self._cur_kind != "heading" or level else self._cur_kind
        self.blocks.append(Block(kind=kind, level=level, text=text))
        self._cur_kind = "paragraph"

    def finish(self) -> list[Block]:
        self._flush()
        return self.blocks


_TAG_RE = re.compile(r"<[^>]+>")


def normalize_body(storage_html: str) -> list[Block]:
    """Parse Confluence storage HTML into an ordered list of normalized blocks."""
    if not storage_html:
        return []
    parser = _StorageParser()
    try:
        parser.feed(storage_html)
        blocks = parser.finish()
    except Exception:
        # Lenient fallback: strip tags, treat as one paragraph.
        text = normalize_text(_TAG_RE.sub(" ", storage_html))
        blocks = [Block(kind="paragraph", level=0, text=text)] if text else []
    return _attach_heading_paths(blocks)


def _attach_heading_paths(blocks: list[Block]) -> list[Block]:
    stack: list[tuple[int, str]] = []  # (level, text)
    for b in blocks:
        if b.kind == "heading" and b.level:
            while stack and stack[-1][0] >= b.level:
                stack.pop()
            stack.append((b.level, b.text))
            b.heading_path = [t for _, t in stack]
        else:
            b.heading_path = [t for _, t in stack]
    return blocks


def build_sections(blocks: list[Block]) -> list[Section]:
    """Group blocks into sections keyed by heading path; number duplicate paths."""
    sections: list[Section] = []
    seen_paths: dict[str, int] = {}
    current: Section | None = None
    for b in blocks:
        if b.kind == "heading" and b.level:
            path_key = ">".join(b.heading_path)
            ordinal = seen_paths.get(path_key, 0)
            seen_paths[path_key] = ordinal + 1
            current = Section(
                heading_path=list(b.heading_path),
                level=b.level,
                sibling_ordinal=ordinal,
            )
            sections.append(current)
        else:
            if current is None:
                current = Section(heading_path=[], level=0, sibling_ordinal=0)
                sections.append(current)
            current.blocks.append(b)
    return sections


def content_hash(blocks: list[Block]) -> bytes:
    """Hash of all normalized text (order-sensitive)."""
    return sha256_text(*[f"{b.kind}:{b.level}:{b.text}" for b in blocks])


def structure_hash(blocks: list[Block]) -> bytes:
    """Hash of the heading tree + block types/order, ignoring body text."""
    skeleton = [f"{b.kind}:{b.level}:{'>'.join(b.heading_path)}" for b in blocks]
    return sha256_text(*skeleton)
