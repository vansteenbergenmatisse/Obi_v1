# Sync rules — make the vector store match the eight rules

Status: **code + tests complete (approved); tag behaviour verified live; Supabase at migration head
(0014) as of 2026-09-25** — §13 **all 6 steps done and green**; `make check` green (backend 940 + 1
xfailed, kb 43, boundaries 0). The two live scripts are **written** (`page_state.py` tested by
`test_page_state_script.py`; `verify_sync_rules.py` authored). On **2026-09-25** the tag→scope path was
**verified end-to-end against live Supabase via
the localhost:3100 widget**: scope-correct retrieval + isolation (toast→"grapes"/Toast Testpage,
mews→"red bananas"/Mews Testpage, no cross-leak), and the **Q-B empty-tags census came back clean
(0 active chunks with `tags=[]`)**. On **2026-09-25** Supabase was **brought to migration head**:
`alembic upgrade head` applied **0013 + 0014** (current before `0012`, after
`0014_chunk_scope_fail_closed (head)`), and both live proofs passed — 3d: as `rag_reader`, empty tags
are visible to **no** scope while mews/toast/operacloud/general each return 2 and `*` returns 8; 3e:
reconciliation ran every 15s with drift 0 / errors 0 and the `reconciliation_run.cursor` error is
**gone**. Also on **2026-09-25** the **live sync-rules runner passed its automated leg** on the real
prod test pages (no staging exists; owner-authorized): `verify_sync_rules.py --no-manual` drove rules
**2/3/4/5/7 + rule 8 — all PASS**, labels restored, the Toast page rebuilt clean (retain-0: 0 inactive
chunks, 1 version row); output in `backend/sync-rules-run.txt`. **What remains — owner only,
deploy-and-sign-off tail:** ~~(1) bring Supabase to migration head~~ **DONE 2026-09-25**; (2) run the
**two manual live rules** — 1 (trash/restore) + 6 (body/title edit) — the automated leg is **DONE
2026-09-25**; (3) tick the 2.2.4/2.3.1 action-plan checkboxes once (2) is in the PR; ~~(4) reconcile
the stale design-page target-lines~~ **DONE 2026-09-25** (owner go-ahead; 7 panels reconciled to
D1–D4). The **▶ Remaining work checklist** at the top of §0 has the exact commands and gotchas. **The
only tail left is (2) the two manual live rules, then (3) the checkboxes.**

**Update 2026-09-30 — the live webhook is now the delivery path.** The Forge bridge
(`services/obi-confluence-sync/`) was registered, deployed to Forge production and installed on
`omniboost.atlassian.net`; secret parity Forge↔Railway proven by signed curl (200 valid / 401
tampered); worker drain confirmed on Railway (`ENABLE_BACKGROUND_JOBS=true`, job succeeded); and a
real Confluence `label_added` event (unrecognized smoke label on Toast-testpage 2 `1713176590`)
travelled Confluence → Forge → Railway → event ledger → job → correct no-index decision, with the
indexed Toast page byte-identical to baseline. That satisfies `i1-webhook`'s live-proof condition
(see `docs/Final_docs/ingestion/webhook.md`) and means the two manual rules below can — and should —
be driven through the **real webhook** (plain Confluence UI actions, verified with `page_state.py` +
the event ledger) instead of the in-process `verify_sync_rules.py` runner. Each manual leg must also
re-assert **rule 8**: the Mews page `1670971395` stays byte-identical throughout. Full detail in §0's
2026-09-30 block.

**§14 (Execution appendix)** inlines the exact test harness, the current + target RLS DDL, the
counting embedder, the naming/docstring/coverage/proof formats, and the CI xfail mechanics — so a
fresh-context agent can execute from this file alone, without re-deriving them from the tree.
Line numbers elsewhere in this doc are anchors as of writing; trust the named symbols/panel ids over
the numbers, and grep the live tree if they drift.

---

## 0. Execution status (updated 2026-09-25) — read this first on resume

Owning action-plan substep: **2.2.4** (the §13 series is packaged under it, plus pointers into
2.2.5 / 2.3.1 / 2.4.1 / 3.4.1). Branch: `feat/rag-phase-4-embed-security-hardening`. Everything is
**left uncommitted in the working tree** per the branch's owner-review convention. The running
record is `docs/Final_docs/ledger.md` + `docs/Final_docs/progress-log.md` (one entry per §13 step);
this §0 is the at-a-glance index those entries expand on.

### ▶ Remaining work (the clean-slate checklist) — 2026-09-25

The eight-rule **code, tests and local proof are done and green**; the tag→scope path is **verified
live** (retrieval + isolation through the localhost:3100 widget against Supabase); and **Supabase is
now at migration head (2026-09-25)**. What is left is **owner-only** — staging / a live Confluence
action. Do them in order:

> **→ NEXT ACTION: the OWNER runs the two MANUAL live rules (1 delete, 6 edit).** The **automated**
> live rules **2/3/4/5/7 + rule 8 all PASSED on 2026-09-25** against the real prod test pages
> (Toast `1670873122` scope-a `obi-toast-test`, Mews `1670971395` as the rule-8 side-check), run with
> `--no-manual` (no staging exists yet — owner accepted running on the grapes/bananas prod test pages).
> Output saved to `backend/sync-rules-run.txt`; the page came back healthier than baseline (retain-0
> clean: 0 inactive chunks, 1 version row). Rules **1 (trash/restore)** and **6 (body/title edit)** are
> interactive Confluence-UI steps the owner will run later; only then are 2.2.4/2.3.1 fully ticked.

### ✅ Done 2026-09-30 — Forge webhook bridge deployed, installed and proven live (delivery leg of 2.0.2)

Everything below ran on 2026-09-30; working tree still uncommitted per the branch convention
(`services/obi-confluence-sync/manifest.yml` now carries the real app id, plus the generated
`package-lock.json` — commit both). Runbook followed: `docs/runbooks/obi-confluence-sync-deploy.md`.

- **Registered** the Forge app once (manifest placeholder → real id
  `ari:cloud:ecosystem::app/b36e7d9d-5117-4f7e-a49e-fcdb6ca19118`). En route: the account had no
  Developer Space, so one named **Omniboost** was created, and the Atlassian Developer Terms
  (incl. the beyond-free-allowance billing clause) were accepted.
- **Secret** `CONFLUENCE_WEBHOOK_SECRET` set as an **encrypted Forge production variable** before
  deploy (same value as the Railway service variable; never printed).
- **`forge lint`** clean after `--fix` migrated the deprecated egress entry to the `- address:` form;
  **`forge deploy -e production`** succeeded (app version 2.0.0); **installed** on
  `omniboost.atlassian.net` Confluence (owner, via the install dialog; `forge install list` shows
  production / Up-to-date).
- **Proof 1 — secret parity (signed curl at Railway):** valid HMAC → `200 {"accepted":true,
  event_id:1, job_id:28}`; tampered body, same signature → `401 invalid signature`.
- **Proof 2 — worker drain:** job 28 `succeeded` on Railway (`ENABLE_BACKGROUND_JOBS=true` confirmed
  in effect).
- **Proof 3 — real event end-to-end (label smoke):** owner added the unrecognized label
  `obi-smoke-test-delete-later` to **Toast-testpage 2 (`1713176590`)** in the Confluence UI →
  Forge delivered it (deterministic-hash `delivery_id`) → event_ledger row 2 (`label_added`,
  `origin=0`) → job 29 `succeeded` → worker correctly indexed **nothing** (no recognized label; 0
  `page_source` rows) — the rule-5 negative half observed live through the real webhook. The indexed
  Toast Testpage `1670873122` stayed byte-identical to its pre-test baseline (tags
  `['obi-toast-test']`, 2 active chunks, 1 version row). This is `i1-webhook`'s live proof
  (webhook.md: a real Confluence event → one ledger row + one job within seconds); the panel flip to
  verified is pending with the step-3 checkbox batch. Note: `forge logs` showed nothing despite the
  proven delivery (Atlassian log-ingestion lag) — the ledger is the evidence of record.
- **Consequence for the remaining manual legs:** run rules 1 and 6 as plain Confluence-UI actions and
  let the **live webhook** deliver (stronger evidence than the in-process `verify_sync_rules.py`
  path, which predates the bridge). Verify each with `scripts/page_state.py 1670873122` + the event
  ledger, and re-assert **rule 8** each time: `page_state.py 1670971395` (Mews) byte-identical
  before/after every leg.

**1 · Bring Supabase to migration head (applies 0013 + 0014) — ✅ DONE 2026-09-25.** Was behind by
0013 (`reconciliation_run.cursor`) + 0014 (RLS fail-closed floor). `alembic current` read `0012`
before; `upgrade head` applied both; `current` after = **`0014_chunk_scope_fail_closed (head)`**. Only
`upgrade` was ever run (never-bend rule 1). Q-B census was **0** immediately before; port was the
session pooler (5432, not 6543); owner confirmed a recent backup first. Live 3d proof: as `rag_reader`
(via `get_reader_engine`, both `app.allowed_sources` and `app.allowed_knowledge_scopes` set) empty-tags
chunks visible = **0** under mews/toast/operacloud/general/`*`/unset, while real corpus = 2/2/2/2 per
scope and 8 under `*`. Live 3e proof: reconciliation ran every 15s (drift 0, errors 0,
pages_scanned 4), each job succeeded, **zero** `reconciliation_run.cursor` errors. The steps below are
kept for the record / any future re-run.
  - **Q-B gate first** — census must be run right before 0014 (last run 2026-09-25 was **0**):
    ```
    cd backend && uv run python -c "
    from schema.engine import session_scope
    from sqlalchemy import text
    with session_scope() as s:
        print('empty-tags active chunks:', s.scalar(text('select count(*) from chunk where is_active and cardinality(tags)=0')))
    "
    ```
    **0** → proceed. **>0** → re-tag the legitimately-global pages with `obi-general-test` in
    Confluence and re-sync first; leave the rest (they correctly go dark). Do not auto-mutate.
  - **Gotcha:** `.env` `DATABASE_URL` is **double-quote-wrapped**; the app strips the quotes but raw
    alembic does not (it throws "Could not parse SQLAlchemy URL"). Pass it unquoted, never printing
    the secret:
    ```
    cd backend
    export DATABASE_URL="$(python3 -c "print([l.split('=',1)[1].strip().strip(chr(34)) for l in open('../.env') if l.startswith('DATABASE_URL=')][0])")"
    uv run alembic -c ../knowledge-base/migrations/alembic.ini current       # confirm the gap
    uv run alembic -c ../knowledge-base/migrations/alembic.ini upgrade head  # applies 0013 + 0014
    uv run alembic -c ../knowledge-base/migrations/alembic.ini current       # expect 0014
    unset DATABASE_URL
    ```
    **Only ever `upgrade` on Supabase — never `downgrade` (especially 0009; never-bend rule 1).**
  - Verify the floor is live (as `rag_reader`, expect 0):
    `SET ROLE rag_reader; SET app.allowed_knowledge_scopes='mews'; SELECT count(*) FROM chunk WHERE cardinality(tags)=0 AND is_active; RESET ROLE;`

