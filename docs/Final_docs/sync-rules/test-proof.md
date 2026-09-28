# Sync-rules test proof — the tests catch a broken build

The 0.2.8 method: a test is only real if it goes red for a stated reason and green after the change.
Rules 1, 1b and 7 are **red-today** tests — they fail on the pre-change code, so the "fails today"
run *is* the red half of the cycle; the "after the change" run is the green half. One block per
test. Commands run from `backend/` with the local Postgres URL exported (overrides the root `.env`'s
Supabase URL — never edit `.env`):

```
export DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag
```

Substep: 2.2.4 (sync-rules §13 step 1). Date: 2026-09-24.

### 1 — `test_in2_delete_page_removes_rows` · panel i2-gone · database

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest -m db app/features/confluence_sync/tests/test_sync_rules_delete.py::test_in2_delete_page_removes_rows` | FAILED — `deactivate_page` soft-deletes: `action == 'deactivated'` (not `'purged'`) and the page's rows survive |
| After the change | same | PASSED — `purge_page` deletes every table's rows; `action == 'purged'` |

### 1b — `test_in2_delete_then_restore_full_rebuilds` · panel i2-gone · database

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest -m db app/features/confluence_sync/tests/test_sync_rules_delete.py::test_in2_delete_then_restore_full_rebuilds` | FAILED — after the delete, `page_row_counts(1001)["page_source"] == 1` (soft-deactivate leaves the row), so `assert 1 == 0` fails; restore never becomes a first index |
| After the change | same | PASSED — purge removes `page_source`; the next sync first-indexes the page, re-embeds every child (`counter.texts == active child count`), page retrievable again |

### 7 — `test_in2_classified_label_removes_rows` · panel tg-classified · database

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest -m db app/features/confluence_sync/tests/test_sync_rules_delete.py::test_in2_classified_label_removes_rows` | FAILED — no classified handling: the sync takes the metadata-only branch, `action == 'metadata_only'` (not `'purged'`) and the rows survive |
| After the change | same | PASSED — the reserved `classified` label is detected on the raw labels and routes to `purge_page`; `action == 'purged'`, zero rows, `page_source` gone |

All three ran red together on the unmodified code (`3 failed`) and green together after the change
(`3 passed`); `git status --short` shows only the intended files. Full run recorded in the ledger
and progress-log entries for 2.2.4 (§13 step 1).

---

Substep: 2.2.4 (sync-rules §13 step 2: rule 2 + membership gate). Date: 2026-09-24.

Rules 2 and 5 are **red-today** tests — they fail on the pre-gate code (an unlabeled page is
indexed with empty tags; removing the last recognized label takes the metadata-only branch and the
rows survive). The membership guard is a **green-today** test whose one line is reverted to force
red. All three membership tests use recognized fixture pages (3002, 3007) — not the `index_page`
base-label injection — so they judge the gate on the page's own labels.

### 2 — `test_tags_remove_last_recognized_label_removes_rows` · panel tg-remove · database

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest app/features/confluence_sync/tests/test_sync_rules_membership.py::test_tags_remove_last_recognized_label_removes_rows` | FAILED — no membership gate: emptying the labels takes the metadata-only branch, `action == 'metadata_only'` and the page's rows survive (`page_row_counts != 0`) |
| After the change | same | PASSED — zero recognized labels on an indexed page routes to `purge_page`; `action == 'purged'`, every table's rows are 0 |

### 2b — `test_tags_unrelated_labels_alone_do_not_keep_page` · panel tg-remove · database

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest app/features/confluence_sync/tests/test_sync_rules_membership.py::test_tags_unrelated_labels_alone_do_not_keep_page` | FAILED — unrelated labels (onboarding/engineering/guide) kept the page indexed with empty tags; rows survive |
| After the change | same | PASSED — unrelated labels resolve to zero recognized labels → `purge_page`; zero rows. Folder roots / housekeeping tags never keep a page in |

### 5 — `test_in2_untagged_page_never_indexed` · panel ks-index · database

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest app/features/confluence_sync/tests/test_sync_rules_membership.py::test_in2_untagged_page_never_indexed` | FAILED — a first-seen unlabeled page (3007) is indexed with empty tags; `action == 'indexed'` and a `page_source` row is written |
| After the change | same | PASSED — no recognized label on a first-seen page → `action == 'skipped'`, no version/chunk/page_source row written |

