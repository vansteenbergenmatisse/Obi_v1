# Deletion and purge

- **Workflow:** ingestion
- **Owning code:** `backend/app/features/ingestion/application/versioning.py` (`purge_page`) and
  `backend/app/features/confluence_sync/application/sync_service.py` (the routing that calls it).
- **Design panel:** `i2-gone` · `tg-purge` · `tg-classified` · `tg-remove` · `ks-index` (design page
  `obi-rag-system-flow.html`)
- **Status:** Implemented (database level) — delete/trash/archive, the `classified` label, an
  unreachable source, **and the last-recognized-label-removed / label-gated-membership triggers**
  all purge or skip. The live label/freshness proof is still pending (needs staging — owner blocker).

## What it does

When a Confluence page is deleted, trashed or archived, or its source becomes unreachable, or it
gains the reserved `classified` label, the page is **removed from the store entirely** — every
chunk, every `document_version`, its `document`, its `page_source` and its `page_restriction` rows.
Nothing is left behind inactive. This is `purge_page(session, *, page_id)`: a single-transaction,
FK-safe delete (release the deferred active-version pointer, delete the versions — chunks cascade —
then the document, then the page_source — restrictions cascade). It returns whether a page row
existed, so re-running it is a safe no-op.

`sync_service` routes to it from four places: the `delete_page` job (`handle_delete_page`), the
sync path when the page's source metadata is gone (`meta is None`), the sync path when change
classification says the status is a delete (`decision.is_delete`), and — detected on the raw labels
before scope resolution — when the reserved `classified` label is present (`handle_sync_page`
returns a `purged` outcome). A page that was purged and later restored or re-published re-enters the
index as a **first index**: `get_local_state` finds no `page_source`, so the next sync does a full
rebuild — every child contextualised and embedded afresh, no vector reused.

This replaces the older soft `deactivate_page` (which only flipped `is_active`/`page_status`) on the
delete and classified paths. `deactivate_page` still exists and is still used by the reconciliation
sweep for source-scope coverage loss (unchanged by this substep).

**Label-gated membership (rule 2 + never-bend rule 5).** Beyond the four delete surfaces above,
`handle_sync_page` also gates on the page's **recognized routing labels** — those matching a
product-catalog routing form (`obi-general`, `{slug}-general`, `{slug}-to-{pos|pms|accounting}`),
enumerated by `ProductCatalog.all_routing_labels()`. Since ADR-routing-labels-sole-content-axis (2026-10-12) these routing
labels are the membership axis; the retired knowledge-scope `-test` tag set
(`settings.knowledge_scope_set` / `knowledge_scopes.json`) no longer decides membership. After
reading the labels: if the page carries **no** recognized routing label, then an already-indexed
page is **purged** (its last recognized label was removed — rule 2, the same all-rows-gone outcome
as a delete), and a first-seen page is **skipped** — never ingested, no version/chunk/`page_source`
row written (rule 5; outcome action `skipped`). A page keeping at least one recognized routing label
stays indexed. Two or more recognized routing labels is legitimate sharing — the page stays indexed
and is reachable under each connection that overlaps them, never churned or hidden.
Folder roots (`source_scope`) no longer decide membership: unrelated Confluence labels are ignored,
and a `source_scope`-root-covered page must still carry a recognized routing label to be indexed.

## Why it does it

Never-bend rule 1 and the accuracy-first stance: hidden-but-present content is a leak waiting to
happen. With content filtering carried by a column (today the routing `labels`), a soft-deactivated
chunk keeps its vector and text on disk; a bug that ignores `is_active`, a raw table read, or a
database dump could surface it.
Deleting the rows means the content is simply not there. For `classified` this is the whole point —
the panel `tg-classified` states it plainly: deleting rather than deactivating means a dump or an
`is_active`-ignoring bug still cannot leak the content.

Purge also makes restore correct for free. The prior code never re-activated a restored page
(`sync_page` took the metadata-only branch and never set `is_active=True`); by deleting `page_source`
on purge, a later restore is indistinguishable from a first index and rebuilds from Confluence, the
source of truth. The risk — a spurious trash webhook purging live work — is accepted (sync-rules
plan §6 rule 1): webhook signature auth gates the trigger, and recovery is a re-index from
Confluence.

This diverges from the design panels `tg-purge`/`tg-classified` as originally worded ("keeps
`page_source` with state `classified` so the sweep knows to skip it"): that rested on the
`scope_state` concept, which the sync-rules decisions retire (D4). The correction is recorded in
`docs/Final_docs/0.4-design-review/plan-corrections.md`. The design page still wins; it gets the
`today`-line update when the 2.2.4 series completes (§13 step 6).

## How we know it works

Database tests in `backend/app/features/confluence_sync/tests/test_sync_rules_delete.py` (level:
database), each naming the panel it protects:

- `test_in2_delete_page_removes_rows` — panel `i2-gone`, rule 1. After a `delete_page` job, every
  table the page owns (chunk, document_version, document, page_source, page_restriction) is at zero
  rows; the outcome action is `purged`.
- `test_in2_delete_then_restore_full_rebuilds` — panel `i2-gone`, rule 1b. After a purge,
  `page_source` is gone; a following sync re-indexes the page with a fresh active version and
  re-embeds every child (asserted via the counting embedder: `texts == active child count`), and the
  page is retrievable again.
- `test_in2_classified_label_removes_rows` — panel `tg-classified`, rule 7. Adding `classified`
  (even alongside a valid recognized scope) drives every table to zero rows on the next sync; the
  outcome action is `purged`.

The membership gate (sync-rules §13 step 2) is proven by
`backend/app/features/confluence_sync/tests/test_sync_rules_membership.py` (level: database):

- `test_tags_remove_last_recognized_label_removes_rows` — panel `tg-remove`, rule 2. Emptying an
  indexed page's labels drives every table to zero rows; outcome action `purged`.
- `test_tags_unrelated_labels_alone_do_not_keep_page` — panel `tg-remove`, rule 2. Replacing all
  recognized labels with unrelated ones (folder-root leftovers) purges the page — unrelated labels
  never keep it in.
- `test_in2_untagged_page_never_indexed` — panel `ks-index`, rule 5 (negative half). A first-seen
  unlabeled page is never ingested (zero rows, outcome action `skipped`).
- `test_in2_first_relevant_tag_full_build` — panel `ks-index`, rule 5 (positive half, §13 step 6).
  The same first-seen page, once it gains its first recognized label, builds in full: a fresh active
  version and every child embedded (`texts == active child count`), retrievable in that scope.
- `test_tags_recognized_label_present_keeps_page` — panel `tg-remove` guard. While a recognized
  label remains, adding/dropping unrelated labels never purges the page.

Rule 8 (a change to one page never touches another's rows) is proven by
`backend/app/features/confluence_sync/tests/test_sync_rules_isolation.py` (level: database):

- `test_in2_change_never_touches_other_pages_rows` — panel `vd-swap`, rule 8. Editing then deleting
  page A leaves neighbour B byte-identical: same active version id, chunk `stable_key`s, tags and
  embedding vectors.

The revert-cycle proof for all of these (the delete/classified three and the membership four) is in
`docs/Final_docs/sync-rules/test-proof.md`.

Not yet proven here: the live label/freshness proof (needs staging — owner blocker).
