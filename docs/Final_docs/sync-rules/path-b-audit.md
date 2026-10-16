# Sync rules x Path B (ADR-0021) audit, HEAD 3178553

## Purpose (two lines)
Check each of the 8 sync rules against the routing-label scheme across code, relational DB and vector rows.
Read-only; tests were read, not re-run in this audit (the commit message reports unit 1148 / db 392 green).

## Entry points
| symbol | file:line | called by |
|---|---|---|
| handle_sync_page | backend/app/features/confluence_sync/application/sync_service.py:31 | worker (webhook + sweep jobs) |
| handle_delete_page | sync_service.py:66 | worker, delete-class events |
| decide_command / resolve_scopes | confluence_sync/domain/ingest_decision.py:140 / :103 | handle_sync_page |
| _apply_upsert | ingestion/application/command_handler.py:109 | IngestionSink |
| _apply_metadata_only | command_handler.py:324 | _apply_upsert |
| _sweep_space (CQL label discovery) | confluence_sync/application/reconciliation.py:~137 | run_reconciliation |
| apply_allowed_labels | retrieval/infrastructure/search_repo.py:105 | retriever.py:208 |
| backfill_labels | ingestion/application/backfill_labels.py:33 | operator |

## Reads and writes
| tables | r/w | file:line |
|---|---|---|
| page_source.tags / .labels | write | command_handler.py:349-351 |
| chunk.tags / chunk.labels (metadata-only restamp, no re-embed) | write | command_handler.py:364-371 |
| chunk.labels on build | write | ingestion/application/versioning.py:105-106, :322 |
| all rows of a page (purge) | write | command_handler.py:101, :119, :157 |
| chunk RLS: chunk_source_read AND chunk_labels_read (0018 dropped chunk_scope_read) | policy | knowledge-base/migrations/versions/0018_retire_knowledge_scope_rls.py:55-56; 0016_chunk_labels.py:52-57 |

## External calls
| client | endpoint | timeout, retry, breaker | file:line |
|---|---|---|---|
| Confluence CQL label search | list_pages_by_label | shared _get: timeout, retry, breaker (per docstring) | platform/clients/confluence_client.py:238-255 |

## The 8 sync rules (source: sync-rules/plan.md section 6, lines 667-771; ledger.md:275 and :279 name them "the 8 sync rules")
1. Delete / trash / archive -> purge every row (plan.md:667)
2. Remove the last recognized tag -> purge (plan.md:682)
3. Remove one tag, another stays -> update tags, no re-embed, same version (plan.md:698)
4. Add a tag when one exists -> union it in, no re-embed, same version (plan.md:706)
5. First recognized tag on an untagged page -> full build (plan.md:722)
6. Edit body / title (attachment deferred) -> rebuild whole page, embed every chunk, no vector reuse (plan.md:735)
7. Add `classified` -> purge (plan.md:756)
8. A page never touches another page's rows (plan.md:765)

Path B changes only what "recognized tag" means: `recognized = settings.product_catalog.all_routing_labels()` (sync_service.py:59; ingest_decision.py:121-123), i.e. `obi-general`, `{slug}-general`, `{slug}-to-{pos|pms|accounting}` (product_catalog.py:175-186). Raw labels go to `chunk.labels` (the routing column); `chunk.tags` now holds recognized routing labels but is inert for retrieval (ingest_decision.py doc, per diff).

## Tests present (confluence_sync/tests unless stated)
| test file | behaviors asserted | panel ids |
|---|---|---|
| test_sync_rules_delete.py:29,50,71,94,139 | rule 1 purge; 1b restore full rebuild; never-indexed no-op; archive caught by lightweight sweep; rule 7 classified purge (labels `obi-general`+`classified`) | i2-gone, tg-classified |
| test_sync_rules_membership.py:43,59,75,94,118 | rule 2 (last routing label, unrelated-only), rule 5 negative + positive (`mews-general`), guard | tg-remove, ks-index |
| test_sync_rules_visibility.py:72,97,115,130,164 | rules 3/4: metadata_only, same version, 0 embeds, asserts `page_source.tags` only | i2-labels, tg-two |
| test_sync_rules_rebuild.py:29,46,76,100 | rule 6 body, title, retain-0, attachment (strict xfail) | i3-embed, i2-rebuild, i4-gc |
| test_sync_rules_isolation.py:56 | rule 8 | vd-swap |
| test_ingest_decision.py (parametrized over every routing label, :26,:61-173) | pure decide_command table incl. classified, tag-removed, shared page | ks-index |
| test_mi_labels.py:76,93,118 | raw labels land on every chunk; label-only change restamps `labels`, no re-embed; backfill idempotent | mi-labels |
| test_mi_labels_rls.py:60,75 | chunk_labels_read no-op when GUC unset, overlaps when set | mi-labels |
| retrieval/tests/test_label_hardfilter_db.py:156-232 | hard filter by seeded labels (zero uses of run_once/set_labels/index_page, so not driven through sync) | mi-filter |
| test_list_pages_by_label.py:23-42 | fixture CQL label discovery with routing labels | trigger |