**2 · Run the live MT-1..MT-7 proof.** ◑ **Automated leg DONE 2026-09-25; manual leg (rules 1, 6)
owner-deferred.** No staging exists, so — with owner sign-off — the automated rules were run on the
real prod test pages with `--no-manual --scope-a obi-toast-test --scope-b obi-mews-test`:
```
cd backend
uv run python scripts/page_state.py 1670873122 | tee baseline.txt
uv run python -u scripts/verify_sync_rules.py --page-id 1670873122 --other-page-id 1670971395 \
    --scope-a obi-toast-test --scope-b obi-mews-test --no-manual --yes | tee sync-rules-run.txt
```
Result: rules **2/3/4/5/7 + rule 8 all PASS**, labels restored, page rebuilt clean (retain-0). Pre-flight
verified live first: OpenAI embeddings OK (3072) and Anthropic OK (the earlier stale key is fixed), so
rebuilds fully contextualize+embed. The contextualizer degrades to metadata-only on an `AnthropicError`
(never aborts a rebuild), so a stale Claude key could not have left the page purged. **Still owner-only:**
rules **1** (trash then restore the page in Confluence) and **6** (edit body, then rename title) — the
two interactive UI steps `--no-manual` skips. Re-run without `--no-manual` to drive them:
    ```
    cd backend
    uv run python scripts/page_state.py <page_id>                     # baseline snapshot
    uv run python scripts/verify_sync_rules.py --page-id <page_id> --other-page-id <other> --yes
    ```
  Auto-drives rules 2/3/4/5/7 via the label API; **pauses** for the manual trash/restore (rule 1) and
  body/title edit (rule 6). `--no-manual` runs only the automated rules. **Save the output → paste in
  the PR** (the CLAUDE.md live-level rule). This output is what unblocks step 3.

**3 · Tick the 2.2.4 / 2.3.1 checkboxes** in `obi-action-plan.html` — only after step 2's output is in
the PR (they name that live proof).

**4 · Reconcile the stale design-page target-lines** on `obi-rag-system-flow.html` — ✅ **DONE
2026-09-25** (owner go-ahead). 17 field edits across 7 panels (`tg-two`, `i4-gc`, `vd-swap`,
`i3-embed`, `i2-rebuild`, `r3-scope`, `tg-filter`) brought simple/steps/tests/settings/note/code text
to D1–D4; `r3-scope` flipped `unverified → built` (0014 applied + verified live). Recorded in
`docs/Final_docs/0.4-design-review/plan-corrections.md` ("TARGET lines RECONCILED"); brief regenerated
(192 panels).

> Also live-confirmed on 2026-09-25 but **not** a sync-rules deliverable: the localhost:3100 widget
> answers end-to-end once a **valid `ANTHROPIC_API_KEY`** is in `.env` (a stale key returned 401 —
> "answer generation failed"). Retrieval/isolation are independent of that key.

### ✅ Done — §13 step 1 (purge_page + rule 1 + rule 7 + restore)

Rules satisfied: **1** (delete/trash/archive → purge), **1b** (delete→restore = first-index full
rebuild), **7** (`classified` label → purge).

- **New code:** `purge_page(session, *, page_id)` in
  `backend/app/features/ingestion/application/versioning.py` (one FK-safe txn: null the deferred
  `active_doc_version_id` → delete `document_version` by page_id [chunks cascade] → delete
  `document` → delete `page_source` [restrictions cascade]); exported from the ingestion feature
  root (`__init__.py`).
- **Routing:** `confluence_sync/application/sync_service.py` now purges from all four delete
  surfaces — `handle_delete_page`, the `meta is None` path, the `classify().is_delete` path, and
  **new** `classified`-label detection on the raw labels via `RESERVED_CLASSIFIED_SCOPE` (matched
  before scope resolution, since `classified` is excluded from the recognized set). `SyncOutcome`
  action renamed `deactivated`→`purged` (no non-test code branches on `.action`).
- **Config:** `RESERVED_CLASSIFIED_SCOPE` re-exported from `app.platform.config` root.
- **Tests (database):** `backend/app/features/confluence_sync/tests/test_sync_rules_delete.py` —
  `test_in2_delete_page_removes_rows`, `test_in2_delete_then_restore_full_rebuilds`,
  `test_in2_classified_label_removes_rows`. Test infra added to `tests/_helpers.py`:
  `CountingEmbedder`, `install_counting_embedder`, `page_row_counts`.
- **Removed** the strict-xfail `test_delete_marks_the_active_version_superseded` (moot: purge deletes
  the version row) and the redundant `test_delete_deactivates_page`, both in `test_worker_sync.py`.
- **Docs/panels:** component doc `docs/Final_docs/ingestion/deletion-and-purge.md`;
  proof `docs/Final_docs/sync-rules/test-proof.md`; corrections appended to
  `docs/Final_docs/0.4-design-review/plan-corrections.md`; coverage rows added to
  `docs/Final_docs/0.5-regression-tests/coverage-map.md`; panel `tg-classified` flipped
  `build→built`, `i2-gone`/`tg-purge` today-lines corrected (status flips batched to step 6); brief
  regenerated.
- **Gate:** `make check` green (backend 931 passed, kb 41 passed, boundaries 0); ruff/pyright clean
  on touched code; whole-repo pyright net-decreased (ADR-0003 D1 holds).

### ✅ Done — §13 step 2 (rule 2 + membership gate)

Rules satisfied: **2** (last recognized label removed → purge), **5** (first-seen page with no
recognized label → never ingested). Panels `tg-remove` (build → built), `ks-index` (today-line
updated); `i2-gone` today-line updated (unlabeled trigger now live).

- **New code:** membership gate in `sync_service.handle_sync_page`, right after
  `resolve_knowledge_scope_tags`: `if not scope_result.matched_labels:` → `purge_page` if already
  indexed (`local is not None`), else `SyncOutcome(action="skipped")`. Keys on **matched_labels**
  (recognized labels present), not resolved `tags`, so a conflict page (zero tags this sync) stays
  indexed rather than churning. `SyncOutcome.action` gains `skipped`. The scope-resolution block was
  moved above the restrictions/attachments fetch so the gate short-circuits before that work.
- **Tests (database):** `test_sync_rules_membership.py` — `test_tags_remove_last_recognized_label_removes_rows`,
  `test_tags_unrelated_labels_alone_do_not_keep_page`, `test_in2_untagged_page_never_indexed`,
  `test_tags_recognized_label_present_keeps_page` (guard). Red-today proof + guard-inversion proof in
  `test-proof.md`.
- **Test-infra decision:** the generic DB fixtures (1001/1002/2002/3005/3007/3010) carry only
  unrelated labels, so the gate un-indexes them. The shared `index_page` helper now injects the base
  `obi-general-test` scope **only when a page has no recognized label** (leaving scope-tagging tests
  that set their own recognized label untouched). 14 tests across 12 files were adjusted (explicit
  recognized label on direct `handle_sync_page`/enqueue paths; `'*'` knowledge-scope wildcard on 3
  RLS source-axis tests that relied on the empty-tags floor; premise rewrites for
  scope_tagging_add/reindex/verify_isolation_script). Full list in `plan-corrections.md`.
- **Source_scope coexistence:** roots still sweep+tag but no longer grant membership (a covered page
  needs a recognized label); `test_reconciliation.py`'s two root tests updated accordingly.
- **Gate:** `make check` green (backend 935 passed, kb 41, boundaries 0); ruff/format clean on
  touched files; whole-repo pyright net-decreased (the `index_page` annotation change removed a
  pre-existing `set_version` error; ADR-0003 D1 holds).
- **Live proof deferred (owner-blocked):** the `tg-remove`/`ks-index` **live** leg — the staging
  label script — is **not** run (needs staging + `CONFLUENCE_WEBHOOK_SECRET` + Confluence
  site-admin). `tg-remove` was flipped `build → built` on the unit+db proof alone, mirroring step
  1's `tg-classified` flip; the live leg stays outstanding (§9 scripts still unwritten).
- **Deviation — no feature flag:** the gate is **unconditional**. The action-plan 2.2.4 body
  mentions "a cut-over flag with default on," but its own *Must be true* says "always, with no
  feature flag," and never-bend rule 5 is unconditional — built flagless, recorded in
  `plan-corrections.md`. Flip to a flagged cut-over only on owner request.
- **Independently verified (not just self-reported):** step 2 was implemented by a subagent, then
  reviewed against the actual diff and re-run — `make check` green on an independent run; the 14
  adjusted tests were audited for weakened assertions (none found; `test_versioning_swap` is
  strengthened; the 3 RLS tests keep their source-isolation asserts, only the orthogonal scope axis
  is opened); confirmed no code branches on `SyncOutcome.action`, so the new `skipped` is inert.

### ✅ Done — §13 step 3 (drop conflict D4 + rule 4 visibility + rule 3 guard + retire scope_state)

Rules satisfied: **4** (add a recognized tag → union it in, no re-embed, same version; shared tags
visible in each scope), **3** (remove one tag, another stays → metadata-only, no re-embed). Decision
**D4** implemented; `scope_state` retired.

- **Code:** `resolve_knowledge_scope_tags` (`domain/knowledge_scope.py`) now returns **all** matched
  recognized tags — the `conflict` field and the `provider_tags` branch are deleted from
  `KnowledgeScopeResult`. `sync_service.handle_sync_page` drops the `knowledge_scope_conflict`
  warning block; `final_tags` naturally unions both providers. Membership gate unchanged (still keys
  on `matched_labels`, which now equals `tags` for a shared page). `KnowledgeScopeResult` export
  unchanged.
- **`scope_state` retirement:** confirmed **zero code touch points** (no enum, no column, no
  consumer) across `backend/` + `knowledge-base/`; every mention was a test docstring/comment or
  design prose. State stays materialized as `tags` (ADR-0016). Retirement is a plan/design act only.
