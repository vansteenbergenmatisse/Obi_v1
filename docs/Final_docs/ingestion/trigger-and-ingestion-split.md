# Trigger layer vs ingestion layer

- **Workflow:** ingestion (stages 1–2 trigger, stages 3–4 ingestion)
- **Owning code:** trigger — `backend/app/features/confluence_sync/` (`application/sync_service.py`,
  `application/worker.py`, `application/reconciliation.py`, `application/event_service.py`,
  `application/scope_state.py`, `domain/ingest_decision.py`, `application/ports.py`); ingestion —
  `backend/app/features/ingestion/application/command_handler.py`; contract —
  `backend/app/shared/sync_command.py`
- **Design panel:** i1-handle, i2-fetch, i2-gone, tg-purge, tg-classified, ks-index (the sync-rules
  series); reconciliation sweep panels
- **Status:** Implemented (unit + database; live sweep leg owner-run)

## What it does

Two hard-separated layers with one small contract between them:

- The **trigger layer** watches Confluence — webhook events and the 30s reconciliation sweep —
  and decides *what should happen* to a page. It fetches the page's current state (meta, labels,
  covering `source_scope` rows, ancestry) and calls the pure `decide_command`, which returns a
  `SyncCommand(page_id, action ∈ {upsert, delete}, scopes, reason)`. It never chunks or embeds.
- The **ingestion layer** takes a `SyncCommand` and does the work: `apply_sync_command` either
  upserts (fetch body · normalize · classify · chunk · contextualize · embed · version · swap ·
  write metadata + restrictions, stamping exactly `cmd.scopes`) or deletes (hard-purge every row
  for the page). It knows nothing about webhooks, sweeps, or `source_scope`.

The contract (`SyncCommand`) lives in `app/shared` — the only thing the two features share. The
trigger owns an `IngestionSink` Protocol (`application/ports.py`); ingestion satisfies it
structurally via `apply_sync_command` and never imports it. `app/main.py` binds the concrete
sink at startup (`set_ingestion_sink`); the worker calls it inside its handle+complete
transaction.

`scopes` are **authoritative**: the trigger computes `recognized_labels ∩ authorized_tags` and
ingestion stamps exactly those. Authorization comes from covering `source_scope` rows — a row's
`tags` are a recognized-scope allow-list (empty tags authorize *all* recognized scopes, Decision
D3); with no row for a space the space is unrestricted and the labels themselves are the scopes.
The reconciliation sweep additionally discovers tagged pages by CQL
(`gateway.list_pages_by_label`) so a freshly-tagged page under no configured root still becomes a
candidate the worker can authorize.

## Why it does it

Ingestion (chunking, metadata, embeddings) is about to change substantially. The ability to
*notice* a page changed and *decide* what to do with it must never break when ingestion does, so
the two concerns are separated with a boundary the build enforces: `make boundaries` forbids
`app.features.confluence_sync` from importing `app.features.ingestion` at all (rule (e) in
`tools/check_feature_boundaries.py`). Production code depends on ingestion only through the
`IngestionSink` port; test files are exempt from that one edge so contract/integration tests can
drive both layers end to end.

The split also fixed the bug that started it: discovery used to depend on `source_scope` roots,
so a published, correctly-tagged page under no root (e.g. "Mews Page 2") was dropped by the sweep
before the tag logic ran. CQL label discovery plus a space-level allow row now surface and
authorize it.

Design decisions built to their recommended defaults (named in the PR): D1 the contract shape,
D2 decide-in-worker on current state (jobs carry only `page_id`+`reason` — and since the
idempotency-key fix of 2026-09-29 the job key is event-ledger-id-scoped,
`sync_page:{page_id}:{event_id}`, so every real delivery gets its own job and the worker's
version guard collapses redundant same-version jobs to `no_change`), D4 the minimal
contract (ingestion re-fetches meta/body — a disclosed double meta/labels fetch per sync), D5 the
closed `reason` vocabulary, D6 the job queue stays the mediation. Two owner calls on 2026-09-25:
**delete = hard purge everywhere** (the 2-action contract; a delete on an unindexed page reports
`skipped`, on an indexed page `purged`), and **D3 empty tags = all recognized** (no reseeding).
The stamped-scopes model changed from the pre-split *union of root tags + label tags* to the
*intersection* `recognized_labels ∩ authorized` — this fixes latent over-sharing (an all-scopes
space root no longer stamps every page with every scope) and retires the additive custom-tag
behaviour; `make eval` shows byte-identical gold-set numbers (no retrieval regression) because the
gold corpus uses single labels and no narrow allow-lists.

## How we know it works

- `test_ingest_decision.py` (unit): one case per row of the event→command table, parametrized
  over every recognized scope — upsert/delete, the allow-list intersection, empty-tag D3,
  page-root subtree coverage (moved in/out), classified/draft/non-current, sweep==webhook
  agreement. Protects the sync-rules decision panels.
- `test_trigger_layer.py` (database): trigger tests with a fake `IngestionSink` (assert only the
  emitted `SyncCommand`, so they pass even if ingestion is swapped out), including the original
  "Mews Page 2" bug (space row authorizes → upsert) and the uncovered-in-scoped-space delete;
  ingestion tests feeding `SyncCommand`s directly (upsert stamps exactly `cmd.scopes`, delete hard
  purges, delete-on-unindexed is `skipped`); and the contract test (a trigger-produced command is
  applied by ingestion, scopes stamped == scopes decided).
- `test_list_pages_by_label.py` (unit): the fixture CQL-discovery contract the sweep relies on.
- `test_worker_sync.py`, `test_reconciliation.py`, `test_sync_rules_*.py`, `test_versioning_*.py`,
  `test_ingestion_pipeline.py` (database): the full worker/sweep/versioning behaviour end to end
  through the bound real sink. `test_i2_fetch...` documents the D4 double-fetch (meta/labels ×2).
- Boundary gate: `make boundaries` fails if production `confluence_sync` imports `ingestion`
  (verified live — injecting the import trips rule (e); removing it returns clean).
- `make check` green: 1012 backend + 43 knowledge-base passing, 1 xfailed. `make eval` unchanged.
- Live: the reconciliation sweep + CQL discovery against production is an owner-run leg (the
  operator seeds one space-level `source_scope` row so `obi-*-test` are authorized across the
  space); not reproduced here.
