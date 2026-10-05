# Sync-rules manual tests — MT-1..MT-7

The human procedures that prove the eight sync rules against a **real Confluence + staging store**,
mirroring the automated fixture-gateway tests one-for-one. Each case names: the Confluence action to
perform, what to observe, the automated test that proves the same outcome offline, and whether the
live runner `verify_sync_rules.py` covers it.

**Never run these against production.** Run against staging with the owner's dedicated test pages,
and save the output where substep 2.2.4's Proof line says (the pull request).

**Label hygiene (owner rule, 2026-10-02).** Any Confluence label added *only to drive a test* — a
scope label on a scratch page, a poke/resync label, anything not approved as a page's real tag — is
removed again before the test is called done. A test is not finished while a test-only label is
still live on any page. Scratch pages end in the trash; surviving real pages end with exactly the
labels the owner approved, nothing else.

## Tooling (both **written**; running the live one stays owner-blocked)

- `backend/scripts/page_state.py <page_id> [marker]` — read-only page dump: active/inactive chunk
  counts (parent/child split), the distinct `tags` on active chunks, `page_status` +
  `current_cf_version` + `active_doc_version_id` (the "is this page live" summary that *replaces* the
  retired `scope_state`), every `document_version` id with its `state`/`cf_version`, and (with
  `marker`) the count of the page's chunks whose `display_content`/`retrieval_content` contains the
  marker word. This is the observation tool every MT reads from. **Written and tested** — runs
  against any reachable DB (local pgvector or the target store), no secrets; covered by
  `test_page_state_script.py` (3 db tests). Exit 1 on an absent page is the clean "purged" signal.
- `backend/scripts/verify_sync_rules.py` — the live staging runner. Refuses the offline fixture
  gateway; drives the label-based rules (2, 3, 4, 5, 7) automatically via the Confluence v1 label
  API and prompts for the physical actions no API here can perform — trash/restore (rule 1) and
  body/title edit (rule 6). Prints pass/fail per rule from DB-state readings (mirrors
  `verify_knowledge_scope_live.py`). Requires `--yes` (a production-guard) and an already-synced
  `--page-id` carrying one recognized label. **Written** — but like its sibling live script it is a
  network + credentials tool with no hermetic test; its logic mirrors the green fixture-gateway
  tests.

Both scripts are now **written**. **Running** `verify_sync_rules.py` still needs staging access +
Confluence site-admin (and, for the webhook-delivery leg, `CONFLUENCE_WEBHOOK_SECRET`) — owner-only
— so the live leg stays outstanding in the ledger under "need from you". Until it is run, the
database level (the automated tests below, all green) is the standing proof. The procedures are
recorded here so the run is turnkey.

## The freshness window

After each Confluence action, wait for the webhook (or the next sweep) to drive the sync before
reading `page_state.py` — the design's freshness target. A change that hasn't synced yet is not a
failure; re-read after the window.

## Cases

### MT-1 — Delete, restore, delete (rules 1 + 1b)
- **Do.** Publish a tagged test page; confirm it is searchable. Trash it in Confluence. Wait, read.
  Restore it from trash. Wait, read. Trash it again.
- **Expect.** After the first trash: `page_state.py` shows **zero** rows for the page — no active or
  inactive chunks, no `document_version`, no `page_source` (purge, not soft-hide). After restore: a
  **fresh** `document_version` (new id), full child set re-embedded, page searchable again. After the
  second trash: zero rows again, no duplicate version left behind.
- **Automated mirror.** `test_in2_delete_page_removes_rows`, `test_in2_delete_then_restore_full_rebuilds`
  (`test_sync_rules_delete.py`, panel i2-gone). **Live-script covers it:** yes.

### MT-2 — Remove the last recognized label (rule 2)
- **Do.** On an indexed page carrying exactly one recognized knowledge-scope label, remove that
  label (leave the page published, optionally with unrelated labels). Wait, read.
- **Expect.** `page_state.py` shows **zero** rows — losing the last recognized label removes the page
  exactly like a delete. Unrelated labels alone never keep it in.
- **Automated mirror.** `test_tags_remove_last_recognized_label_removes_rows`,
  `test_tags_unrelated_labels_alone_do_not_keep_page` (`test_sync_rules_membership.py`, panel
  tg-remove). **Live-script covers it:** yes.

### MT-3 — Remove one recognized label, another stays (rule 3)
- **Do.** On a page tagged with two recognized scopes (e.g. `obi-mews-test`, `obi-toast-test`),
  remove one. Note the active `document_version` id first. Wait, read.