### 5-guard — `test_tags_recognized_label_present_keeps_page` · panel tg-remove · database (green-today guard)

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest app/features/confluence_sync/tests/test_sync_rules_membership.py::test_tags_recognized_label_present_keeps_page` | PASSED — a page keeping a recognized label alongside unrelated ones is not purged |
| Guard reverted | invert the membership gate: `if not scope_result.matched_labels:` → `if scope_result.matched_labels:`; rerun | FAILED (`AssertionError` at the `action != "purged"` line) — the recognized-label page is purged, proving the gate's condition is load-bearing |
| Restored | revert the one-line change; rerun (all four membership tests) | PASSED (`4 passed`); `git status --short` clean |

The three behaviour tests ran red together on the unmodified code and green after the gate; the
guard's inversion was run and confirmed red, then restored to green. The gate keys on
`scope_result.matched_labels` (recognized labels present), not the resolved `tags`, so a page with
two conflicting provider labels — zero resolved tags this sync, but recognized labels present —
stays indexed rather than being purged and re-indexed (proven separately by the still-green
`test_ingestion_pipeline.py` conflict tests). Full run recorded in the ledger and progress-log
entries for 2.2.4 (§13 step 2).

## §13 step 3 — drop conflict (D4) + rule 4 visibility + rule 3 guard, 2026-09-24

Two or more recognized provider labels is legitimate sharing, not a conflict: the page resolves to
all matched tags and is visible in each of those scopes by overlap, never public. New behaviour
tests + the inverted resolver tests fail on the unmodified code for one reason — the conflict branch
zeroes the label-derived tags — and pass after the branch is removed. All commands run with
`DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag` exported.

Red-today set (ran together on the unmodified code → **7 failed**; after removing the conflict
branch → all **green**):

| test (file) | Fails today (reason) | After the change |
|---|---|---|
| `test_tags_add_second_tag_updates_tags_no_reembed` (test_sync_rules_visibility.py) | FAILED — 2nd provider label → conflict zeroes tags; `page_source.tags` is not `{mews,toast}` | PASSED — both tags unioned in, metadata-only, 0 re-embed, same version |
| `test_tags_shared_page_visible_in_both_scopes` (test_sync_rules_visibility.py) | FAILED — conflict → empty tags → page not visible in mews (app-layer overlap on `[]` matches nothing) | PASSED — visible in mews and toast, not operacloud |
| `test_tags_remove_shared_tag_keeps_other_scope` (test_sync_rules_visibility.py) | FAILED — the two-tag page never establishes `{mews,toast}` (conflict) | PASSED — after dropping toast: mews-only, 0 re-embed, same version |
| `test_two_provider_labels_share_both_scopes_mews_and_opera_cloud` (test_knowledge_scope.py) | FAILED — resolver returns `tags == ()` | PASSED — `tags == ("obi-mews-test","obi-operacloud-test")` |
| `test_two_provider_labels_share_both_scopes_mews_and_toast` (test_knowledge_scope.py) | FAILED — resolver returns `tags == ()` | PASSED — `tags == ("obi-mews-test","obi-toast-test")` |
| `test_labels_are_trimmed_and_lowercased_before_matching` (test_knowledge_scope.py) | FAILED — two provider labels → `tags == ()` | PASSED — `tags == ("obi-mews-test","obi-toast-test")` |
| `test_two_provider_labels_share_all_scopes_no_conflict_log` (test_ingestion_pipeline.py) | FAILED — a `knowledge_scope_conflict` warning is still emitted and `ps.tags == {"base"}` | PASSED — no conflict log; `ps.tags == {"base","obi-mews-test","obi-toast-test"}` |

Green-today guards (revert-inversion method, §14.7):

### r3-guard — `test_tags_remove_one_tag_keeps_page_updates_tags_no_reembed` · panel i2-labels · database
Rule 3: remove one recognized tag while another stays → metadata-only, no re-embed, same version.

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest …::test_tags_remove_one_tag_keeps_page_updates_tags_no_reembed` | PASSED |
| Guard reverted | add `ChangeClass.labels_changed` to `_REBUILD_CLASSES` (a label-only change now rebuilds); rerun | FAILED — the retag attempts a new version at the same cf_version → `UniqueViolation (uq_document_version_idem)` → job fails; the version is not held stable |
| Restored | remove `labels_changed`; rerun | PASSED; files clean |

