# Phase 10 — Knowledge-scope tagging (ingestion-side half)

**Status:** §§10.1–10.2 done (2026-08-24); §10.7 (corpus migration) not started. `docs/rag/PLAN.md`
Phase 10 §§10.1–10.2, 10.7. Design doc:
[`docs/adr/0011-Knowledge-Scope-Tagging-And-Retrieval-Filtering.md`](../../adr/0011-Knowledge-Scope-Tagging-And-Retrieval-Filtering.md).
Only the ingestion-relevant sub-steps are covered here — retrieval-time filtering, request threading,
and curated knowledge are in [`../retrieval/phase-10.md`](../retrieval/phase-10.md).

Promotes [`../../future-ideas/IDEAS.md`](../../future-ideas/IDEAS.md) idea #8's "knowledge/RAG
separation" concern, plus the retrieval-side gap idea #2 already flagged from a direct code read:
`page_source.tags`/`chunk.tags` (ADR-0004, [phase-3.5.md](./phase-3.5.md)) have been written at every
ingestion activation since Phase 3.5.3 and read by nothing at query time. This phase adds the missing
**automatic, per-page** tag source; retrieval-side reading of `tags` is Phase 10's other half.

**Terminology note:** this phase calls the concept a "knowledge scope," never a "provider" — see
ADR-0011's Context for why (this repo's own deployment is itself code-named Toast). **Currently
recognized scopes: `general`, `mews`, `opera-cloud`, `toast`** — yes, `toast` is a real recognized
value (Toast POS, a third-party product unrelated to this repo's codename), a deliberate, disclosed
choice, not an oversight.

**Operator: adding a new knowledge scope.**
[`config/knowledge_scopes.json`](../../../config/knowledge_scopes.json) — at the true **repo
root**, not nested under `apps/automation` or `apps/web` — is the single global place this is
decided. A dedicated file, not `.env`, not buried in `settings.py`; living at repo root also
means `apps/web` can read the same file later instead of duplicating the list (e.g. a future
scope-switcher UI, PLAN 10.8). No scope name is hardcoded anywhere else in the codebase
(`resolve_knowledge_scope_tags` below and retrieval's filter both just intersect against
`Settings.knowledge_scope_set`, which loads that JSON file), so recognizing a new provider is one
edit to that file plus labeling the matching Confluence pages — never a code change.

## What's new here

- **`Settings.knowledge_scopes`** (§10.1) — centrally configured, comma-separated recognized scope
  identifiers, always including `general`. Not a DB table — env-driven, matching this repo's existing
  config convention (ADR-0006 decision 2).
- **`confluence_sync/domain/knowledge_scope.py::resolve_knowledge_scope_tags`** (§10.2) — a new pure
  function, same shape as `chunk_diff.diff_chunks`: intersects a page's already-fetched Confluence
  labels (`HttpConfluenceClient.get_labels()`, unchanged, already called on every sync) with the
  recognized set. At most one non-`general` recognized label is valid; two or more is a quarantined
  conflict (zero label-derived tags contributed, `knowledge_scope_conflict` logged, self-heals next
  sync) — never "first wins," never "make it available everywhere."
- **`sync_service.handle_sync_page` wiring** (§10.2) — unions the new label-derived tags with the
  existing `source_scope`-derived tags (unchanged, [phase-3.5.md](./phase-3.5.md)'s 3.5.6) before
  calling the **same, unmodified** `stage_and_activate`/`_apply_metadata_only` seam in
  `ingestion/application/versioning.py`. No change to `versioning.py`'s core logic — both entry points
  already accept and stamp a `tags` list end to end.

## What's explicitly NOT changed here

- `source_scope`'s existing role (which spaces/page-subtrees get synced at all) is unchanged — it
  keeps meaning "sync inclusion," not "knowledge scope." Its tags are unioned in, not replaced.
- ADR-0004's `source_type`/`source_id`/RLS isolation model is untouched — a different axis (data
  connector, e.g. Confluence vs. a future Zendesk), not this phase's concern.
- `versioning.py`'s activation/rollback/GC logic — the `tags` parameter it already accepts is simply
  given a richer value by the caller.

## Corpus migration (§10.7)

The 9 live pages synced this session (2026-08-21, [`PLAN.md`](../PLAN.md) §0) carry only the
`source_scope`-assigned `base` tag — no recognized knowledge-scope label. Before retrieval filtering
(retrieval-side, §10.4) is ever enabled against real content, an operator must add a recognized
Confluence label (at minimum `general`) to each currently-synced page and let a sync pick it up —
otherwise those pages become invisible to every scoped query the moment filtering is enabled, per this
phase's own "no recognized tag → does not participate" rule. This is a disclosed manual step, not
automated by this phase.

## Files & folders used

```
apps/automation/app/platform/config/settings.py                              knowledge_scopes, default_knowledge_scope
apps/automation/app/features/confluence_sync/
├── domain/knowledge_scope.py (new)     resolve_knowledge_scope_tags, KnowledgeScopeResult
├── application/sync_service.py         unions label-derived + source_scope tags at the existing seam
apps/automation/app/features/ingestion/application/versioning.py              unchanged — the seam already accepts `tags`
apps/automation/scripts/seed_curated_knowledge.py (new)                       curated-knowledge CLI (retrieval-side data, ingestion-adjacent tooling)
```

## Not this file

Retrieval-time filtering (§10.4), request-level `knowledge_scope` threading (§10.5), and the
always-present curated-knowledge layer (§10.6) — all retrieval/answer-runtime side, see
[`../retrieval/phase-10.md`](../retrieval/phase-10.md).