## Per-rule verdict (CODE / DB / VECTOR)
| # | Rule | CODE | DB | VECTOR | Verdict | Evidence and gap |
|---|---|---|---|---|---|---|
| 1 | delete/trash/archive | Label-independent. DELETE events -> SyncCommand delete -> purge_page (sync_service.py:80; command_handler.py:96-104). Archive via lightweight sweep orphan pass. | page_source/document/version/restriction rows gone | chunks cascade | COVERED | test_in2_delete_page_removes_rows, test_in2_delete_then_restore_full_rebuilds, test_in2_archived_page_without_webhook_purged_by_lightweight_sweep. Restore works only if the page still carries a routing label (ingest_decision.py:122). |
| 2 | remove last tag | resolve_scopes returns set() when no routing label (ingest_decision.py:121-123) -> delete -> purge | rows removed; no `empty tags` state reachable | chunks removed | COVERED | test_tags_remove_last_recognized_label_removes_rows, test_tags_unrelated_labels_alone_do_not_keep_page (membership.py:43,59). Note: a legacy page carrying only `obi-*-test` is no longer a member, so the first post-Path-B sync of such a page PURGES it (see old-tag section). |
| 3 | remove one tag, one stays | labels_hash changes (change_detection.py:203-204), scopes drift, metadata-only (command_handler.py:203-232) | page_source.tags+labels updated | chunk.tags AND chunk.labels restamped, no re-embed (command_handler.py:364-371) | PARTIAL | Code and DB path work. test_tags_remove_one_tag_keeps_page_updates_tags_no_reembed (visibility.py:164) asserts only `page_source.tags`, version id and 0 embeds. Nothing asserts that `chunk.labels` shrinks after a removal, nor that a Toast-to-Mews chat stops seeing the page. test_mi_labels.py:93 proves the label restamp only for an ADD. |
| 4 | add a tag | same metadata-only path, union via cmd.scopes | tags+labels updated | chunk.labels restamped, no re-embed | PARTIAL | test_tags_add_second_tag_updates_tags_no_reembed (visibility.py:72) + test_in2_label_only_change_restamps_labels_no_reembed (test_mi_labels.py:93, adds an extra raw label). The retrieval assertions in test_tags_shared_page_visible_in_both_scopes (visibility.py:107-112) and test_tags_remove_shared_tag_keeps_other_scope (:154,:158) are now vacuous: their comments say the scope arg no longer excludes (ADR-0021), so they prove nothing about routing. Routing flip after adding a routing label is untested end to end. |
| 5 | first tag -> full build | untagged -> delete/skipped (ingest_decision.py:122); first routing label -> upsert, local None -> rebuild (command_handler.py:162) | page_source created | every child embedded, `labels=list(labels)` stamped (command_handler.py:189; versioning.py:105) | COVERED | test_in2_untagged_page_never_indexed, test_in2_first_relevant_tag_full_build (membership.py:75,94; uses `mews-general`). Chunk.labels on first build covered by test_in2_chunk_carries_raw_labels (test_mi_labels.py:76). |
| 6 | edit body/title -> full rebuild, no reuse | rebuild classes unchanged by Path B; labels passed through to stage_and_activate (command_handler.py:180-191) | old version rows deleted (retain 0) | all children re-embedded, labels restamped on the new chunks | COVERED (attachment edit remains a strict xfail, D2) | test_sync_rules_rebuild.py:29,46,76; xfail :100. These tests do not touch labels, so label-scheme independence is by construction, not asserted. |
| 7 | add `classified` -> purge | RESERVED_CLASSIFIED_SCOPE check precedes recognized check (ingest_decision.py:119-120); knowledge_scopes.json keeps only `classified` | all rows removed | chunks removed | COVERED for add; PARTIAL for removal | test_in2_classified_label_removes_rows (delete.py:139, `obi-general`+`classified`). Removing `classified` -> fresh first build is stateless in decide_command but has no DB test; only the live script exercises it (scripts/webhook_rules_live.py:425-441). |
| 8 | page never touches other pages | all writes keyed by page_id | per-page | per-page | COVERED | test_in2_change_never_touches_other_pages_rows (isolation.py:56). Not label dependent. |

Net: 5 COVERED (1, 2, 5, 6, 8), 1 COVERED plus a removal gap (7), 2 PARTIAL (3, 4). No rule is a hard GAP in code; every rule handles routing labels in code, DB and vector. The partials are test-proof gaps on the vector `labels` column and the routing outcome.

