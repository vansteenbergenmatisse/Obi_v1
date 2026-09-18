# Phase 0 — Design docs & ADRs (ingestion-relevant parts)

**Status:** ✅ done. **No code** — this phase produced design documents only.

Phase 0's deliverable was `docs/rag/DESIGN.md` plus two ADRs, written and reviewed *before* any
Phase 3.5 code (`docs/rag/PLAN.md` lines 1839–1868). Two of the durable decisions it locked shape
how ingestion is built and where its write authority comes from. A third ADR, written earlier in
the project's life, fixed the module boundary ingestion lives inside.

## Files & folders used

- `docs/rag/DESIGN.md` — the design of record.
- `docs/adr/0003-Feature-Boundary-Enforcement.md` — feature-facade rule, `platform`/`shared` split.
- `docs/adr/0004-Multi-Source-Provider-Tagging-And-RLS.md` — RLS role split (writer vs reader).
- `apps/automation/tools/check_feature_boundaries.py` — the machine enforcement of ADR-0003.

## What ADR-0003 fixes for ingestion

`ingestion` and `confluence_sync` are two of the four features with **one public root**
(`app/features/<f>/__init__.py`) that re-exports everything crossing the boundary — nothing outside
a feature may deep-import it, and code inside a feature must not import its own root (the
"self-facade" ImportError trap). This is why, for example, `confluence_sync/application/
sync_service.py` imports `stage_and_activate`, `attachment_to_blocks`, `classify`, etc. from
`app.features.ingestion` (the root), never from `app.features.ingestion.application.versioning`
directly. `apps/automation/tools/check_feature_boundaries.py` fails the build on this, wired as
`make boundaries`.

Two decisions from ADR-0003 that materially affect ingestion's code layout:

- **D4** — the ingestion facade re-exports `normalization` as a *module* (`norm.Block`,
  `norm.normalize_body`, `norm.content_hash`), not loose symbols — every ingestion call site uses
  the `norm.` prefix.
- The one legal same-feature deep import that isn't through a root: `confluence_sync/application/
  worker.py` lazily imports `reconciliation` inside `_handle_reconcile_space` to avoid a module-load
  cycle (`worker.py:68-75`) — permitted because it's a same-feature deep import (rule b), not a
  cross-feature one.

## What ADR-0004 fixes for ingestion

ADR-0004 designs the RLS isolation model that Phase 3.5.3 later implements (see
[phase-3.5.md](./phase-3.5.md)). The half of it that lands on the ingestion side:

- **The writer role (`rag_writer`, superuser-equivalent, `BYPASSRLS`)** is the identity every
  ingestion write runs as — the worker, the webhook, reconciliation, and the single activation
  point in `ingestion/application/versioning.py`. RLS is enabled only on reads; the writer path is
  deliberately untouched by it (ADR-0004 decision 4).
- **The single ingestion seam.** Decision 8: `versioning.py`'s activation point is the *one* place
  that stamps `source_id`/`source_type`/`tags` onto `page_source` and `chunk` rows — a constant
  (`confluence:default`) today, becomes a parameter when a second source type is added. Nothing
  else in ingestion needs to know about source isolation.
- **CHECK constraint, not a PG enum**, for `source_type` — so a new connector never needs `ALTER
  TYPE` inside a migration.

## What's retrieval-side instead

ADR-0004's RLS policy, GUC binding, and reader role; ADR-0005 (reranking + answer pipeline) — see
`../retrieval/phase-0.md`.
