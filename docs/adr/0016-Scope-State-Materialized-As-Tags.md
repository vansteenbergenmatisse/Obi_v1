# 0016 — Scope State Materialized as Tags (No Separate Column)

Status: Accepted
Date: 2026-09-18
Governs: apps/automation (platform/db, ingestion, retrieval)

> **Retroactive ADR.** This records a decision already shipped and covered by tests; it
> documents existing behavior, it does not change it. Written to close a documentation gap
> (cm-docs). It narrows and complements ADR-0011, which governs how labels drive scope
> tagging and retrieval filtering; this ADR records the *schema* decision underneath it.

## Context

The design page speaks of a page's **`scope_state`** — the knowledge-scope facet of a page
and its chunks. A reader could reasonably expect a dedicated `scope_state` column. It does
not exist, and it must not be reintroduced, because a second surface for the same fact would
be a source of drift (two places to keep in sync, two places to filter on).

## Decision

1. **There is no `scope_state` column.** The knowledge-scope state is materialized as
   `tags` — a `ARRAY(Text)`, `NOT NULL`, default `'{}'` — on both `page_source` and
   `chunk`, and likewise on `source_scope` and `curated_knowledge_entry`
   (`apps/automation/app/platform/db/models.py`: PageSource.tags 109-111, Chunk.tags
   288-290, SourceScope.tags 503-505, CuratedKnowledgeEntry.tags 574-576).

2. **`chunk.tags` is the retrieval hot path** and is GIN-indexed (`ix_chunk_tags_gin`,
   models.py:345-351) for `tags && ARRAY[...]` membership tests under the knowledge-scope
   filter (ADR-0011).

3. **Change-detection state stays on its own columns**, distinct from `tags`:
   `content_hash`, `structure_hash`, `attachment_manifest_hash`, `access_scope_hash`,
   `labels_hash` on `page_source` (models.py:127-131), and `access_scope` on `chunk`
   (models.py:313). "Scope state" (tags) and "the fingerprints that detect changes to it"
   (ADR-0015) are different concerns on different columns.

## Reason / Consequences

- One surface for scope means one place to write it (ingestion) and one place to filter on
  it (retrieval): `chunk.tags`. No column can silently disagree with another.
- The name `scope_state` on the design page and the column `tags` in the schema are the same
  fact under two names; asserting `row.tags` proves both at once.
- Any future work must not add a `scope_state` column; extend `tags` semantics instead, or
  amend this ADR.

Cross-references: ADR-0011 (label-driven knowledge-scope tagging and retrieval filtering),
ADR-0015 (change-detection fingerprints — the separate hash columns).

Tests: `test_scope_tagging_retag.py` (module docstring: "'scope_state' is this same
tags/labels state … there is no separate `scope_state` column in the schema"),
`test_vector_data_column.py` (`test_vd_column_embedding_colocated_with_tags_and_tsv_on_same_row`,
asserting `row.tags` "== scope_state, no separate column").