### r4-guard — `test_tags_general_tag_visible_everywhere` · panel i2-labels · database
Rule 4: the explicit `general` tag is in every user's scope set → a `[general,toast]` page is
retrievable by a user of any scope.

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest …::test_tags_general_tag_visible_everywhere` | PASSED |
| Guard reverted | drop `obi-general-test` from the resolver's matched set; rerun | FAILED (AssertionError) — the general tag never lands, so a mews/operacloud user (who carries general) no longer resolves the page |
| Restored | revert the resolver; rerun | PASSED; `git status --short` clean on both code files |

The seven behaviour/resolver tests ran red together on the unmodified code and green after the
conflict branch was removed (`13 passed` for the step-3 set). Both guards' inversions were run and
confirmed red, then restored to green. Full run recorded in the ledger and progress-log entries for
2.2.4 (§13 step 3).

## §13 step 4 — RLS floor fail-closed (D3) + read-path overlap, 2026-09-24

Commands run with `DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag` exported.
The change: drop `OR cardinality(tags) = 0` from `chunk_scope_read` (`schema.py`
`apply_chunk_scope_rls`), plus migration `0014_chunk_scope_fail_closed.py`.

Red-today test (fails on unmodified code — the floor makes an empty-tags chunk global):

### RLS — `test_sec_empty_tags_visible_to_no_scope` · panel 3.4.1 (r3-scope) · database
D3: an active chunk with `tags = []` returns for no real scope value (fail-closed floor).

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest …::test_sec_empty_tags_visible_to_no_scope` | FAILED — `assert 18 == 0`: the `cardinality(tags)=0` floor returns the empty-tags chunk under a foreign scope (empty=public leak) |
| After the change | drop the floor line in `schema.py` + migration 0014; rerun | PASSED — empty tags overlap nothing; the `'*'` opt-out still returns the chunk (asserted) |

Green-today guard (revert-inversion method, §14.7):

### D4-guard — `test_sec_read_paths_use_overlap_not_equality` · panel 3.4.1 (r3-scope) · database
D4: a `[mews,toast]` chunk is visible to a scope overlapping one tag, not only to an exact match.

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest …::test_sec_read_paths_use_overlap_not_equality` | PASSED |
| Guard reverted | change the policy predicate from `tags && …` to `tags = string_to_array(…)` (equality); rerun | FAILED — the single-scope mews reader no longer sees the two-tag shared chunk (equality hides legitimate sharing) |
| Restored | revert to `&&`; rerun | PASSED; `git status --short` clean |

### migration — `test_0014_*` · panel 3.4.1 (r3-scope) · database (knowledge-base suite)
Reversibility: floor gone at head, restored on downgrade, dropped again on re-upgrade.

| Step | Command | Result |
|---|---|---|
| Round-trip | `uv run pytest tests/test_migration_0014_chunk_scope_fail_closed.py -v` | 2 PASSED — `qual` has no `cardinality` at head, `cardinality` back after `downgrade 0013_reindex_progress`, gone again after re-`upgrade head`; source spine + RLS enable state survive; curated floor untouched |

Full run recorded in the ledger and progress-log entries for 2.2.4 (§13 step 4).

## §13 step 5 — rule 6: no reuse + title rebuild + retain 0, 2026-09-24

Substep 2.3.1 (i3-embed, i2-rebuild, i4-gc, vd-swap; D1 retain 0, D2 attachment strict xfail). Tests
in `app/features/confluence_sync/tests/test_sync_rules_rebuild.py`. Rules 6 tests are **red-today**
(they fail on the pre-change code), so the "fails today" run is the red half; the title test's red
was additionally re-confirmed by reverting the one line it guards (`ChangeClass.title_changed`).

### 6a — `test_in3_body_edit_reembeds_every_chunk_no_reuse` · panel i3-embed · database

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest …::test_in3_body_edit_reembeds_every_chunk_no_reuse` | FAILED — `assert 5 == 9`: the diff-reuse path embeds only the 5 changed children of 9, reusing the rest |
| After the change | same | PASSED — `_resolve_children` embeds all children; `counter.texts == active child count` |

