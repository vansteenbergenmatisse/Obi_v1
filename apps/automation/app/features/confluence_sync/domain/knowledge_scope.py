"""Resolve a page's Confluence labels into knowledge-scope tags (PLAN 10.2, ADR-0011).

Pure, no I/O: takes the labels already fetched by the caller (`gateway.get_labels`) and the
recognized set from `Settings.knowledge_scope_set` (PLAN 10.1). Two or more *provider* labels
(anything other than ``general``) on the same page is a conflict — a page can only live in one
provider's knowledge scope — so it contributes zero label-derived tags until an operator fixes
the Confluence labels; the caller unions the (possibly empty) result with the page's existing
`source_scope` tags rather than replacing them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeScopeResult:
    tags: tuple[str, ...]
    conflict: bool
    matched_labels: tuple[str, ...]


def resolve_knowledge_scope_tags(
    labels: Sequence[str], recognized: frozenset[str]
) -> KnowledgeScopeResult:
    matched = tuple(sorted({label.strip().lower() for label in labels} & recognized))
    provider_tags = tuple(tag for tag in matched if tag != "general")
    if len(provider_tags) > 1:
        return KnowledgeScopeResult(tags=(), conflict=True, matched_labels=matched)
    return KnowledgeScopeResult(tags=matched, conflict=False, matched_labels=matched)
