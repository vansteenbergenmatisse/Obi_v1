# Phase 3.5 — Accuracy + tagging spine (ingestion-relevant sub-steps only)

**Status:** ✅ done. Phase 3.5 had six sub-steps (`PLAN.md` lines 1869–2069); only two touch
ingestion. **3.5.1** (pin pgvector ≥0.8 + HNSW iterative-scan), **3.5.2** (cross-encoder reranker),
**3.5.4** (`query_trace` scoreboard), and **3.5.5** (measure rerank lift) are entirely retrieval-
side — see `../retrieval/phase-3.5.md`.

## Files & folders used

```
apps/automation/app/features/ingestion/application/versioning.py    the single provider-tag stamp
apps/automation/app/features/confluence_sync/
├── domain/scope_resolver.py           resolve_scope_roots, resolve_space_scope
├── application/reconciliation.py      space discovery + per-space sweep, wired to scope
apps/automation/app/platform/db/models.py                            SourceScope table, page_source/chunk tag columns
apps/automation/scripts/seed_source_scope.py                         one-off CLI to seed roots
apps/automation/alembic/versions/0004_source_scope.py                the migration
```

## 3.5.3 — Provider tagging (the writer-side half)

`PLAN.md` lines 1942–2018 (ADR-0004 territory, see [phase-0.md](./phase-0.md)). Schema: three
columns on `page_source` and `chunk` only (never `document_version`, which retrieval never reads)
— `source_type` (CHECK constraint, not a PG enum), `source_id` (the isolation key, e.g.
`confluence:default`), `tags` (free-form array).

**Ingestion's entire responsibility here is one seam.** `ingestion/application/versioning.py`
stamps the constants at both write sites:

- `build_chunks`'s `common` dict (`versioning.py:82-100`): `source_type=_SOURCE_TYPE`,
  `source_id=_SOURCE_ID`, `tags=list(tags) if tags is not None else []` on every parent/child chunk.
- `_activate` (`versioning.py:352-354`): the same three fields on `page_source`.

`_SOURCE_TYPE = "confluence"` / `_SOURCE_ID = "confluence:default"` (`versioning.py:36-37`) are
constants today — comments at both write sites note this becomes a parameter threaded from the
caller once a second source type exists. Nothing else in ingestion needs to know about isolation;
the RLS policy, the reader-role GUC binding, and the negative-isolation tests are all retrieval-
side (`../retrieval/phase-3.5.md`).

The **writer** is what every ingestion write already runs as — worker, webhook, reconcile, and this
activation point are untouched by RLS by design (ADR-0004 decision 4). Originally the writer escaped
RLS by being a superuser locally; **ADR-0013 (Phase 6) changed the mechanism to table ownership with
`FORCE` dropped**, so the same bypass holds on managed Postgres with no superuser — see
[`./phase-6.md`](./phase-6.md). The reader half (`rag_reader`, non-owner) is unchanged.

## 3.5.6 — Confluence source scoping (`source_scope` table)

`PLAN.md` §0 progress notes, lines ~1576–1631. Governs which spaces/page-subtrees reconciliation
actually sweeps, and what gets purged from the registry when scope shrinks — replacing the old
`CONFLUENCE_SPACES` env var (confirmed dead code, zero consumers, deleted).

- **`source_scope` table** — one row per configured sync root: `root_type` (`space` or `page`) +
  `root_id`, unique on `(root_type, root_id)`.
- **`confluence_sync/domain/scope_resolver.py`** — a pure tree-walk, no extra API calls:
  - `resolve_scope_roots` (`scope_resolver.py:20-55`) maps each root to the live page ids it
    covers — a `space` root covers every page in the listing; a `page` root covers itself plus
    every descendant reachable by walking `parent_id`.
  - `resolve_space_scope` (`scope_resolver.py:66-100`) unions every *active* root recorded for one
    space into an allow-set + per-page tags. Deliberately takes **every** recorded root for a
    space, active or not, so it can distinguish "zero rows ever" (unrestricted, the default) from
    "rows exist but all inactive" (restricted to nothing) — otherwise deactivating a space's last
    root would silently revert to unrestricted instead of purging it.
- **`application/reconciliation.py`** wires this into: (a) space discovery — which spaces get
  swept at all now unions in every space implied by a `source_scope` row, so a brand-new space with
  zero `page_source` rows still gets its first sweep; (b) per-space sweep, narrowing to the
  resolved allow-set; (c) purge-on-scope-removal — deactivating the last active root for a space
  purges everything it used to cover via the same `deactivate_page` path an upstream deletion uses.
- **`scripts/seed_source_scope.py`** — one-off idempotent CLI (upsert/deactivate/delete by
  `root_type`+`root_id`). Rows are seeded here, not by the migration itself — migrations 0001–0003
  never coupled DDL to mutable env state, and seeding from `Settings` would make `alembic upgrade
  head` non-deterministic across environments including the hermetic test DB.

**Current status:** implemented and tested (14 tests), but **no `source_scope` rows are seeded
against the real Confluence tenant yet** (`PLAN.md` §0) — the live token now works, but nothing
will actually sync from it until `scripts/seed_source_scope.py` is run.

## Not this file

- 3.5.1 (pgvector/HNSW pin), 3.5.2 (reranker), 3.5.4 (`query_trace`), 3.5.5 (rerank-lift
  measurement) — all retrieval-side, `../retrieval/phase-3.5.md`.
- The RLS policy itself, the `rag_reader` role, and the negative-isolation tests — retrieval-side,
  same file.
