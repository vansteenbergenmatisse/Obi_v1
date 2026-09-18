# 0016 — Scope State Materialized as Tags (No Separate Column)

Status: Accepted
Date: 2026-09-18
Governs: apps/automation (platform/db, ingestion, retrieval)

> **Retroactive ADR.** This records behavior already shipped and covered by tests; it
> documents existing behavior, it does not change it. Written to close a documentation gap
> (cm-docs). It relates to ADR-0011, which governs how labels drive scope tagging and retrieval
> filtering; this ADR records the *schema* shape underneath it.

> **Caveat — open code-vs-design reconciliation (added 2026-09-18).** The design page targets a
> richer model than this ADR records: its schema section defines `CREATE TYPE scope_state AS ENUM
> ('ok','conflict','classified','unlabeled')`, and panels `i2-labels` / `i2-gone` / `tg-classified`
> describe writing that state and acting on it. **None of that enum, a `scope_state` column, or those
> four state values exist in the code** (verified by grep) — the shipped code materializes only the
> tag set (plus a transient conflict flag). No prior ADR, including ADR-0011, ratified using `tags`
> *instead of* the enum, so this ADR documents an as-yet-**unratified divergence**, not a settled
> superseding decision. It is the same code-vs-design delta as the (deliberately unwritten)
> label-gated-ingestion ADR — logged in `docs/plan/delta.md` and tracked decision-needed in
> `docs/plan/decisions.md` (`live-0.5.3-cm-docs`). Read the "Decision" below as a *description of
> shipped behavior*, pending the owner's call to either build the enum model or amend the design page
> + never-bend rule #5.

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
