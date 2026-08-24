# Phase 10 — Knowledge-scope tagging (ingestion-side half)

**Status:** §§10.1–10.2 done and committed (2026-08-24 — 10.1 `ad29f1b` config, later superseded by
`18ee219` moving the recognized-scope list to `config/knowledge_scopes.json`; 10.2 `9fb134f`
label-driven tags). §10.7's tooling half is built: the corpus-readiness check
(`verify_knowledge_scope_coverage` + `scripts/verify_knowledge_scope_backfill.py`) is implemented and
tested; the manual relabel of the live corpus and the flag flip remain an operator action.
`docs/rag/PLAN.md` Phase 10 §§10.1–10.2, 10.7. Design doc:
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

- **Recognized-scope configuration** (§10.1, superseded by `18ee219`) — the recognized set (always
  including `general`) lives in `config/knowledge_scopes.json` at the repo root, loaded by
  `platform/config/knowledge_scopes.py::load_recognized_knowledge_scopes` and exposed as
  `Settings.knowledge_scope_set`. Not a DB table, and deliberately not `.env` — a dedicated global
  file (see the operator note above). Process construction fails fast if `general` is missing.
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
phase's own "no recognized tag → does not participate" rule. Deciding *which* scope each page belongs
to is a content decision, so it stays manual; nothing in code guesses it. **This manual step is the
single highest-risk point for the `toast`/`mews`-vs-`Muse` naming collisions** (ADR-0011 Context) — the
operator typing a label is the one place no code catches "did you mean the POS platform or this repo's
codename?", so relabeling should be done with ADR-0011's Context open.

**The readiness gate** (built here, §10.7) makes the "did every page get labeled?" question
mechanical instead of eyeballed:

- **`confluence_sync/application/knowledge_scope_backfill.py::verify_knowledge_scope_coverage`** —
  read-only, counts every `is_active` chunk whose `tags` overlap **none** of the recognized scopes
  (the same bound `tags && :param` overlap predicate as retrieval's §10.4 filter, never a literal
  `ARRAY[...]`), grouped by `page_id`. Returns a `KnowledgeScopeCoverage` (`total_active_chunks`,
  `untagged_active_chunks`, `untagged_page_ids`, `is_ready`). Counts **all** active chunks, parents
  and children, and only active ones — retrieval reads only `is_active` rows and superseded rows are
  GC'd, so no historical backfill is needed. Exported from the feature's public root.
- **`scripts/verify_knowledge_scope_backfill.py`** — a thin CLI over that function (mirrors
  `seed_source_scope.py`'s one-off ownership). Loads the recognized set from
  `config/knowledge_scopes.json`, prints the coverage (and, when not ready, the offending
  `page_id`s so the operator knows which Confluence pages still need a label), and **exits non-zero
  until the corpus is fully labeled** — the machine gate that must pass before
  `ENABLE_KNOWLEDGE_SCOPE_FILTERING=true` is set in any environment with real content. It never
  flips the flag itself; that stays a deliberate `.env` change.
- **`scripts/run_reconciliation_once.py`** — the one-off that actually propagates the operator's new
  labels into `chunk.tags`. Builds the **live** `HttpConfluenceClient` (refuses the offline fixture
  gateway), runs a *complete* `run_reconciliation` (enqueues one `sync_page` per live page), then
  `drain()`s the queue. Each job's `handle_sync_page` re-reads the fresh labels and re-stamps tags
  via the **metadata-only path — no re-embedding** (a label change bumps `labels_hash`, not the body,
  so `classify` never routes it to a rebuild). It is the manual equivalent of the scheduled
  `scheduled_complete_reconcile` + `worker_tick`; it never flips the flag.

**Status (2026-08-24): 10.7 complete.** The operator labeled all 9 live pages `general` in Confluence,
`run_reconciliation_once.py` propagated it (9 pages swept, 9 `sync_page` jobs drained `metadata_only`),
the verify gate reported **READY** (85 active chunks, 0 untagged — every active chunk and `page_source`
row carries `['base', 'general']`), and `ENABLE_KNOWLEDGE_SCOPE_FILTERING` was then flipped **`true`**.
Live scoped retrieval was confirmed end-to-end after the flip (a `general`/`mews` request returns
grounded hits; a `mews`-only filter returns none — the predicate genuinely excludes). See
[`PLAN.md`](../PLAN.md) §0 and [`retrieval/phase-10.md`](../retrieval/phase-10.md).

## Files & folders used

```
apps/automation/app/platform/config/settings.py                              knowledge_scopes, default_knowledge_scope
apps/automation/app/features/confluence_sync/
├── domain/knowledge_scope.py (new)     resolve_knowledge_scope_tags, KnowledgeScopeResult
├── application/sync_service.py         unions label-derived + source_scope tags at the existing seam
├── application/knowledge_scope_backfill.py (new, §10.7)   verify_knowledge_scope_coverage — the pre-flip readiness check
├── __init__.py (§10.7)                 exports verify_knowledge_scope_coverage, KnowledgeScopeCoverage
├── tests/test_knowledge_scope_backfill.py (new, §10.7)    real-DB: untagged/source-scope-only/inactive/partial coverage
apps/automation/app/features/ingestion/application/versioning.py              unchanged — the seam already accepts `tags`
apps/automation/scripts/verify_knowledge_scope_backfill.py (new, §10.7)       readiness-gate CLI; exit 0 = ready to flip the filter flag
apps/automation/scripts/run_reconciliation_once.py (new, §10.7)               one-off live complete sweep + drain; re-stamps tags metadata-only, never flips the flag
apps/automation/scripts/seed_curated_knowledge.py (new)                       curated-knowledge CLI (retrieval-side data, ingestion-adjacent tooling)
```

## Not this file

Retrieval-time filtering (§10.4), request-level `knowledge_scope` threading (§10.5), and the
always-present curated-knowledge layer (§10.6) — all retrieval/answer-runtime side, see
[`../retrieval/phase-10.md`](../retrieval/phase-10.md).