## Known gaps (still assume the OLD scheme or unproven)
- Nothing in tests drives "label change via sync -> chunk.labels changed -> retrieval routing changes" (rules 3/4). test_label_hardfilter_db.py has 0 uses of run_once/set_labels/index_page.
- test_sync_rules_visibility.py:1-15, :107-112, :154-158 and its docstrings still describe the retired scope-overlap model; the retrieval assertions are vacuous.
- Legacy-tag purge risk: a page carrying only `obi-toast-test` / `obi-mews-test` / `obi-general-test` is not a member (ingest_decision.py:121-123), so its next sync, or the first complete sweep, purges it (rule 2). Ledger.md:281 says the 4 standing test pages plus Toast-testpage carry one `-test` tag each. The prod runbook (docs/runbooks/adr-0021-prod-migration.md) was not read in this audit; confirm it orders "add routing label" before the first sync.
- source_scope allow-list: authorized_tags (ingest_decision.py:67-100) intersects labels with row `tags`. Any active source_scope row with non-empty legacy tags (e.g. `obi-toast-test`) authorizes none of the routing labels, so covered pages are deleted. Ledger.md:279 records the live row id=23 with empty tags (safe). Other rows were not enumerated here (needs live). test_source_scope_lifecycle.py:45-46 was migrated to routing labels.
- Stale operator scripts and docs with old defaults: scripts/verify_sync_rules.py:350-351, scripts/webhook_rules_live.py:492-493 (and :48), scripts/verify_knowledge_scope_live.py:235 and :19, scripts/smoke_webhook.py:7,24,151, scripts/verify_directed_routing_live.py:10,51 (`GATE_SCOPE = ("obi-general-test",)`). Run with their defaults they would not index a page.
- docs/Final_docs/sync-rules/manual-tests.md:70,78,82 (MT-3, MT-4) still use `obi-mews-test`, `obi-toast-test`, `obi-general-test`; docs/Final_docs/sync-rules/routing-test-labels.md:19-30 still says each page needs the membership tag `obi-general-test` plus one routing label. This contradicts HEAD (commit message: base tag no longer required) and ADR-0021.
- backend/app/main.py:230-235 still publishes `knowledge_scopes` from knowledge_scope_set; per knowledge_scopes.json that set is now empty, so /health shows `[]` (cosmetic, not read).
- knowledge_scope_backfill.py is kept as a superseded no-op (docstring); every active chunk reports as "unscoped" against the empty set (per diff). Any readiness gate that fails on that count would misbehave: not checked here.
- Sweep CQL: reconciliation.py now passes the whole catalog label set (every product x pos/pms/accounting, so more labels than the 9 live ones) into `label in (...)`. Length and the 400 history (ledger.md:279 finding a) were not checked; the fix is documented at confluence_client.py:245-250 (needs live).
- Archive fires no webhook (ledger.md:279 b); caught only by the daily lightweight sweep, tested at test_sync_rules_delete.py:94.
- No ingestion hook for `chunk_labels_read` default: with no `session_labels`, the GUC is `'*'` and routing filters nothing (search_repo.py:112-114, :122-123). That is intended for legacy chats but means a token without connection context sees every member page.

## Claims from the design
| panel | claim | file:line | verdict | note |
|---|---|---|---|---|
| ks-index | membership = published + recognized label, roots decide nothing | ingest_decision.py:114-127 | confirmed | recognized set is now routing labels |
| tg-remove | last recognized label removed -> purge | ingest_decision.py:122-123; command_handler.py:101 | confirmed | |
| tg-classified | `classified` removes | ingest_decision.py:119-120 | confirmed | |
| mi-labels | raw labels stamped on chunk and page_source, restamped without re-embed | command_handler.py:350-367; versioning.py:105,322 | confirmed | |
| i2-labels / tg-two | multiple tags = sharing, overlap visibility | visibility tests | drifted | visibility is now `labels && session_labels`; the test comments and assertions describe the retired scope overlap |
| 3.4.1 | empty tags visible to no scope | 0018 drops chunk_scope_read | drifted | the scope fence no longer exists; isolation is source + labels only |
| live proof on Supabase of 0018 and routing sync | not available | n/a | needs live | |

## Not on the design page
- knowledge_scope_backfill.py: kept only so imports and tests resolve (docstring).
- ingestion/application/backfill_labels.py:33 operator backfill of raw labels.
- scripts/verify_directed_routing_live.py one-command live isolation check.

## Follow-up — gaps closed 2026-10-13 (the verdicts above stay as the HEAD-3178553 record)

The two PARTIAL verdicts (rules 3 and 4) and the stale-operator-file known-gap are now closed in the
working tree (uncommitted, branch convention). The per-rule table above is left as the point-in-time
audit of commit 3178553; this section records what changed since.