- **Expect.** Same `document_version` id (no rebuild), the remaining scope still on `tags`, and no
  re-embed (metadata-only). The page stays searchable in the surviving scope only.
- **Automated mirror.** `test_tags_remove_one_tag_keeps_page_updates_tags_no_reembed`
  (`test_sync_rules_visibility.py`, panel i2-labels). **Live-script covers it:** yes.

### MT-4 — Add a second recognized label (rule 4, sharing)
- **Do.** On a page tagged `obi-mews-test`, add `obi-toast-test`. Note the version id first. Wait,
  read; then query as a Mews user and as a Toast user, and as an Opera Cloud user.
- **Expect.** Same `document_version` id, both tags on `tags`, no re-embed. Found under Mews **and**
  Toast, **not** under Opera Cloud (legitimate sharing by overlap, never public). A page tagged
  `obi-general-test` + anything is found under every scope.
- **Automated mirror.** `test_tags_add_second_tag_updates_tags_no_reembed`,
  `test_tags_shared_page_visible_in_both_scopes`, `test_tags_general_tag_visible_everywhere`
  (`test_sync_rules_visibility.py`, panels tg-two/i2-labels). **Live-script covers it:** yes.

### MT-5 — First recognized label on an untagged page (rule 5)
- **Do.** Publish a page with **no** recognized label; wait, read (nothing should exist). Add one
  recognized label. Wait, read.
- **Expect.** While unlabeled: `page_state.py` shows **zero** rows — never ingested. After the first
  recognized label: a full build — a `document_version`, the full child set embedded, searchable in
  that scope.
- **Automated mirror.** `test_in2_untagged_page_never_indexed` (negative half, step 2) +
  `test_in2_first_relevant_tag_full_build` (positive half, step 6) (`test_sync_rules_membership.py`,
  panel ks-index). **Live-script covers it:** yes.

### MT-6 — Edit body, then rename (rule 6)
- **Do.** On an indexed page, edit the body (a real content change). Wait, read. Then rename the
  page title, body unchanged. Wait, read. Use a `marker` word added in each edit.
- **Expect.** Each edit produces a **new** `document_version` id and re-embeds **every** child (no
  vector reuse); the marker appears in the expected child count. The just-superseded version and its
  chunks are **gone** immediately (retain 0), not merely inactive.
- **Automated mirror.** `test_in3_body_edit_reembeds_every_chunk_no_reuse`,
  `test_in3_title_change_reembeds_every_chunk`, `test_in3_rebuild_deletes_old_version_rows_immediately`
  (`test_sync_rules_rebuild.py`, panels i3-embed/i2-rebuild/i4-gc). **Live-script covers it:** yes
  (body+title). Attachment-only edit is **out of scope** (D2, blocked by version identity until
  substep 2.4.1 — tracked by the strict xfail `test_in3_attachment_edit_reembeds_page`).

### MT-7 — Add the `classified` label (rule 7)
- **Do.** On an indexed page (any recognized tags), add the reserved label `classified`. Wait, read.
- **Expect.** `page_state.py` shows **zero** rows — `classified` removes the page outright, whatever
  other recognized tags it carried. Re-tagging (remove `classified`, keep a recognized label)
  re-indexes it as a first build.
- **Automated mirror.** `test_in2_classified_label_removes_rows` (`test_sync_rules_delete.py`, panel
  tg-classified). **Live-script covers it:** yes.

### Rule 8 — a change to one page never touches another (side-check across every MT)
- **Do.** Keep a second, unrelated indexed page B untouched throughout MT-1 and MT-6. Read B's
  `page_state.py` before and after A's churn.
- **Expect.** B's `document_version` id, chunk set, tags and embeddings are unchanged — one page's
  edit or delete never moves a neighbour's rows.
- **Automated mirror.** `test_in2_change_never_touches_other_pages_rows`
  (`test_sync_rules_isolation.py`, panel vd-swap). **Live-script covers it:** observe during MT-1 /
  MT-6 (not a separate live case).

## What no manual test can cover
- **Attachment-only rebuild** (rule 6, attachments) — blocked by version identity until substep
  2.4.1; held as a strict xfail, not a live case.
- **The RLS fail-closed floor** (D3, empty tags visible to no scope) — a database-role assertion
  (`test_sec_empty_tags_visible_to_no_scope`), not a Confluence action; proven at the database level.
- **Webhook delivery / detection latency** — the signing gap and the 14-day complete-sweep timing
  are operational, reported from the `verify_sync_rules.py` run, not asserted here.
