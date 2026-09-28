# Full re-index job

- **Workflow:** ingestion
- **Owning code:** `backend/app/features/confluence_sync/application/reindex.py` (orchestration);
  `backend/app/features/confluence_sync/application/worker.py` (the `reindex` job handler);
  `knowledge-base/schema/models.py` (`ReconciliationRun` progress columns) +
  `knowledge-base/migrations/versions/0013_reindex_progress.py`
- **Design panel:** `i1-sweep` (a pipeline-stamp change reaches every tagged page via one job
  instead of waiting for the daily sweep) and `i2-classify` (the enqueued `sync_page` work is
  version/config classified — a stamp bump rebuilds, an unchanged page is a `no_change` no-op)
- **Status:** Implemented (database level; substep 2.0.3)

## What it does

When a pipeline stamp changes — `parser_version`, `chunker_version`,
`contextualization_version`, `retrieval_schema_version` or `embedding_model` — every tagged page
must be rebuilt under the new pipeline. Without this job the change would only be picked up by the
next scheduled complete sweep (up to 14 days later). `run_reindex` enumerates every live, tagged
page (`page_source.tags` non-empty, ordered by `page_id`) and idempotently enqueues one
`sync_page` job per page, on the exact same version/config-guarded path a live webhook event
takes. It owns no rebuild logic of its own: each enqueued `sync_page` reaches
`handle_sync_page → stage_and_activate`, which embeds the whole page afresh (never a reused
vector, rule #4).

The job is modelled as a `reconciliation_run` row with `kind="reindex"`, so "the job row shows
progress" is literally true. Three explicit columns carry the counter: `total_pages` (tagged pages
to rebuild), `pages_done` (how many enqueued so far), and `cursor` (the last `page_id` enqueued).
Work proceeds in batches (default cap 100, the worker drain-cap convention); progress is flushed
after every batch. If the process crashes, the next invocation reads the persisted `cursor` from
the run row and continues from the next page — a completed page is never re-enqueued. The per-page
enqueue key embeds the pipeline-stamp signature, so re-running at the same stamp collides on the
existing keys (a no-op) while bumping any stamp yields fresh keys and rebuilds every page.
`enqueue_reindex_job` is the single operator/scheduler entry point; the worker's `_handle_reindex`
runs it via `run_reindex`.

## Why it does it

A stamp bump is precisely the case where the cheap version guard would otherwise skip work: the
Confluence revision has not changed, only the pipeline has, so nothing in the webhook stream
signals a rebuild. The job closes that gap with one auditable unit of work instead of waiting for
the safety-net sweep. It reuses `ReconciliationRun` (rather than inventing a new table) because a
reindex is a sweep of the same shape — enumerate a page set, idempotently enqueue `sync_page`,
record counts — and the owner's default (per `docs/plan/decisions.md`) is to build to the
smallest existing pattern. Progress lives in explicit, queryable columns rather than in the
`report` JSONB because the proof requires a counter that survives a restart and can be read
directly. Idempotency is load-bearing: `enqueue_job` is `ON CONFLICT DO NOTHING` on
`idempotency_key`, and change classification renders an already-rebuilt page `no_change`, so a
second run does no rebuild work. The orchestration stays inside `confluence_sync` and reaches
ingestion only through the `sync_page` job path, honouring the one-way feature boundary
(`make boundaries`).

## How we know it works

Tests in `backend/app/features/confluence_sync/tests/test_reindex.py` (database level; all
`db`-marked, rolled back per test). Each names the panel it protects in its docstring.

- `test_reindex_batches_enqueue_every_tagged_page` (panel `i1-sweep`) — one reindex job enqueues a
  `sync_page` rebuild for every tagged page across multiple batches; an untagged page is left
  alone. Asserts `total_pages`, `pages_done`, `jobs_enqueued`, `cursor`, and the exact set of
  enqueued page ids.
- `test_reindex_resume_after_crash_does_not_reenqueue_completed_pages` (panel `i1-sweep`) — a run
  interrupted after one batch resumes from the persisted cursor, finishes, and enqueues each
  remaining page exactly once (never re-enqueuing a completed page).
- `test_reindex_progress_counter_survives_a_restart` (panel `i1-sweep`) — the counter is re-read
  from the `reconciliation_run` row in a fresh session (`total_pages`/`pages_done`/`cursor`
  persisted) and the run continues to completion.
- `test_reindex_stamp_bump_rebuilds_every_tagged_page_with_a_new_version` (panel `i2-classify`) —
  bumping `contextualization_version` and running the job yields a fresh `document_version` per
  tagged page (the old one is GC'd in the swap — retain 0, no rollback; sync rule 6 / D1, §13
  step 5).
- `test_reindex_second_run_is_a_noop` (panel `i2-classify`) — after a reindex completes at a
  stamp, running it again at the same stamp enqueues no new jobs and creates no new versions.

Handler registration is covered by
`test_i1_handle_handler_set_covers_sync_delete_reconcile` (panel `i1-handle`), extended in 2.0.3
to assert `reindex` is the fourth wired job type. Migration `0013_reindex_progress` was applied up
and down against the local pgvector Postgres to confirm the three columns are added and dropped
reversibly.

**Not yet proven / out of scope here:** no scheduler trigger or operator CLI is wired for the
reindex job in 2.0.3 (the substep is database-level); `enqueue_reindex_job` exists as the entry
point but a scheduled/operator invocation and a live run are future work. Cross-worker-crash
resumability is proven at the `run_reindex` function level (explicit commit boundaries between
batches), not through the worker's single handle+complete transaction.
