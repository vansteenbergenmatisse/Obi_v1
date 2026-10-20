"""Resolve a page's Confluence labels into knowledge-scope tags (PLAN 10.2, ADR-knowledge-scope-tagging-and-filtering).

Pure, no I/O: takes the labels already fetched by the caller (`gateway.get_labels`) and the
recognized set from `Settings.knowledge_scope_set` (PLAN 10.1). Every recognized label becomes a
tag. Two or more recognized provider labels on one page is *legitimate sharing* (decision D4): the
page belongs to each of those knowledge scopes at once, and is later made visible in each by plain
overlap (`chunk.tags && allowed_scopes`). There is no conflict concept — the caller unions the
matched tags with the page's existing `source_scope` tags.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeScopeResult:
    tags: tuple[str, ...]
    matched_labels: tuple[str, ...]


def resolve_knowledge_scope_tags(
    labels: Sequence[str], recognized: frozenset[str]
) -> KnowledgeScopeResult:
    matched = tuple(sorted({label.strip().lower() for label in labels} & recognized))
    return KnowledgeScopeResult(tags=matched, matched_labels=matched)