- **Rules 3 & 4 — PARTIAL → COVERED (test-proof).** New DB test file
  `backend/app/features/confluence_sync/tests/test_sync_rules_routing.py` drives a routing-label
  change *through the real sync path* (`set_labels` + `run_once`) and asserts the two things the
  audit found unproven: that `chunk.labels` **grows** (rule 4) / **shrinks** (rule 3) on the active
  chunks, and that retrieval **routing flips** through the real `HybridRetriever.retrieve(...,
  session_labels=...)` — a Toast→Mews chat starts/stops seeing the page while the Mews→Toast chat is
  unaffected (the connections pivot on the directed box `toast-to-pms` vs `mews-to-pos`). Green on
  current code (the code already worked — this closes the proof gap); proven real by the 0.2.8 revert
  method (disabling the label filter + its GUC turns both red, then restored). This also supersedes
  the "vacuous retrieval assertions" note on `test_sync_rules_visibility.py:107-112,154-158`: the real
  routing proof now lives in the new file; the visibility tests keep their valid tags/version/no-embed
  assertions.
- **Stale operator scripts & docs — closed.** `verify_directed_routing_live.py` `GATE_SCOPE` →
  `()` (mirrors the gate's `allowed_scopes=()`; the scope GUC is a dead no-op post-0018) + docstring;
  `verify_sync_rules.py` / `webhook_rules_live.py` `--scope-a/-b` defaults → `mews-general` /
  `toast-general`; `smoke_webhook.py` example → `toast-general`; `verify_knowledge_scope_live.py`
  SUPERSEDED banner (retired scope axis — not re-defaulted); `routing-test-labels.md` "two labels" →
  "one label" (routing label alone is membership, ADR-0021); `manual-tests.md` MT-3/MT-4 and
  `docs/runbooks/phase-9-directed-routing-live-test.md` corrected to the routing model.
- **`/health` `knowledge_scopes: []`** (audit item at main.py:230-235) — confirmed live and cosmetic;
  left as-is.
- **Still open (unchanged by this pass):** `setup_supabase.py check_deploy_readiness` still asserts
  the retired `chunk_scope_read` — now carries a precise STALE docstring banner but was deliberately
  NOT re-implemented (it is a fail-closed security gate with its own tests; re-spec is its own
  substep + security review — it fails SAFE meanwhile). The live re-sync + the
  `verify_directed_routing_live.py` isolation proof remain owner/worker-owned (the nine labelled
  pages were still the pending tail jobs at check time; chunks 0). The source_scope allow-list and
  sweep-CQL-length items still need a live check.

Gate after this pass: `make check` green — boundaries 0 · backend 1542 passed + 1 xfailed · kb 53
passed; ruff + pyright clean on all touched files.

## Follow-up 2 — the "Still open" bullet is CLOSED 2026-10-13 (later)

The five items the bullet above left open were run **read-only against production Supabase on
2026-10-13** (owner-authorized) and all passed. The bullet stays as the point-in-time record; this
corrects it.

- **Readiness gate — CORRECTION, it WAS re-implemented.** The bullet's "deliberately NOT
  re-implemented … still asserts the retired `chunk_scope_read`" is **wrong for HEAD `8025d24`**.
  `check_deploy_readiness` is fully re-specced for Path B (asserts `chunk_source_read`
  PERMISSIVE/SELECT + chunk RLS enabled + the curated reader policy; `chunk_scope_read` appears only
  in comments saying it is NOT asserted; `chunk_labels_read` is reported-only, fail-open), with a
  4-case test `test_deploy_readiness_check.py` green in `make check`. Run live: rc `0` READY. The
  re-spec and the audit prose shipped in the same commit; the prose simply wasn't updated.
- **Live re-sync + isolation proof — done.** The nine labelled pages are no longer pending: jobs
  `1249–1261` all `succeeded`, each page has 2 active chunks, and
  `verify_directed_routing_live.py --source toast --target mews --mirror` returned exit `0` PASS as
  `rag_reader` (RLS enforced, non-vacuous, zero mismatches), both directions.
- **source_scope allow-list — SAFE.** All 5 active rows (ids 10/11/12/13/23) carry empty `tags=[]`;
  none authorizes zero routing labels.
- **Sweep-CQL length — SAFE.** 21-label catalog → a 464-char `label in (...)` clause, far under the
  limit; the historical 400 was the `space.id` field, not length. Live-corroborated by the
  succeeding sweep.

Full detail and numbers: `plan.md` "Update 2026-10-13 (later)" block. The remaining tail is
human/partner only (Phase A, then Base + Data Hub integration) plus the optional `obi.omniboost.com`
DNS switch.