### 6b — `test_in3_title_change_reembeds_every_chunk` · panel i2-rebuild · database

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest …::test_in3_title_change_reembeds_every_chunk` | FAILED — `assert 0 == 6`: `title_changed ∉ _REBUILD_CLASSES`, so a rename takes the metadata-only path and re-embeds nothing |
| Guard reverted | remove `ChangeClass.title_changed` from `_REBUILD_CLASSES`; rerun | FAILED — same `assert 0 == 6` (rename → metadata-only), proving the one-line trigger is load-bearing |
| Restored | re-add `title_changed`; rerun | PASSED — a rename rebuilds and re-embeds every child |

### 6c — `test_in3_rebuild_deletes_old_version_rows_immediately` · panel i4-gc (D1) · database

| Step | Command | Result |
|---|---|---|
| Fails today | `uv run pytest …::test_in3_rebuild_deletes_old_version_rows_immediately` | FAILED — retain 2 keeps the superseded v1: its 6 chunk rows survive (`assert [<6 chunks>] == []`) and `count_versions == 2` |
| After the change | same | PASSED — `DEFAULT_RETAIN_SUPERSEDED = 0` deletes the just-superseded version + chunks in the swap; only the active version remains |

### 6d — `test_in3_attachment_edit_reembeds_page` · panel i2-rebuild (D2) · database (strict xfail)

| Step | Command | Result |
|---|---|---|
| Xfails today | `uv run pytest …::test_in3_attachment_edit_reembeds_page` | XFAIL (`reason="needs 2.4.1"`, strict) — an attachment-only edit can't stage a new version at the same cf_version (`uq_document_version_idem`); flips to a real pass (→ XPASS, forcing marker removal) when 2.4.1 lands |

Ripple tests updated for the new rules (rewritten, not weakened) proven green in the full
`make check` run recorded in the ledger/progress-log 2.3.1 entry: `test_versioning_gc.py` (retain 0),
`test_versioning_swap.py::test_i4_swap_old_version_and_its_chunks_removed`,
`test_worker_sync.py::test_vd_swap_old_vectors_leave_the_live_set_and_are_deleted_at_once` and its two
`count_versions == 1` re-index assertions, `test_reindex.py`, `test_attachment_wiring.py`.

---

Substep: 2.2.4 (sync-rules §13 step 6: rule 5 positive guard + rule 8 isolation invariant).
Date: 2026-09-24.

Both are **green-today guards** — the behaviour was delivered by earlier steps (membership gate,
step 2; per-page purge, step 1) — so each is proven real by the revert step: undo the one line it
protects, confirm red, restore, confirm green. Checksums of the two touched source files
(`sync_service.py`, `versioning.py`) matched before and after, so the proof left no residue.

### 5 — `test_in2_first_relevant_tag_full_build` · panel ks-index · database

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest …::test_in2_first_relevant_tag_full_build` | PASSED — the unlabeled page builds nothing; adding the first recognized label fully builds it, `counter.texts == active child count` |
| Guard reverted | invert the membership gate `if not scope_result.matched_labels:` → `if scope_result.matched_labels:` in `sync_service.py`; rerun | FAILED — the inverted gate builds the still-unlabeled premise page (`{'chunk': 2, 'document_version': 1, …} != {…0}`), proving the gate is what admits a page only on a recognized label |
| Restored | restore the gate; rerun | PASSED; source checksum back to the pre-revert value |

### 8 — `test_in2_change_never_touches_other_pages_rows` · panel vd-swap · database

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest …::test_in2_change_never_touches_other_pages_rows` | PASSED — editing then deleting page A leaves B's version id, chunk keys, tags and embeddings byte-identical |
| Guard reverted | drop the `WHERE page_id == page_id` scope from the `DELETE FROM document_version` in `purge_page` (`versioning.py`); rerun | FAILED — the unscoped delete reaches B's version (FK violation) and A's purge aborts, so B's snapshot moves / A's rows survive, proving the per-page scope is load-bearing |
| Restored | restore the `where(DocumentVersion.page_id == page_id)`; rerun | PASSED; source checksum back to the pre-revert value |

With this step the eight sync rules each have at least one green database test proven real by the
0.2.8 method. `git status --short` after the proof shows only the intended step-6 files (the two
test files and the docs); the two production files are byte-identical to before the proof.
