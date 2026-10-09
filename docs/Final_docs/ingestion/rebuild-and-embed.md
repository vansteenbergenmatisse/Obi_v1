# Rebuild and embed (versioning)

- **Workflow:** ingestion
- **Owning code:** `backend/app/features/ingestion/application/versioning.py`
  (`stage_and_activate`, `build_chunks`, `_resolve_children`, `_activate`, `_gc_superseded`);
  rebuild triggering in `backend/app/features/confluence_sync/application/sync_service.py`
  (`_REBUILD_CLASSES`).
- **Design panel:** `i2-rebuild`, `i3-embed`, `i4-gc`, `vd-swap`
- **Status:** Implemented (sync rule 6 / §13 step 5, 2026-09-24)

## What it does

When a page changes, ingestion rebuilds the **whole page**. A change is a rebuild trigger when its
`ChangeClass` is in `_REBUILD_CLASSES`: body/section edits, a **title change** (rename), an index
pipeline-config change, or a first index. `stage_and_activate` builds a fresh `document_version`
with all its parent and child chunks staged inactive, then activates it in the caller's single
transaction via a pointer swap (`_activate`): the previously active version is superseded and its
chunks flipped inactive, the new version and its chunks go active, and `page_source` is repointed.

**Every child is contextualised and embedded afresh on every rebuild** — `_resolve_children`
contextualises all children and calls the embedder once with the full set. No vector, and no
`retrieval_content`, is ever carried over from an old version.

Since 8.2.2 (panel `mi-applies`) the build also stamps the page's validated "Applies to"
payload onto `page_source.applicability` and every staged chunk (`build_chunks` /
`_activate`, threaded from the command handler; NULL = no record = label-only). The
Applies-to table itself never reaches the blocks — it is lifted out of the body before
normalization — so it is metadata, not chunk content, and a table-only edit is a restamp,
not a rebuild (see `applicability-schema.md`).

Immediately after the swap, `_gc_superseded` runs with **retain 0**: the just-superseded version
and its chunks are deleted in that same transaction. Nothing is retained; there is no rollback
window. A gate-failed build (zero child chunks) still rolls back whole and leaves no version row
(`i4-failed`), and a `failed`-state row is never GC'd (only `superseded` rows are).

Attachment-only edits are **not** yet a rebuild trigger (`attachment_changed` is deliberately out
of `_REBUILD_CLASSES`): a Confluence attachment edit does not bump the page's `cf_version`, so a new
version cannot stage without colliding on `uq_document_version_idem`. That is deferred to substep
2.4.1 (version identity gains a fingerprint dimension); see the strict-xfail test below.

## Why it does it

Sync rule 6: *a rebuild embeds the whole page; no vector is reused from an old version.* Reuse saved
a few embedding cents but risked a stale vector sitting next to new text — most sharply on a rename,
where the title is part of every child's contextualised text, so a reused vector would hide the old
title. Embedding every child on every rebuild is simpler and removes that class of staleness; the
higher embedding cost is accepted (substep 2.3.1), bounded by the embedder's per-run cap and
circuit breaker.

Retain 0 (decision **D1**, "kill rollback"): with no reuse and no conflict state, a retained
superseded version bought only a rollback path that the owner chose to drop — recovery is a fresh
re-index from Confluence, the source of truth. Deleting the old version in the swap keeps the store
minimal and makes "the old build is gone" provable in one read. The `rollback_to` function and its
public export were retired with the decision (a retained rollback API with no reachable superseded
target would be dead, untested code).

## How we know it works

Database tests (`backend/app/features/confluence_sync/tests/`), all driving the real sync path with
the fixture gateway and the counting embedder; assertions are outcomes (re-embed counts, row
counts), never code paths:

- `test_sync_rules_rebuild.py::test_in3_body_edit_reembeds_every_chunk_no_reuse` — panel `i3-embed`:
  a body edit re-embeds every child (`counter.texts == active child count`), none reused.
- `test_sync_rules_rebuild.py::test_in3_title_change_reembeds_every_chunk` — panel `i2-rebuild`: a
  rename triggers a full rebuild and re-embeds every child.
- `test_sync_rules_rebuild.py::test_in3_rebuild_deletes_old_version_rows_immediately` — panel
  `i4-gc`: after one edit the old version row and its chunks are gone; only the active version
  remains (`count_versions == 1`).
- `test_sync_rules_rebuild.py::test_in3_attachment_edit_reembeds_page` — panel `i2-rebuild` (D2):
  **strict xfail**, `reason="needs 2.4.1"`; flips to passing when 2.4.1 lands.
- `test_versioning_gc.py::test_i4_gc_keeps_zero_superseded_versions` and
  `::test_i4_gc_deletes_the_superseded_version_and_cascades_chunks` — panel `i4-gc`: retain 0, chunk
  cascade.
- `test_versioning_swap.py::test_i4_swap_old_version_and_its_chunks_removed` and
  `test_worker_sync.py::test_vd_swap_old_vectors_leave_the_live_set_and_are_deleted_at_once` — panel
  `vd-swap`: the old version leaves the live set and is deleted in the same swap.
- `test_versioning_failed.py::test_i4_failed_never_garbage_collected_by_gc` — panel `i4-failed`:
  retain 0 touches only `superseded` rows; a `failed` row survives untouched.

Each red-today test's revert/red/green cycle is recorded in
`docs/Final_docs/sync-rules/test-proof.md` (§13 step 5). The design-page **status** flips for
`i2-rebuild`/`i3-embed`/`i4-gc` are batched to §13 step 6, mirroring steps 1–4.

Not proven here: the attachment-only rebuild (deferred to 2.4.1, strict xfail) and the live-webhook
leg (owner-blocked; `verify_sync_rules.py` against staging, step 6).