- **Tests (database):** new `test_sync_rules_visibility.py` — `test_tags_add_second_tag_updates_tags_no_reembed`,
  `test_tags_shared_page_visible_in_both_scopes`, `test_tags_general_tag_visible_everywhere` (guard),
  `test_tags_remove_shared_tag_keeps_other_scope`, `test_tags_remove_one_tag_keeps_page_updates_tags_no_reembed`
  (rule-3 guard). Inverted the three two-provider resolver unit tests in `test_knowledge_scope.py`
  (now `..._share_both_scopes_*`) and rewrote `test_ingestion_pipeline.py`'s conflict test to
  `test_two_provider_labels_share_all_scopes_no_conflict_log`. **Removed** the moot
  `test_s_audit_knowledge_scope_conflict_log_line_emitted_on_conflicting_labels` (that audit event no
  longer exists; s-audit's other two log lines keep their own tests). Red-today + guard-inversion
  proofs in `test-proof.md`.
- **Eval (Rule 11):** `make eval` before/after **byte-identical** (only the run label differs) → no
  gold-set regression. Caveat: the bundled baseline ranker doesn't route through knowledge-scope
  resolution, so it can't move on this change — the real visibility proof is the db+retrieval tests.
- **Docs/panels:** `today` lines updated on `tg-two`/`tg-conflict`/`tg-state`/`i2-labels` (status
  flips + target reconciliation batched to step 6, mirroring steps 1–2); corrections in
  `plan-corrections.md` (incl. 2.2.3 retired/absorbed, 2.5.1 re-scoped to the D3 backfill);
  coverage-map rows added; `deletion-and-purge.md` conflict wording corrected; brief regenerated.
- **Gate:** `make check` green (backend **939** passed, kb **41**, boundaries 0); ruff/format clean
  on touched files; whole-repo pyright unchanged (47; the 3 pre-existing `PageHashes bytes|None`
  errors in `sync_service.py` are present at HEAD, outside this diff — ADR-0003 D1 holds).
- **Security (RLS/visibility touch):** the change strictly **tightens** isolation — the old
  conflict→empty-tags path let a two-provider page reach *every* scope via the RLS empty-tags floor;
  now it carries real tags and is visible only in its own scopes. The residual empty-tags=public
  floor (any regression to empty tags) is closed defence-in-depth by D3 in step 4. No HTTP endpoint,
  LLM call, or outbound network was modified.

### ✅ Done — §13 step 4 (RLS floor fail-closed D3 + read-path overlap D4)

Rules satisfied: cross-cutting **3.4.1 / r3-scope** (empty tags visible to no scope; read paths use
`tags && allowed_scopes` overlap, not equality). Decision **D3** implemented; **Q-A** resolved.

- **Code:** `apply_chunk_scope_rls` (`knowledge-base/schema/schema.py`) drops the
  `OR cardinality(tags) = 0` clause — `chunk_scope_read` is now pure `'*'` opt-out **OR** `tags &&
  string_to_array(scope_guc)`; docstring rewritten to the fail-closed posture. `apply_curated_scope_rls`
  **unchanged** (curated keeps its floor, D3). New migration
  `knowledge-base/migrations/versions/0014_chunk_scope_fail_closed.py` — self-contained raw DDL (so
  the downgrade restores the pre-0014 with-floor policy even though the helper is now floor-less),
  `down_revision = 0013_reindex_progress`. The DB test harness applies RLS via
  `schema.apply_chunk_scope_rls` (`db_harness.py:146`), not alembic, so the schema edit is what the
  sec tests exercise; the migration round-trip is proven separately by the KB alembic-chain test.
- **Tests:** 2 new db tests in `test_customer_isolation_backstop.py` —
  `test_sec_empty_tags_visible_to_no_scope` (red today: `assert 18 == 0`; green after) and
  `test_sec_read_paths_use_overlap_not_equality` (green-today guard, inversion `&&`→`=` confirmed
  red then restored). The moot `test_scope_rls_untagged_chunk_is_global_visible_under_any_scope`
  (asserted the removed floor) was **rewritten in place** into the fail-closed test. 2 new
  reversibility tests in `knowledge-base/tests/test_migration_0014_chunk_scope_fail_closed.py`.
  Proofs in `test-proof.md`.
- **Q-A resolved (corrects the step-1 §0 note):** the flag default is **False** in both code and the
  test env — the step-1 "runs True" note was a misread (retrieval tests pass `True` directly to the
  `HybridRetriever` constructor, not via env). RLS fail-closed is flag-independent; the app-layer
  flag stays default-False, its flip deferred to PLAN 10.7's operator `.env` (`test_settings.py:49-51`).
  No default change. Eval before/after byte-identical (fixture ranker runs under `'*'`, can't move).
- **Docs/panels:** `r3-scope`/`i2-labels` today-lines updated (status flips + target reconciliation
  batched to step 6 — `r3-scope`'s target still names the retired `scope_state='ok'` conjunct, not
  edited in place); `plan-corrections.md` step-4 section; `coverage-map.md` rows; brief regenerated.
- **Gate:** `make check` green (backend **940**, kb **43**, boundaries 0); ruff/format clean on the 3
  touched files; whole-repo pyright unchanged at **47** (ADR-0003 D1 holds).
- **Security (RLS touch):** strictly **tightening** — dropping an `OR` clause only reduces
  visibility; empty tags now reach no scope; unset GUC still denies; `'*'` opt-out kept for the
  trusted eval/parent path only; curated untouched; RLS `ENABLE`d, never disabled/forced. No HTTP
  endpoint, LLM call, or outbound network modified.
- **Live/Q-B deferred (owner-blocked):** applying 0014 to Supabase + the pre-deploy empty-tags
  backfill audit (Q-B) need the owner; the `r3-scope` **live** leg stays outstanding.

### ✅ Done — §13 step 5 (rule 6: no reuse + title rebuild + retain 0)

Rules satisfied: **6** (a rebuild embeds the whole page, no vector reused). Decisions **D1** (retain
0, kill rollback) and **D2** (attachments deferred, strict xfail) implemented. Panels `i3-embed`,
`i2-rebuild`, `i4-gc`, `vd-swap` today-lines updated (status flips batched to step 6).

- **Code:** `versioning.py` — `DEFAULT_RETAIN_SUPERSEDED` 2→0; `_resolve_children` re-embeds every
  child (dropped `diff_chunks`/reuse); removed the `old_children` threading, `reusable_active_children`,
  `_pipeline_config_matches`, and `rollback_to`. `sync_service.py` — `ChangeClass.title_changed`
  added to `_REBUILD_CLASSES` (a rename rebuilds; safe on `uq_document_version_idem` — a title edit
  bumps `cf_version`). `ingestion/__init__.py` + `FEATURES.md` — reuse/rollback dropped from the
  public surface. `.github/workflows/ci.yml` — attachment strict-xfail added to the test-db
  allow-list (dead `test_delete_marks_the_active_version_superseded` name removed).
- **Tests (database):** `test_sync_rules_rebuild.py` — `test_in3_body_edit_reembeds_every_chunk_no_reuse`,
  `test_in3_title_change_reembeds_every_chunk`, `test_in3_rebuild_deletes_old_version_rows_immediately`,
  `test_in3_attachment_edit_reembeds_page` (**strict xfail**, needs 2.4.1). Ripple rewrites (not
  weakened): `test_versioning_gc.py` (retain 0), `test_versioning_swap.py`, `test_worker_sync.py`
  (vd-swap + `count_versions==1`), `test_reindex.py`, `test_attachment_wiring.py`. Retired:
  `test_pipeline_reuse.py`, `test_versioning_rollback.py`, `test_reuse_guard_disables_on_config_change`.
- **Deviation (cut-depth):** removed the dead reuse *wiring* but **retained** the pure `chunk_diff`
  domain leaf + its test (now unused, deferred removal). `rollback_to` removed outright (retain 0
  leaves no target; rule 11 forbids an untested exported fn). Status flips batched to step 6.
- **Gate:** `make check` green (backend 935 passed + 1 xfailed, kb 43, boundaries 0); ruff/format
  clean on touched files; whole-repo pyright net-decreased 47→44 (ADR-0003 D1 holds). See §0 ledger.

### ✅ Done — §13 step 6 (rule 5 positive guard + rule 8 invariant + finalise)

Rules satisfied: **5** positive half (first recognized tag on an untagged page → full build; the
negative half landed in step 2), **8** (a change to one page never touches another's rows).

- **Tests (database):** `test_in2_first_relevant_tag_full_build` (panel ks-index) added to
  `test_sync_rules_membership.py`; `test_in2_change_never_touches_other_pages_rows` (panel vd-swap) in
  the new `test_sync_rules_isolation.py`. Both green-today guards, each proven real by the 0.2.8
  revert method (rule 5: invert the membership gate; rule 8: drop the `page_id` scope on the version
  delete in `purge_page`) — production-file checksums matched before/after (no residue). Proofs in
  `test-proof.md`. No production code changed.
- **Docs finalised:** `coverage-map.md` + `test-proof.md` step-6 sections; **created**
  `manual-tests.md` (MT-1..MT-7, each mapped to its automated mirror + `verify_sync_rules.py` live
  coverage, honest that the live scripts are owner-blocked/unwritten); `plan-corrections.md` step-6
  section recording the batched status flips + everything deliberately left undone.
- **Design-page statuses flipped** (`obi-rag-system-flow.html`, via `panel.py`): `i2-gone`,
  `tg-purge`, `i2-labels`, `i3-embed`, `i2-rebuild`, `tg-two` → **built**; `tg-conflict`/`tg-state`
  (retired) + `tg-deactivate` (narrowed) today-lines finalised. Brief regenerated (192 panels).
- **Gate:** `make check` green (backend 937 passed + 1 xfailed, kb 43, boundaries 0); ruff/pyright
  clean on the touched test files; whole-repo pyright unchanged at 44 (ADR-0003 D1 holds).
- **Deliberately NOT done (owner-blocked / workflow-constrained) — see the step-6 ledger entry:**
  design-page **target** lines left stale (workflow forbids editing a target line; tracked in
  `plan-corrections.md`); `tg-conflict`/`tg-state` status unchanged (no `retired` status word);
  action-plan checkboxes for 2.2.4/2.3.1 **not ticked** (each names a live proof that is owner-blocked);
  the live scripts + Q-B backfill + 0014-to-Supabase remain outstanding.
  - **→ Update (2026-09-25):** most of this tail has since been cleared — **0014 applied to Supabase**,
    **Q-B census clean**, **target lines reconciled** (owner go-ahead; 7 panels), and the
    **verify_sync_rules.py automated leg passed** on prod. Only the **two manual live rules (1 delete,
    6 edit)** and the **2.2.4/2.3.1 checkboxes** remain. See §0.

### Cross-cutting deliverables still outstanding (§9, §12)

- **Scripts (live level):** `backend/scripts/page_state.py` (read-only page dump) and
  `backend/scripts/verify_sync_rules.py` (staging runner, MT-1..MT-7). ✅ **Written (2026-09-24).**
  `page_state.py` is tested (`test_page_state_script.py`, 3 db tests) and runs against any DB, no
  secrets. `verify_sync_rules.py` mirrors `verify_knowledge_scope_live.py`: it auto-drives the
  label-based rules (2/3/4/5/7) via the v1 label API and prompts for the physical trash/restore
  (rule 1) and body/title edit (rule 6); it refuses the offline fixture and requires `--yes`. Like
  its sibling live script it has no hermetic test (network + credentials). **Automated leg RUN
  2026-09-25** on the real prod test pages (owner-authorized; no staging): `--no-manual --scope-a
  obi-toast-test --scope-b obi-mews-test` → rules **2/3/4/5/7 + rule 8 all PASS**, labels restored,
  page rebuilt clean (retain-0); output in `backend/sync-rules-run.txt`. The script is self-contained
  (no API server / worker / webhook needed — it enqueues+drains jobs in-process), so
  `CONFLUENCE_WEBHOOK_SECRET` is **not** needed to run it. **Still outstanding:** the two manual rules
  **1** (trash/restore) and **6** (body/title edit) — interactive Confluence-UI steps, owner-run.
- **`docs/Final_docs/sync-rules/manual-tests.md`** (MT-1..MT-7 human procedures) — ✅ **written
  (step 6).** Each MT maps to its automated mirror + whether `verify_sync_rules.py` covers it live;
  it flags that the two live scripts below are unwritten/owner-blocked. **Running** the procedures
  live still needs staging (below).
- **Migration `0014`** — ✅ **written (step 4) and APPLIED to Supabase (2026-09-25)**:
  `0014_chunk_scope_fail_closed.py`, reversible, round-trip proven by
  `knowledge-base/tests/test_migration_0014_chunk_scope_fail_closed.py`. `alembic upgrade head` moved
  the live DB from `0012` → `0013` → `0014 (head)`; Q-B census was 0 first; 3d/3e live proofs passed
  (see §0 Remaining-work #1). The fail-closed floor is now live on production.
- **CI xfail allow-list (§14.8):** ✅ **done (step 5).** `.github/workflows/ci.yml`'s test-db
  allow-list now names `test_in3_attachment_edit_reembeds_page` (the D2 strict xfail); the dead
  `test_delete_marks_the_active_version_superseded` name was removed, and the test-unit guard now
  allows no xfail (that suite has none). Remove the attachment name when 2.4.1 lands (it will XPASS).

### Open questions status

- **Q-A (enable `enable_knowledge_scope_filtering`).** ✅ **Resolved (step 4): no default change.**
  The step-1 "test env runs True" note was a **misread** — the code default *and* the test-env
  default are **False** (`settings.py:281`; `test_settings.py:56-57`; `conftest.py` never sets it).
  Retrieval tests pass `True` directly to the `HybridRetriever` constructor, not via env. RLS
  fail-closed is the flag-independent security boundary; the app-layer flag stays default-False, its
  flip deferred to PLAN 10.7's operator `.env` (`test_settings.py:49-51`). Eval byte-identical.
- **Q-B (empty-tags backfill before the floor flip).** ✅ **Resolved at deploy (2026-09-25).** The
  census run immediately before `alembic upgrade head` returned **0 active chunks with `tags=[]`**, so
  no backfill was needed; 0014 was then applied and the live 3d proof confirmed empty tags are visible
  to no scope. No auto-mutation occurred.
- **Q-C (substep packaging).** Resolved: executing the §13 series one step at a time.

### Corrections/discoveries from steps 1–2 that affect later steps

- **D4 correction already applied:** `purge_page` **deletes `page_source`** (panels
  `tg-purge`/`tg-classified` as worded said "keep page_source with state classified" — that rested
  on the retired `scope_state`). Steps 2's rule-2 purge and the restore path both rely on
  `page_source` being gone → `get_local_state` returns `None` → first index. Logged in
  `plan-corrections.md`. This resolves the "fix the code to match rule 5" arm of the
  `live-0.5.3-cm-docs` decision-needed in `docs/plan/decisions.md`.
- **Boundary fix to §14.3:** the counting-embedder seam the appendix suggests (monkeypatch
  `ingestion.application.services.build_embedding_provider` from a confluence_sync test) **fails
  `make boundaries`** (cross-feature deep import). The legal seam used instead — reused by steps
  5/6 — is `install_counting_embedder` in `_helpers.py`: patch `build_ingestion_services` in the
  `sync_service` namespace and swap the embedder via `dataclasses.replace`.
- **Step 2 — the gate keys on `matched_labels`, not resolved `tags` (step 3 must preserve this):** a
  two-provider **conflict** page resolves to zero `tags` today yet still carries recognised
  `matched_labels`, so it stays indexed rather than being purged and immediately re-indexed. When
  step 3 drops the conflict branch (conflict resolves to *both* tags), **keep the discriminator on
  `matched_labels`** — the gate stays correct and never churns a legitimately-shared page.
- **Step 2 — three RLS tests + one script test now lean on the empty-tags floor (step 4 must
  revisit):** `test_force_rls_managed_postgres`, `test_reader_rls_reconcile` and `test_retrieval_eval`
  open the orthogonal knowledge-scope axis with the `'*'` wildcard (they assert **source**-axis
  isolation only), and `test_verify_isolation_script` **forces empty tags via SQL** to still hit the
  script's legacy untagged-corpus branch. When step 4 makes the RLS floor fail-closed (D3) and runs
  the Q-B empty-tags backfill, **re-examine all four** — the forced-empty-tags branch may become
  unreachable and the `'*'` opt-outs may need a real per-scope value.
- **Step 2 — `SyncOutcome.action` gained `skipped` (first-seen unlabeled); step 1 added `purged`.**
  No non-test code branches on `.action` (verified), so both are safe additive labels; the
  worker/event surfaces just record them.

---

## 1. Context — why this change

Three facts, all verified in code with file:line, drive this work:

1. **"Remove the last tag" is an active cross-scope leak today, not a cosmetic state.** The chunk
   RLS policy has an *empty-tags-means-public* floor — `chunk_scope_read` includes
   `OR cardinality(tags) = 0` (`knowledge-base/schema/schema.py:116-123`, floor on line 120). Because
   `enable_knowledge_scope_filtering` defaults to **False** (`backend/app/platform/config/settings.py:281`,
   wired `backend/app/main.py:77-88`), the app-layer overlap predicate is skipped and **RLS is the only
   scope gate**. So an active chunk with `tags=[]` is returned to *every* scope (mews, toast,
   operacloud, general). A Toast page whose last tag is removed becomes readable by Mews users today.

2. **Delete/trash/archive only hides, it does not remove.** `deactivate_page`
   (`backend/app/features/ingestion/application/versioning.py:402-416`) sets `is_active=False` and
   leaves every chunk, version, document and registry row on disk. "Hidden" chunks still carry their
   vectors and text.

3. **Restore-from-trash is already broken.** `page_restored`/`page_unarchived` are subscribed and
   route to `sync_page` (`schemas/events.py:22-23`, `event_service.py:93-104`), but the handler takes
   the metadata-only branch (`status_changed` ∉ `_REBUILD_CLASSES`, `sync_service.py:36-43,188-196`)
   and **never re-sets `is_active=True`** — only `stage_and_activate` (`versioning.py:344`) and
   `rollback_to` (`versioning.py:440`) do. A restored page stays dead until a body edit or pipeline
   bump forces a rebuild.

The owner specified eight rules for what the vector store must do on each Confluence change, and
settled four design decisions (§2). Intended outcome: **the database contents exactly match the eight
rules, empty-tags can never be reached on an active chunk, and the RLS floor is fail-closed so the
leak cannot recur.**

---

## 2. Decisions taken (owner-confirmed)

| # | Decision | Effect |
|---|---|---|
| D1 | **Kill rollback (retain 0).** | Rule 6 deletes the page's old `document_version` rows in the same txn as the swap; chunks cascade. `i4-gc` retain changes 2→0; substep `2.4.3` rollback is retired. |
| D2 | **Attachments deferred, tracked by a strict xfail.** | Rule 6 rebuilds on **body + title** now. Attachment-only rebuild is blocked by the version-identity collision (`sync_service.py:44-55`) and belongs to existing substeps **2.2.1** (fingerprint incl. attachment manifest) + **2.4.1** (version uniqueness on document+fingerprint, migration 0011). Write the attachment-swap test now, marked **strict xfail** with reason "needs 2.4.1", so it flips to passing when 2.4.1 lands and nobody forgets. |
| D3 | **Flip the chunk RLS floor to fail-closed.** | Remove `OR cardinality(tags) = 0` from `chunk_scope_read`. Empty tags → visible to no scope. Curated floor (`curated_knowledge_entry_scope_read`, `schema.py:143-151`) stays as-is (operator-authored, intentionally global). |
| D4 | **Drop the conflict rule entirely.** | Two+ platform tags on one page is *legitimate sharing*, enforced by plain overlap (`tags && allowed_scopes`). `[mews,toast]` → visible in mews and toast, not operacloud. `[general,toast]` → visible everywhere (general is seeded into every user's scopes). "Public" is the explicit `general` tag, **never** empty tags. This retires `scope_state`; rewrites what `3.4.1` checks (§7). |

---

## 3. The model after this change (so the rules cohere)

- **Membership** (is the page in the index at all): the page is published/current **and** carries at
  least one recognised knowledge-scope tag from `knowledge-base/config/knowledge_scopes.json`
  (the canonical allowlist — mews, toast, operacloud, general; `classified` is reserved and excluded
  from the offerable set, `knowledge_scopes.py:36,42,69-76`). Folder roots / `source_scope` do **not**
  decide membership (per substep 2.2.4).
- **Visibility** (which scopes can retrieve it): plain overlap `chunk.tags && allowed_scopes`, applied
  identically at the RLS layer and every app read path. **Empty tags overlap nothing → visible to
  nobody** (D3). "Everyone" is expressed as the explicit `general` tag, which is in every user's
  allowed scopes.
- **No conflict concept.** Multiple recognised tags = shared across those scopes.
- **No unreachable empty-active state.** Rules 1/2/5/7 guarantee every active chunk carries ≥1
  recognised tag; D3 makes the floor fail-closed as defence-in-depth if that ever regresses.

---

## 4. Confirmed ground truth (today's behaviour, file:line)

| Area | Today | file:line |
|---|---|---|
| Delete/trash/archive | soft: `is_active=False`, rows stay | `versioning.py:402-416`; route `event_service.py:81-92` → `sync_service.py:263-265` |
| Remove a tag (incl. last) | metadata-only: `chunk.tags` rewritten, rows stay active | `sync_service.py:188-196,268-302`; class `labels_changed` `change_detection.py:193-194` |
| Add a tag (≥1 exists) | metadata-only, same version id, no re-embed | same as above |
| Two provider tags | conflict → zero label tags → (floor) **public** | `knowledge_scope.py:29-30`; `sync_service.py:108-115`; floor `schema.py:120` |
| First tag / first index | full build, all children embedded | `change_detection.py:140-144` → `sync_service.py:145` → `stage_and_activate` |
| Body edit | rebuild, but **reuses** unchanged-chunk vectors via `diff_chunks` | `chunk_diff.py:56-113`; `versioning.py:149-184` |
| Title edit | metadata-only (`title_changed` ∉ rebuild set) | `change_detection.py:189-190`; `sync_service.py:36-43` |
| Attachment edit | metadata-only; cannot stage a new version at same cf_version | `sync_service.py:44-55` |
| Old versions | retain 2 superseded, older cascade-deleted | `_gc_superseded` `versioning.py:378-399` |
| `classified` label | **no delete path** — only a reserved scope name in config | `knowledge_scopes.py:36`; `platforms.py:33` |
| RLS floor | empty tags = visible to all; flag-off = RLS-only | `schema.py:116-123`; retriever `retriever.py:129-147` |
| Read paths use overlap? | yes (`&&`) at RLS + app (flag-on) + curated | `search_repo.py:79-97`; `curated_knowledge_repo.py:25-40` |
| Restore-from-trash | re-stamps `page_status=current`, never re-activates | `sync_service.py:268-302` (no `is_active` write) |
| Whole-page hard-delete helper | **does not exist** | grep clean; only `_gc_superseded` deletes rows |
| FK topology for a purge | `chunk.doc_version_id`→`document_version` ON DELETE CASCADE; `page_restriction.page_id`→`page_source` ON DELETE CASCADE; `document_version.document_id`→`document` **no** cascade; `page_source.active_doc_version_id`→`document_version` UNIQUE deferrable pointer | `models.py:262,174,203,114-118` |

**Purge order (single txn), reused by rules 1/2/7:** null `page_source.active_doc_version_id` →
`DELETE FROM document_version WHERE page_id=X` (chunks cascade) → `DELETE FROM document WHERE
page_id=X` → `DELETE FROM page_source WHERE page_id=X` (page_restriction cascades). `event_ledger`
rows are left as audit history (no FK to page_source).

---

## 5. New/changed code (the shared building blocks)

1. **`purge_page(session, *, page_id)`** — new function in `versioning.py`, next to `deactivate_page`.
   Ordered single-txn delete above. Returns whether a row existed. Exported through the ingestion
   feature root so `confluence_sync` reaches it at the boundary.
2. **Rebuild-trigger widening** — add `ChangeClass.title_changed` to `_REBUILD_CLASSES`
   (`sync_service.py:36-43`). Attachment stays out until 2.4.1 (D2).
3. **Remove vector reuse** — `_resolve_children` (`versioning.py:149-184`) stops consulting
   `diff_chunks` for embedding reuse; every child is contextualised + embedded on every rebuild
   (substep **2.3.1**).
4. **retain 0** — `stage_and_activate` calls `_gc_superseded(..., retain=0)` (or purges the
   just-superseded version) so no superseded rows survive the swap (D1; `versioning.py:254,378-399`).
5. **classified purge** — in `handle_sync_page`, detect the reserved `classified` label explicitly
   (before scope resolution) and call `purge_page`; return a `purged` outcome (rule 7).
6. **last-tag / no-tag purge** — in `handle_sync_page`, after `final_tags` is computed: if an
   already-indexed page ends with no recognised tag → `purge_page` instead of metadata-only (rule 2 +
   membership). First-index with no tag → never indexed (rule 5 requires a tag).
7. **drop conflict** — `resolve_knowledge_scope_tags` (`knowledge_scope.py:24-31`) returns all matched
   recognised tags, no `conflict` flag; delete the conflict branch and the `knowledge_scope_conflict`
   warning (`sync_service.py:108-114`). `scope_state` is not introduced.
8. **RLS floor flip** — new migration `0014_chunk_scope_fail_closed.py` DROP/CREATE `chunk_scope_read`
   without the `cardinality(tags)=0` clause; mirror in `schema.py:116-123` so the harness DDL matches.
   Curated policy untouched.
9. **delete_page → purge** — `handle_delete_page` (`sync_service.py:263-265`) and the `meta is None`
   path (`sync_service.py:87-91`) call `purge_page` instead of `deactivate_page` (rule 1). Restore then
   works for free: with `page_source` gone, a later `page_restored`/sweep sees `local is None` →
   first-index full build (documented + tested, §6 rule 1b).

**Open recommendation (§11 Q-A):** also set `enable_knowledge_scope_filtering=True` so the app read
paths enforce overlap alongside RLS ("every read path uses overlap", D4). Gated behind an eval run
(Rule 11).

---

## 6. Per-rule plan

Format: **today** (file:line) · **change** · **files** · **test-first** (name · level · red/green today
· outcome asserted) · **risk** · **panels** (keep/changed/new).

### Rule 1 — Delete / trash / archive → delete its rows
- **Today:** soft deactivate (`versioning.py:402-416`).
- **Change:** route DELETE_EVENTS and the `meta is None` path to `purge_page` (§5.9).
- **Files:** `versioning.py` (+`purge_page`), `sync_service.py:87-91,263-265`, ingestion root export.
- **Test-first:** `test_in2_delete_page_removes_rows` · **db** · **red today** (rows remain) · asserts
  `chunk`, `document_version`, `document`, `page_source` counts for the page are **0** after a
  `delete_page` job through the fixture gateway. Docstring `panel i2-gone · rule 1`.
- **Rule 1b (restore):** `test_in2_delete_then_restore_full_rebuilds` · **db** · restore after purge →
  `local is None` → fresh version + `embed calls == child count`, page retrievable again.
- **Risk:** irreversible; a spurious trash webhook deletes real work (mitigated: restore re-indexes
  from Confluence, the source of truth). Detection latency if webhook is down (only the 14-day
  complete sweep catches an orphan) — pre-existing.
- **Panels:** `i2-gone` **changed**; `p2-s2_2-close-i2-gone` **changed**; `tg-purge`,`tg-deactivate`
  **new→built**; substep **2.2.4** **changed**.

### Rule 2 — Remove the last relevant tag → delete its rows (same as rule 1)
- **✅ Built (§13 step 2, 2026-09-24).** As-built differs from the spec below: the gate fires on
  `scope_result.matched_labels` **before** `final_tags` (not a post-`final_tags` branch), and the
  tests are `test_tags_remove_last_recognized_label_removes_rows` +
  `test_tags_unrelated_labels_alone_do_not_keep_page` in `test_sync_rules_membership.py`, docstring
  `panel tg-remove · rule 2` (not `tg-purge`). `knowledge_scope.py` was **not** changed. Panel
  `tg-remove` flipped build→built. See §0.
- **Today:** metadata-only, rows stay active with `tags=[]` → **leaks** (floor).
- **Change:** if an indexed page ends with no recognised tag → `purge_page` (§5.6).
- **Files:** `sync_service.py` (post-`final_tags` branch), `knowledge_scope.py`.
- **Test-first:** `test_tags_remove_last_relevant_tag_removes_rows` · **db** · **red today** · asserts 0
  rows for the page after `gateway.set_labels(id, [])` + sync. Docstring `panel tg-purge · rule 2`.
- **Risk:** a transient empty-label read from Confluence would purge a live page; mitigate by trusting
  only the authoritative label list per sync (already fetched fresh) and re-index on restore.
- **Panels:** `tg-remove` **new→built**; `i2-gone` **changed**; substep **2.2.4** **changed**.

### Rule 3 — Remove one relevant tag, another stays → update tags, no re-embed, same version id
- **Today:** already metadata-only and correct (`sync_service.py:188-196,299-301`).
- **Change:** **keep**; lock it in.
- **Test-first:** `test_tags_remove_one_tag_keeps_page_updates_tags_no_reembed` · **db** · **green today
  (guard)** · asserts `active_version(id)` unchanged **and** embed-call counter == 0 **and**
  `chunk.tags` == remaining set. 0.2.8 proof reverts the `chunk.tags` UPDATE (`sync_service.py:299-301`).
- **Panels:** substep **2.2.5** **keep/confirm**; `tg-change`,`tg-retag` **keep**.

### Rule 4 — Add a relevant tag when one exists → update tags, no re-embed, same version id
- **Today:** a **second provider** tag triggers conflict → `tags=[]` → public.
- **Change:** drop conflict (§5.7). Any added recognised tag is unioned in; metadata-only.
- **Files:** `knowledge_scope.py`, `sync_service.py:108-115`.
- **Test-first (behaviour, red today):**
  - `test_tags_add_second_tag_updates_tags_no_reembed` · **db** · both tags present, same version id, 0
    embed calls. (Red today: conflict → `tags=[]`.)
  - `test_tags_shared_page_visible_in_both_scopes` · **db+retrieval** · `[mews,toast]` found in mews and
    toast, **not** operacloud. (Red today: public → also found in operacloud.)
  - `test_tags_general_tag_visible_everywhere` · `[general,toast]` found under every scope.
  - `test_tags_remove_shared_tag_keeps_other_scope` · `[mews,toast]` − toast → mews-only, 0 embed calls.
- **Risk:** changes retrieval visibility of currently-conflicted pages → **eval before/after required**
  (Rule 11).
- **Panels:** `tg-two`,`tg-conflict`,`tg-state` **changed/retired**; `i2-labels`,`2.2.3`,`2.5.1`
  **changed**; recorded in `plan-corrections.md` (§8).

### Rule 5 — First relevant tag on an untagged page → full build
- **◑ Partly built (§13 step 2, 2026-09-24).** The **negative** half — the no-tag→no-index gate — is
  built: a first-seen page with no recognised label returns `SyncOutcome(action="skipped")` and
  writes no rows, proven by `test_in2_untagged_page_never_indexed` (panel `ks-index`). The
  **positive** guard `test_in2_first_relevant_tag_full_build` (first tag → full build, embed calls ==
  child count) is still **deferred to step 6** per §13.
- **Today:** already a full build on first index.
- **Change:** **keep**; ensure the no-tag→no-index gate (zero recognised tags → never first-indexed).
- **Test-first:** `test_in2_first_relevant_tag_full_build` · **db** · **green today (guard)** · version
  created **and** embed-call counter == child-chunk count. Plus `test_in2_untagged_page_never_indexed`
  (no rows when first-seen with no recognised tag).
- **Panels:** `ks-index` **keep**; substep **2.2.4** membership clause **changed**.

### Rule 6 — Edit (body / title / attachment) → rebuild whole page, embed every chunk, reuse no vector
- **Today:** body reuses vectors (`diff_chunks`); title = metadata-only; attachment can't version;
  retain 2.
- **Change:** remove reuse (§5.3, substep **2.3.1**); add `title_changed` to rebuild set (§5.2); retain
  0 (§5.4, D1). Attachment deferred (D2).
- **Files:** `versioning.py:149-184,254`, `sync_service.py:36-43`.
- **Test-first:**
  - `test_in3_body_edit_reembeds_every_chunk_no_reuse` · **unit/db** · **red today** (reuse → calls <
    count) · embed-call counter == child count after a one-word edit.
  - `test_in3_title_change_reembeds_every_chunk` · **db** · **red today** (title=metadata-only) · embed
    calls == child count after a rename.
  - `test_in3_rebuild_deletes_old_version_rows_immediately` · **db** · **red today** (retain 2) · after
    one edit, superseded/old `document_version` rows for the page == 0, old chunks == 0.
  - `test_in3_attachment_edit_reembeds_page` · **db** · **strict xfail** reason `"needs 2.4.1"` (D2) ·
    new version + full re-embed on an attachment-only change; flips to pass when 2.4.1 lands.
- **Risk:** full re-embed on every rename raises embedding cost (accepted per 2.3.1 — title is in the
  contextualised text, so correctness requires it); retain 0 removes the safety net (D1) — recovery is
  a fresh re-index.
- **Panels:** `i3-embed` **changed→built**; `i2-rebuild` **changed**; `i4-gc` **changed** (retain 0);
  `2.4.3` rollback **retired**; substep **2.3.1** **changed→built**; attachment → **2.2.1 / 2.4.1**.

### Rule 7 — Add `classified` → delete the rows
- **Today:** no path; `classified` is only a reserved config scope.
- **Change:** detect the `classified` label in `handle_sync_page` → `purge_page` (§5.5).
- **Test-first:** `test_in2_classified_label_removes_rows` · **db** · **red today** · 0 rows after
  `gateway.set_labels(id, ["classified", ...])` + sync.
- **Risk:** the config's reserved value must equal the Confluence label spelling — assert against
  `knowledge_scopes.json`.
- **Panels:** `i2-gone` **changed**; `tg-classified` **new→built**; substep **2.2.4** **changed**.

### Rule 8 — A page never touches another page's rows
- **Today:** already per-page.
- **Change:** **keep**; add an explicit invariant guard.
- **Test-first:** `test_in2_change_never_touches_other_pages_rows` · **db** · **green today (guard)** ·
  index A and B; edit **and** delete A; assert B's chunk ids, embeddings, tags, version id are
  byte-identical before/after.
- **Panels:** `vd-swap` **keep**.

### Cross-cutting — RLS floor fail-closed (D3) + read-path overlap (D4)
- **Change:** migration `0014_chunk_scope_fail_closed.py` + `schema.py` mirror (§5.8).
- **Test-first:** `test_sec_empty_tags_visible_to_no_scope` · **db** · **red today** (floor = public) ·
  as `rag_reader`, an active chunk with `tags=[]` returns for **no** scope value. Plus
  `test_sec_read_paths_use_overlap_not_equality` confirming dense/keyword/curated/parent all filter by
  `&&`. Docstring `panel 3.4.1 · D3/D4`.
- **Risk:** any legitimately-global content must now carry the explicit `general` tag; a backfill check
  may be needed before deploy (§11 Q-B).
- **Panels:** substep **3.4.1** **changed** (empty-tags = private + overlap, not public floor).

---

## 7. `scope_state`: retire it

With no conflict state (D4), `scope_state` would only ever hold `ok` → no job. **Drop `scope_state`
from the plan entirely** (no column, no RLS state predicate, no `tg-state` work). **`3.4.1`** now
checks: *empty tags are visible to no scope (fail-closed), and every read path (dense, keyword,
curated, parent) plus the RLS policy filter by `tags && allowed_scopes` overlap, not equality* —
covered by the Rule-4 visibility tests + `test_sec_*`.

---

## 8. Design-page corrections — `docs/Final_docs/0.4-design-review/plan-corrections.md` (new)

One entry per panel/substep the decisions move, each marked **changed/retired** with the reason:
`tg-two` (conflict→legitimate sharing), `tg-conflict` (retired), `tg-state`/`scope_state` (retired),
`i2-labels` (overlap visibility, empty=private), `2.2.3` (labels→tags, no conflict state), `2.5.1`
(shared tags), `i2-gone` (delete not deactivate; classified/last-tag purge), `i4-gc` (retain 0),
`2.4.3` (rollback retired), `3.4.1` (fail-closed floor), `2.3.1` (no reuse). Flip the `today` lines on
`obi-rag-system-flow.html` and the statuses on `obi-action-plan.html` when each substep lands.

---

## 9. Scripts

### `backend/scripts/page_state.py <page_id> [marker]` (new — manual testing)
Read-only session. Prints for one page: **active** and **inactive** chunk counts; the distinct `tags`
on its active chunks; `page_status` and `is_active` summary (*replaces* the requested `scope_state`,
which is being retired — §7, flagged so the substitution is explicit); every `document_version` id
with its `state` and `cf_version`; and, if `marker` is given, the count of the page's chunks whose
`display_content`/`retrieval_content` contains the marker word. No writes, no network. Uses the
read-only pattern from the tests' `_helpers.read()`.

### `backend/scripts/verify_sync_rules.py` (new — live, staging)
Refuses the offline fixture gateway (mirror `run_reconciliation_once.py:41-50`). Runs the Confluence
cases against staging with the owner's test pages, printing pass/fail per rule from `page_state`
readings: add first tag (5), add second/shared tag (4), remove one tag (3), remove last tag (2), edit
body+title (6), delete+restore (1), add classified (7). **Covers manual tests MT-1..MT-7** (§10).
Does **not** cover the attachment case (blocked, D2) or the RLS-floor unit assertion (db-only). Output
goes in the PR per CLAUDE.md live-level rule.

---

## 10. Tests, proof, coverage, CI

**One automated test per rule + manual mirror.** Every rule's fixture-gateway test runs with **no
Confluence** (`FixtureConfluenceGateway` + db harness, `conftest.py` + `_helpers.py`).
`docs/Final_docs/sync-rules/manual-tests.md` (new) lists MT-1..MT-7 as human procedures, each mapped
to its automated test name **and** whether `verify_sync_rules.py` covers it live. Assertions are
**outcomes, never code paths** — "0 chunk rows for this page", "same version id and 0 embed calls",
"embed calls == child count", "found in mews, not in operacloud".

**Embed-call counter.** `FakeEmbeddingProvider` (`embeddings_client.py:55`) has no counter. Add a thin
counting wrapper (increment per text in `embed`) as a test fixture, reused by rules 3/4/5/6.

**Prove each test real (the 0.2.8 way) → `docs/Final_docs/sync-rules/test-proof.md` (new).** For each
test: revert the one line it guards → run → **red** (record the reason), restore → **green**. Red-today
tests (1,2,4,6,7,RLS) already fail on current code — record that as the first half of the cycle;
green-today guards (3,5,8) use the revert step. Format copied from
`docs/Final_docs/0.2-agent-quality/test-writer-check.md`.

**Coverage map → `docs/Final_docs/0.5-regression-tests/coverage-map.md` (edit in place).** One row per
test in the existing columns `| panel | title | test file | test name | level | green |`. Panels:
`i2-gone`, `tg-purge`, `tg-remove`, `tg-retag`, `tg-add`, `i2-labels`, `ks-index`, `i3-embed`, `i4-gc`,
`i2-gone`(classified), `vd-swap`, `3.4.1`.

**CI (0.5.4) + xfail bookkeeping.** All tests land in `make test-unit` / `make test-db`, gated by the
`obi four-level check (0.5.1)` status (`.github/workflows/ci.yml`). Add the attachment strict-xfail
(`test_in3_attachment_edit_*`) to the workflow's xfail allow-list (the `grep -vF` lines) alongside the
existing `test_delete_marks_the_active_version_superseded`; when substep **2.2.4** retires that older
xfail, remove it from the allow-list (it will XPASS → CI red otherwise).

**Rules that cannot be tested automatically (with reason).**
- **Rule 6 attachment rebuild** — testable only as a **strict xfail** until 2.4.1 exists (version
  identity can't represent an attachment-only change today).
- **Live webhook delivery / detection latency** (signing gap; 14-day complete-sweep timing) — not
  unit-testable; covered by `verify_sync_rules.py` against staging, reported in the PR.

---

## 11. Open questions (recommended defaults)

- **Q-A — enable `enable_knowledge_scope_filtering`?** The app layer only applies overlap when this
  flag is **on** (default off; RLS-only today). **Recommend: turn it on** so both layers enforce
  overlap, **gated behind an eval before/after run** (Rule 11). If the eval regresses, ship RLS
  fail-closed alone and keep the flag off.
- **Q-B — backfill of existing empty-tags active chunks before the floor flip.** After D3, any page
  relying on empty-tags=public goes dark. **Recommend:** a one-off audit (list active chunks with
  `tags=[]`) on staging/prod before deploy; re-tag legitimately-global pages with `general`. Report the
  list in the PR; do not auto-mutate.
- **Q-C — substep packaging.** Spans 2.2.4, 2.2.5, 2.3.1, i2-gone, i4-gc, 3.4.1 and touches 2.2.1/2.4.1
  (pointer). **Recommend** the ordered series in §13, one substep + ledger entry at a time.

---

## 12. Deliverables (files created/edited on execution)

**New docs:** `docs/Final_docs/sync-rules/plan.md` (this file), `.../manual-tests.md`,
`.../test-proof.md`; `docs/Final_docs/0.4-design-review/plan-corrections.md`.
**Edited docs:** `docs/Final_docs/0.5-regression-tests/coverage-map.md`; design page
`obi-rag-system-flow.html` + `obi-action-plan.html` statuses/`today` lines; `docs/Final_docs/ledger.md`
+ `progress-log.md` (append per substep); relevant `docs/Final_docs/ingestion/` component docs.
**New scripts:** `backend/scripts/page_state.py`, `backend/scripts/verify_sync_rules.py`.
**New migration:** `knowledge-base/migrations/versions/0014_chunk_scope_fail_closed.py` (+ downgrade).
**Code:** `versioning.py` (`purge_page`, retain 0, no-reuse), `sync_service.py` (rebuild set, purge
branches, classified, drop conflict), `knowledge_scope.py` (drop conflict), `schema.py` (RLS mirror),
ingestion feature root export, `.github/workflows/ci.yml` (xfail allow-list), test files + counting
embedder fixture.

---

## 13. Execution order (each stops at green + ledger entry)

1. ✅ **DONE (2026-09-24)** — **purge_page + rule 1 + rule 7 + restore** (i2-gone; delete/classified
   purge; restore full build). See §0 and the ledger 2.2.4 entry.
2. ✅ **DONE (2026-09-24)** — **rule 2 + membership gate** (last-tag purge + no-tag skip; tg-remove,
   ks-index). See §0 and the ledger 2.2.4 (step 2) entry.
3. ✅ **DONE (2026-09-24)** — **drop conflict + rule 4 visibility + rule 3 guard** (retire
   scope_state; overlap tests). See §0 and the ledger 2.2.4 (step 3) entry.
4. ✅ **DONE (2026-09-24)** — **RLS floor fail-closed (migration 0014) + read-path overlap tests**
   (3.4.1); Q-A resolved (no default change). See §0 and the ledger 2.2.4 (step 4) entry.
5. ✅ **DONE (2026-09-24)** — **rule 6: no-reuse (2.3.1) + title rebuild + retain 0 (i4-gc)**;
   attachment strict-xfail (D2), rollback retired (D1). See §0 and the ledger 2.3.1 entry.
6. ✅ **DONE (2026-09-24)** — **rule 5 positive guard + rule 8 invariant**; finalised coverage-map,
   test-proof, created manual-tests; flipped design-page statuses. Live legs + target-line
   reconciliation + action-plan checkboxes remain owner-blocked. See §0 and the ledger 2.2.4 (step 6).

Before each: read the named panels + the component doc + ledger (CLAUDE.md). After each:
`make check` green, migration reversible, security review for endpoint/LLM/RLS touches, ledger +
progress-log entries, design-page `today` line flipped.

---

## 14. Execution appendix — exact APIs, DDL and formats (so this file stands alone)

> **Path caveat:** older proof docs (e.g. `0.2-agent-quality/test-writer-check.md`) cite
> `apps/automation/...` / `apps/web/...`. The tree has since moved. Trust the **live** layout:
> backend Python is under `backend/app/...`, tests under `backend/app/features/<feature>/tests/`.

### 14.1 DB-test harness (drive the real worker with no network)

All confluence_sync DB tests use `pytestmark = pytest.mark.db` at module top, the `gateway`/`settings`
fixtures from `backend/app/features/confluence_sync/tests/conftest.py` (autouse `_db_isolation`
truncates between tests), and the helpers in `backend/app/features/confluence_sync/tests/_helpers.py`:

```python
# _helpers.py public surface (import from ._helpers)
index_page(gateway, settings, page_id, version)   # seed a page via the REAL sync path
enqueue_sync(page_id, cf_version, key)             # push a sync_page job
enqueue_delete(page_id, status, key)               # push a delete_page job
run_worker(gateway, settings, owner="test")        # drain(...) up to 50 jobs
# worker.run_once(gateway, settings, owner=...) runs exactly one job (used by index_page)
read()                                             # fresh read-only Session (use as: `with read() as s:`)
active_version(page_id) -> DocumentVersion | None  # via PageSource.active_doc_version_id
active_versions_count(page_id) -> int              # DocumentVersion rows in state=active
active_child_chunks(page_id) -> list[Chunk]        # is_active AND kind=child
child_chunks_for_version(doc_version_id) -> list[Chunk]   # all child rows of a version, any is_active
restricted_principals(page_id) -> set[str]         # persisted ACL
count_versions(page_id) -> int                     # all DocumentVersion rows for the page
```

**Fixture gateway** `FixtureConfluenceGateway`
(`backend/app/platform/clients/fixture_confluence_client.py`) — in-memory mutators to express each
scenario (all keyed by int page_id, fixtures never written):

```python
gateway.set_version(page_id, version)      # advance cf version -> triggers a body-edit rebuild path
gateway.set_status(page_id, status)        # "current" | "archived" | "trashed" | "deleted" | "draft"
gateway.set_labels(page_id, [ ... ])       # REPLACES the page's label set (tag add/remove/last/classified)
gateway.set_restrictions(page_id, [ids])   # page read-restriction principals
gateway.set_group_members(group_id, [ids])
gateway.hide(page_id)  / gateway.unhide(page_id)   # get_page_meta/get_page -> None (deletion/lost access)
gateway.set_attachment_content(download_link, data|None)
```

**Scenario recipes (map rules → gateway calls):**
- Rule 1 delete: `index_page(...)`; `gateway.set_status(id,"trashed")` **or** `gateway.hide(id)`;
  `enqueue_delete(id,"trashed",key)`; `run_worker(...)`; assert **0** rows (see 14.2).
- Rule 1b restore: after the delete, `gateway.set_status(id,"current")` / `gateway.unhide(id)`;
  `enqueue_sync(id, version, key)`; `run_worker(...)`; assert a fresh version + full re-embed.
- Rule 2 last tag / Rule 7 classified: `gateway.set_labels(id, [])` (or `["classified"]`);
  `enqueue_sync(...)`; `run_worker(...)`; assert 0 rows.
- Rule 3/4 tag change: `gateway.set_labels(id, [<new set>])`; `enqueue_sync(...)`; `run_worker(...)`;
  assert `active_version(id)` unchanged + counter (14.3) shows 0 embed calls + `chunk.tags` updated.
- Rule 6 body edit: `gateway.set_version(id, v+1)` (a per-version fixture snapshot with changed body);
  Rule 6 title: same with a changed title; assert counter `.texts == len(active_child_chunks(id))`.

### 14.2 Asserting on rows (outcome, never code path)

```python
from sqlalchemy import func, select
from schema.models import Chunk, DocumentVersion, Document, PageSource
with read() as s:
    assert s.scalar(select(func.count()).select_from(Chunk).where(Chunk.page_id == pid)) == 0
    assert s.scalar(select(func.count()).select_from(DocumentVersion).where(DocumentVersion.page_id == pid)) == 0
    assert s.get(Document, ...) is None   # by page_id lookup
    assert s.get(PageSource, pid) is None
```
For "no reuse / embed every child" assert on the **counter** (14.3), not on chunk contents. For
"unchanged" (rules 3/4) assert `active_version(pid).id == version_before` and `counter.calls == 0`.

### 14.3 Counting embedder (there is no built-in counter)

`FakeEmbeddingProvider(dim, model="fake")` (`embeddings_client.py:55`) only exposes `dim`, `model`,
`embed(texts)->list[list[float]]`. Add a thin counting wrapper as a test fixture and inject it by
monkeypatching the build seam `build_embedding_provider` in
`backend/app/features/ingestion/application/services.py` (called by `build_ingestion_services`, which
`handle_sync_page` invokes each run):

```python
class CountingEmbedder:
    def __init__(self, inner):
        self.inner, self.model, self.dim = inner, inner.model, inner.dim
        self.calls = 0   # embed() invocations
        self.texts = 0   # total texts embedded == children (re)embedded this build
    def embed(self, texts):
        self.calls += 1; self.texts += len(texts)
        return self.inner.embed(texts)

# in the test: monkeypatch.setattr(services_mod, "build_embedding_provider",
#     lambda settings: counter)  where counter = CountingEmbedder(FakeEmbeddingProvider(dim=settings.embedding_dim))
```
Tests run with `EMBEDDING_PROVIDER=fake`, `EMBEDDING_DIM=256`, `CONTEXTUALIZATION_ENABLED=false`
(root `backend/conftest.py`). With reuse removed and contextualization off, a rebuild calls `embed`
once with all children — assert on **`counter.texts == child count`**, not `counter.calls`. For a
metadata-only path assert `counter.calls == 0`.

### 14.4 RLS floor flip — exact current vs target DDL

Current `chunk_scope_read` (`knowledge-base/schema/schema.py:116-123`, `apply_chunk_scope_rls`):
```sql
CREATE POLICY chunk_scope_read ON chunk AS RESTRICTIVE FOR SELECT
USING (current_setting('app.allowed_knowledge_scopes', true) = '*'
   OR cardinality(tags) = 0                                             -- << the public floor (remove)
   OR tags && string_to_array(current_setting('app.allowed_knowledge_scopes', true), ','));
```
Target (fail-closed — drop only the middle line; keep the `'*'` opt-out used by the parent-expansion
path, `retriever.py:247-259`, and eval):
```sql
CREATE POLICY chunk_scope_read ON chunk AS RESTRICTIVE FOR SELECT
USING (current_setting('app.allowed_knowledge_scopes', true) = '*'
   OR tags && string_to_array(current_setting('app.allowed_knowledge_scopes', true), ','));
```
Effect: empty tags → `tags && …` is false → denied; unset GUC → `string_to_array(NULL,',')` → NULL →
denied (already fail-closed). **Leave `apply_curated_scope_rls` (schema.py:143-151) unchanged** (D3).
Edit `apply_chunk_scope_rls` in `schema.py` to the target DDL (so the test harness `apply_*` matches),
and add migration `0014_chunk_scope_fail_closed.py`: **upgrade** DROP+CREATE the floor-less policy,
**downgrade** DROP+CREATE the current (with-floor) policy. Both are pure `conn.execute(text(...))`,
mirroring the existing `apply/drop_chunk_scope_rls` shape. RLS is `ENABLE`d but **NOT** `FORCE`d
(ADR-0013): the test must read as the non-owner `rag_reader` role for the policy to apply.

### 14.5 Naming + docstring convention (obi-test-writer)

- Name `test_<stage>_<behavior>`; the owner's spec fixes the stages used here: `in2` (delete/index),
  `in3` (rebuild/embed), `tags` (tag ops), `sec` (RLS/security). Match the prevailing prefix of
  sibling tests already in the target test file (grep first — a historical `in2→i2` rename exists;
  the docstring, not the prefix, is the source of truth for which panel is protected).
- Docstring: **line 1** `panel <id> · rule <n>` (e.g. `panel i2-gone · rule 1`); **line 2** the exact
  acceptance sentence being proved. Every regression test names the design panel it protects.

### 14.6 Coverage-map row format (`docs/Final_docs/0.5-regression-tests/coverage-map.md`, edit in place)

Columns: `| panel | title | test file | test name | level | green |`. Test file path is relative to
`backend/` (e.g. `app/features/confluence_sync/tests/test_sync_rules_delete.py`); multiple files
`; `-separated; extra tests summarised `(+N more: nameA, nameB)`; `level` ∈ unit|database; `green` =
`yes`/`no`. Example real row:
```
| `i4-gc` | Garbage collect old versions | app/features/ingestion/tests/test_versioning_gc.py | test_i4_gc_keeps_the_two_most_recent_superseded_versions | database | yes |
```

### 14.7 Proof format (`docs/Final_docs/sync-rules/test-proof.md`, new — the 0.2.8 method)

Per test: run unmodified → revert the **one** line its docstring names → rerun (confirm **red** for the
stated reason) → restore → rerun (confirm **green**); `git status --short` clean after. For red-today
tests (1,2,4,6,7,RLS) the "fails today" run **is** the red half — record it, then record green after
the change. One `### N — <panel>, <level>` block per test with a 3-row table:
```
| Step | Command | Result |
|---|---|---|
| Fails today / Passes today | uv run pytest <path>::<test> -v | FAILED (reason) / PASSED |
| Guard reverted / stub added | same | PASSED / FAILED |
| Restored | same | PASSED; git status clean |
```
Commands run with `DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag` exported
(overrides the root `.env`'s Supabase URL — never edit `.env`).

### 14.8 CI xfail-allowlist mechanics (`.github/workflows/ci.yml`)

Both the `make test-unit` and `make test-db` steps run with `PYTEST_ADDOPTS: "-rsxX"` and a skip-guard
that fails the job on any `SKIPPED`, any `XPASS`, or any `XFAIL` **except** an allowlisted name. The
allowlist is a single `grep -vF` per step (currently only the tg-deactivate test):
```bash
unexpected="$(grep -E '^XFAIL ' "$log" | grep -vF 'test_delete_marks_the_active_version_superseded' || true)"
```
To add the attachment strict-xfail (D2), extend **both** steps (unit ~line 89, db ~line 114) to also
exclude it, e.g.:
```bash
unexpected="$(grep -E '^XFAIL ' "$log" \
  | grep -vF 'test_delete_marks_the_active_version_superseded' \
  | grep -vF 'test_in3_attachment_edit_reembeds_page' || true)"
```
Mark that test `@pytest.mark.xfail(reason="needs 2.4.1", strict=True)`. When substep 2.2.4 lands and
retires the tg-deactivate xfail, remove **its** `grep -vF` line (it will XPASS → CI red otherwise).

## 15 · Open follow-up: meerdere scopes per vraag (POS + PMS tegelijk) — eerst beslissen, dan bouwen

Jasper's veldvraag (2026-10-01): een property draait vaak een POS én een PMS tegelijk (bijv. Toast +
Opera Cloud), maar een vraag draait vandaag onder precies één platform-scope — het token en de
`/chat`-request dragen één `knowledge_scope`-string, die `resolve_allowed_scopes` aanvult met
`obi-general-test`. De datalaag kan het al (pagina's dragen meerdere tags, de zoeklaag filtert op een
scopes-*set*), dus de uitbreiding zit in de token-claim en de gate, niet in de opslag.

**Eerst kort beslissen hoe we dit exact willen** voordat er iets gebouwd wordt — de open keuzes:
1. Lijst in de token-claim (`knowledge_scopes: [toast, operacloud]`) vs. één scope met voorrangsregel.
2. Zoekgedrag bij een lijst: één gefuseerde zoekronde over de unie van scopes, of per scope en fuseren.
3. Wat de citations/trace tonen als bronnen uit verschillende scopes komen.
4. Backwards-compat: blijft de enkelvoudige claim geldig (lijst van één) zodat bestaande platforms niet breken.

Daarna pas implementeren: claim + gate + `resolve_allowed_scopes` een set laten accepteren, met test
per keuze. Status: **Decision needed** (owner) — nog niet gepland in de actieplan-substeps.

### 15.1 · Harde voorwaarde vóór de multi-scope bouw: eerst een rotsvast testfundament

Dit is géén kleine wijziging: meerdere scopes per vraag (bijv. Toast + Mews/Opera tegelijk) raakt
meer dan de token-claim alleen. Bekende implicaties, elk met eigen testbehoefte:
- **Autorisatie/RLS** — de scopes-set in de authorization context stuurt élke databaseread (search,
  rerank-tekst, parent-expansie, curated lookup); een lijst mag nooit breder resolven dan het token.
- **Isolatie** — een Toast+Opera-gebruiker mag nóóit een Mews-only pagina zien; de adversariële
  kant (gemanipuleerde body-scope, onbekende scope in de lijst, lege lijst) moet fail-closed blijven.
- **Retrieval-gedrag** — fusie/ranking over de unie van scopes, deduplicatie als een pagina in twee
  scopes leeft, citations en trace bij bronnen uit verschillende scopes.
- **Caching & limits** — antwoordcache-keys en rate-limits zijn vandaag per (principal, scope);
  een lijst verandert de key-ruimte.
- **Eval** — rule 11 geldt: geen retrieval-wijziging zonder voor/na-cijfer op de gold set.

**Afspraak (owner, 2026-10-02): vóór er ook maar één regel multi-scope-code geschreven wordt, komt
er een rock-solid testsuite** — eerst de huidige single-scope contracten als regressievloer
vastklikken, daarna red-first tests voor het besliste multi-scope-gedrag (§15-keuzes 1–4). De
testscope zelf wordt met de owner afgestemd (vragenronde) en als testplan hier vastgelegd.

### 15.2 · Het testplan (owner-afgestemd 2026-10-02): de regressievloer vóór multi-scope

> **2026-10-05 — waar dit nu leeft:** de golven 0–4 hieronder zijn als substappen 4.1–4.5 in de
> roadmap opgenomen (`docs/Final_docs/plan.md` §A, stap 4); golf 5 is vervangen door roadmap-stap 5
> (het volledige multi-integratie-ontwerp, §D aldaar) + stap 6 (de agent-gebouwde testuitbreiding).
> De §15-keuzes 1–4 worden beslist in het beslismemo van §D.1. Dit blok blijft staan als record van
> de owner-afspraak; de roadmap is leidend voor de volgorde.
>
> **Status 2026-10-05:** golf 0 (= substap 4.1, baselines in `docs/plan/baseline.md`) en golf 1
> (= substap 4.2, audit + 25 gap-dichtende tests + de G14 scope-waarde-fix in
> `docs/Final_docs/4-test-foundation/`) zijn **afgerond**.
>
> **Status 2026-10-05 (later die dag):** golf 2 (= substap 4.3) is **gebouwd** —
> `backend/scripts/webhook_rules_live.py`, de permanente webhook-pad-runner (alleen echte
> Confluence-REST-mutaties, pollt de DB tot de gedeployde keten het werk deed, event-ledger-bewijs
> per leg, rule-8-getuige, labels + body hersteld in een `finally`); de **live run zelf is
> owner-only** (zie de ledger-entry 4.3 "need from you"). Golf 4 (= 4.5) is als before-gate
> bevestigd (byte-identiek aan de 4.1-baseline). Golf 3 (= 4.4) is de owner's browsercheck
> (ledger "4.4 · need from you"); de Playwright-automatisering ervan blijft roadmap-stap 6.
> Ook 4.6–4.8 (verify-state-staart) zijn klaar: live proofs read-only herbevestigd, de laatste
> vier `unverified`-panelen geflipt, en de 2.2.4/2.3.1-checkboxes getickt op het 2026-09-30-bewijs.
>
> **Status 2026-10-05 (slot): STAP 4 VOLLEDIG AFGEROND.** De live run van `webhook_rules_live.py`
> is owner-ordered uitgevoerd en **alle 8 regels PASS** door het echte webhookpad (output
> `backend/webhook-rules-live-run.txt`; de eerste run ving een echte restore-API-bug, gefixt —
> ledger "4.3-addendum"). De owner's browserchecks (golf 3 / 4.4) zijn **gedaan en geslaagd**;
> de screenshot-bewijzen staan in `docs/Final_docs/4-test-foundation/browser-checks-4.4/`.
> Bonus: X1 (Supabase-guards op de 0010/0014-downgrades) is besloten en gebouwd (4 hermetische
> tests; kb-suite 49). Volgende: roadmap-stap 5 — het multi-integratie-ontwerp (§D), op go-ahead.
>
> **Status 2026-10-05 (avond): stap 5 is gestart — §D.0 (de scope-restamp-fix, findings A+B van
> 2026-10-03) is AF** (commit `41fc248`, ledger "D.0"): de handler vergelijkt `cmd.scopes` met de
> gestempelde tags en herstempelt metadata-only; het B-lek is op RLS-niveau dicht bewezen onder
> `rag_reader`; beide sentinel-tests bewust red-first omgeklapt; `make check` + eval groen. X2 is
> ook af en gecommit (`f480b32`). Open owner-call: het archive-fires-no-webhook-gat (aanbeveling
> in de D.0-ledger-entry). Volgende substap: §D.1 — het beslismemo dat de §15-keuzes 1–4 beslist,
> eerst de owner/Jasper-feiten (Base ≤3 vs Data Hub ≤2 aansluitingen; customer-id als company_id).

Owner-keuzes uit de vragenronde: (1) eerst de **regressievloer** — het huidige single-scope gedrag
vastklikken; multi-scope red-first tests wachten op de §15-beslissing; (2) contract **nog niet
beslist** — er komt eerst een kort beslismemo; (3) alle vier de niveaus: unit+database (CI-gate),
een permanent live-webhook-script, browser (Playwright) én eval/gold-set; (4) diepste dekking op
**security & isolatie + sync-correctheid + "werkt het écht"** (end-to-end realiteit boven mocks).

De golven, in volgorde:

- **Golf 0 — baselines bevriezen (vóór élke codewijziging).** `make eval` per stage draaien en de
  cijfers vastleggen (rule 11 heeft een "voor" nodig); `make check`-tellingen noteren
  (nu: boundaries 0 · backend 1015+1xfail · kb 45).
- **Golf 1 — dekkingaudit + gaten dichten (unit + database, de CI-vloer).** Stap 1: audit die élk
  contract mapt op een bestaande test (obi-auditor, lezen-alleen): de 8 sync-regels, event-dedup
  (payload_hash + delivery_id), idempotency-keys-per-event (f8098d0), de autorisatiecontext
  (onbekende scope → 400 vóór search; body/token-conflict → genegeerd + gelogd; elke read onder
  dezelfde context — search, rerank-tekst, parent-expansie, curated), RLS onder béíde rollen,
  antwoordcache-keys per (principal, history, scope), rate-limits. Output: een gatenlijst.
  Stap 2: elk gat red-first dichten met /obi-test-writer. Adversariële diepte verplicht:
  vervalste/afwijkende body-scope, onbekende scope, lege scope, cross-tenant-leespoging onder
  rag_reader, RLS-settings gemanipuleerd binnen een sessie.
- **Golf 2 — het live-webhook-script permanent maken.** De sessie-runner (webhook_rules_live.py,
  alle 8 regels via échte Confluence-mutaties → Forge → Railway → worker, met de Mews-pagina als
  byte-identieke getuige) promoveren naar `backend/scripts/` met dezelfde waarborgen als
  verify_sync_rules.py: STAGING-ONLY-stempel, --yes, labels hersteld in een finally, één commando,
  plakbare output. Dit is de "werkt het écht"-knop die de owner zelf kan indrukken.
- **Golf 3 — browser (Playwright).** Tegen de stub-hostpagina's (bestaande conventie, deterministisch):
  toast-host ziet toast-content; mews-host kan een toast-only pagina níét zien; none-host → nette
  weigering; multi-host = het besliste gedrag (wacht dus deels op §15).
- **Golf 4 — eval.** De gold set per stage als voor/na-poort bij elke retrieval-aanraking; bij
  multi-scope komen er gemengde-scope goldvragen bij (Toast-vraag met Opera-token enz.).
- **Golf 5 — multi-scope red-first.** Geblokkeerd tot de §15-keuzes beslist zijn; start met het
  beslismemo, daarna de falende tests die het besliste contract vastleggen, pas dan implementatie.

Werkwijze per golf: één golf per keer, /obi-change-procedure, ledger-entry bij afronding.
