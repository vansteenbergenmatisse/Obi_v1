# Coverage map — substep 0.5.2 (built from substep 0.5.1's test-suite-inventory.md)

Date: 2026-09-16
Source: `docs/Final_docs/0.3-synopsis-2026-09-16/test-suite-inventory.md` (the current, authoritative
"tests.md" for this repo — the older `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/tests.md`
audited against a stale 101-`built`-panel snapshot; 0.4.2 corrected 52 panels' status fields since
then, and the panel set is now 108 `built`). One row per currently-`built` panel: panel id, title,
test file, test name, level, green (yes/no). Rows for panels that already have a test copy the
first-cited test name (with a `(+N more)` count when more than one test cites the panel — most
panels have several). Rows for uncovered panels start empty; those get filled by 0.5.2's ingestion +
scope-list batches (this substep) and 0.5.3's retrieval/widget/store/security batches (a later
substep) — not all of them belong to 0.5.2.

**Level note on the frontend rows:** CLAUDE.md's test-level table calls the browser level "Playwright
against a stub host page." No such suite existed anywhere in this repo before 0.5.1's own new
`apps/web/e2e/widget-mounts.spec.ts`. Every frontend row below with a `.test.ts`/`.test.tsx` file is
actually a **vitest + jsdom component test**, not a real browser — labeled honestly as `component
(jsdom, not a real browser)` rather than mislabeled `browser`, per the same drift the 0.3.2 audit
already flagged.

**108 built panels, 70 pre-filled (already had a citing test before this substep), 38 start empty.**
Of the 38 empty rows, 12 are this substep's actual scope (Ingestion stages 2–4 and the scope list);
the remaining 26 (retrieval/widget/store/security/overview/component-owner panels) are out of scope
for 0.5.2 and stay empty here for 0.5.3 or a later substep to fill.

| panel | title | test file | test name | level | green |
|---|---|---|---|---|---|
| `ov-confluence` | Confluence, the source of truth | app/platform/clients/tests/test_confluence_client.py | test_http_client_group_only_restriction_fails_closed (+2 more) | unit | yes |
| `ov-auth` | The auth host: the host backend or an agreed auth service |  |  |  |  |
| `ov-corpus` | The Postgres corpus |  |  |  |  |
| `ov-widget` | The Obi widget |  |  |  |  |
| `cm-root` | app/main.py: the wiring | app/features/confluence_sync/tests/test_chat_endpoint.py | test_create_app_wires_the_answer_cache_by_default | database | yes |
| `cm-sync` | features/confluence_sync |  |  |  |  |
| `cm-ingest` | features/ingestion |  |  |  |  |
| `cm-retrieval` | features/retrieval |  |  |  |  |
| `cm-agent` | features/rag_agent |  |  |  |  |
| `cm-platform` | platform/: shared technical capabilities | app/platform/db/tests/test_models_constraints.py | test_chunk_has_exactly_one_canonically_named_source_type_check (+2 more) | unit | yes |
| `cm-shared` | shared/: small generic helpers | app/shared/tests/test_ttl_cache.py | test_hit_returns_the_stored_value (+13 more) | unit | yes |
| `cm-scripts` | scripts/: operator tools | app/features/confluence_sync/tests/test_knowledge_scope_backfill.py | test_all_active_chunks_scope_tagged_is_ready (+8 more) | database | yes |
| `cm-docs` | docs/adr: the decisions of record |  |  |  |  |
| `cm-web` | apps/web: the widget |  |  |  |  |
| `cm-contracts` | packages/contracts | app/features/rag_agent/tests/test_token_claims_contract.py | test_required_claims_match_the_verifier (+2 more) | unit | yes |
| `cm-tokens` | packages/design-tokens |  |  |  |  |
| `cm-infra` | infra/foundation: local Postgres |  |  |  |  |
| `i1-checks` | Rate limit, size cap, HMAC, parse | app/features/confluence_sync/tests/test_webhook.py | test_missing_signature_is_rejected (+4 more) | database | yes |
| `i1-ledger` | The event ledger | app/features/confluence_sync/tests/test_webhook.py | test_duplicate_delivery_is_deduped (+3 more) | database | yes |
| `i1-self` | Was this our own write? | app/features/confluence_sync/tests/test_webhook.py | test_self_generated_event_enqueues_no_job | database | yes |
| `i1-claim` | A worker claims the job | app/features/confluence_sync/tests/test_job_queue.py | test_claim_uses_skip_locked | database | yes |
| `i1-reaper` | The reaper | app/features/confluence_sync/tests/test_job_queue.py | test_reap_reclaims_expired_lease | database | yes |
| `i1-fail` | Retry with backoff, then dead letter | app/features/confluence_sync/tests/test_job_queue.py | test_fail_backs_off_then_dead_letters | database | yes |
| `i1-handle` | Handle and complete in one transaction | app/features/confluence_sync/tests/test_worker_sync.py | test_version_guard_drops_stale_update | database | yes |
| `i2-fetch` | Fetch the page facts | app/features/confluence_sync/tests/test_worker_sync.py | test_in2_body_fetch_skipped_when_unchanged_required_on_version_bump | database | yes |
| `i2-meta` | Metadata only: update in place | app/features/confluence_sync/tests/test_worker_sync.py | test_permission_change_is_metadata_only (+1 more) | database | yes |
| `i2-nochange` | No change | app/features/confluence_sync/tests/test_attachment_wiring.py | test_resyncing_unchanged_page_is_a_true_no_change_not_a_spurious_rebuild | database | yes |
| `i2-tobuild` | On to ingestion stage 3 | app/features/confluence_sync/tests/test_attachment_wiring.py | test_i2_tobuild_body_and_attachment_blocks_both_reach_chunker | database | yes |
| `i2-inplace` | Update tags, state and restrictions in place | app/features/confluence_sync/tests/test_worker_sync.py | test_dropped_restriction_leaves_page_unrestricted | database | yes |
| `i3-blocks` | Normalize HTML into blocks | app/features/ingestion/tests/test_normalization.py | test_i3_blocks_input_is_storage_html_plus_attachment_text (+2 more) | unit | yes |
| `i3-parents` | Parent chunks | app/features/ingestion/tests/test_chunking.py | test_small_section_yields_one_parent_one_child (+2 more) | unit | yes |
| `i3-children` | Child chunks | app/features/ingestion/tests/test_chunking.py | test_small_section_yields_one_parent_one_child (+3 more) | unit | yes |
| `i3-context` | Contextualize each child | app/features/ingestion/tests/test_contextualizer.py | test_fallback_prefixes_heading_path_deterministically (+6 more) | unit | yes |
| `i3-tsv` | The keyword index | app/features/confluence_sync/tests/test_ingestion_pipeline.py | test_children_have_embeddings_and_tsv (+1 more) | database | yes |
| `i4-document` | Ensure the document row | app/features/confluence_sync/tests/test_versioning_document.py | test_i4_document_one_row_per_page_across_rebuilds (+1 more) | database | yes |
| `i4-chunks` | Insert the chunks inactive | app/features/confluence_sync/tests/test_versioning_chunks.py | test_i4_chunks_parents_persisted_before_children_are_linked (+2 more) | database | yes |
| `i4-gate` | Validation gate | app/features/confluence_sync/tests/test_versioning_gate.py | test_i4_gate_zero_children_marks_version_failed (+1 more) | database | yes |
| `i4-swap` | The pointer swap | app/features/confluence_sync/tests/test_ingestion_pipeline.py | test_version_upgrade_is_atomic_and_updates_content (+3 more) | database | yes |
| `i4-failed` | A failed version never activates | app/features/confluence_sync/tests/test_versioning_failed.py | test_i4_failed_version_persists_as_a_record (+1 more) | database | yes |
| `i4-gc` | Garbage collect old versions | app/features/confluence_sync/tests/test_versioning_gc.py | test_i4_gc_keeps_the_two_most_recent_superseded_versions (+1 more) | database | yes |
| `i4-rollback` | Rollback to an older version | app/features/confluence_sync/tests/test_versioning_rollback.py | test_rollback_restores_prior_version (+3 more) | database | yes |
| `tg-add` | Add a label | app/features/confluence_sync/tests/test_scope_tagging_add.py | test_tg_add_label_only_change_updates_tags_without_rebuild | database | yes |
| `tg-change` | Change a label | app/features/confluence_sync/tests/test_scope_tagging_change.py | test_tg_change_label_swap_leaves_no_stale_double_tag | database | yes |
| `tg-first` | The page is in the index | app/features/confluence_sync/tests/test_scope_tagging_first.py | test_tg_first_page_indexed_with_tags_already_resolved | database | yes |
| `tg-retag` | Tags updated without a re-embed | app/features/confluence_sync/tests/test_scope_tagging_retag.py | test_tg_retag_metadata_only_touches_tags_and_scope_state_not_version_or_embeddings | database | yes |
| `r1-proxy` | The widget's proxy route | apps/web/src/platform/automation-api/tests/client.test.ts | r1_proxy_forwards_chat_api_key_as_bearer_auth (+1 more) | component (jsdom, not a real browser) | yes |
| `r1-auth` | Verify who is asking | app/platform/config/tests/test_platforms.py | test_hs256_alg_is_forbidden (+15 more) | unit | yes |
| `r1-limits` | Limits and validation | app/features/rag_agent/tests/test_answer_service.py | test_rejects_history_not_ending_in_user_turn (+22 more) | unit | yes |
| `r1-small` | Small talk short-circuit | app/features/rag_agent/tests/test_small_talk.py | test_recognizes_small_talk_phrases_case_and_whitespace_insensitively (+8 more) | unit | yes |
| `r1-clarify` | Too vague to search? | app/features/rag_agent/tests/test_clarification.py | test_long_query_is_never_ambiguous_and_skips_the_classifier (+28 more) | unit | yes |
| `r1-idem` | Idempotency replay | app/features/confluence_sync/tests/test_chat_endpoint.py | test_idempotency_key_replay_with_different_field_is_not_the_first_callers_answer (+3 more) | database | yes |
| `r1-short` | A short reply without search | app/features/confluence_sync/tests/test_chat_endpoint.py | test_r1_short_small_talk_writes_no_query_trace_row (+1 more) | database | yes |
| `r2-embed` | Embed the question | app/platform/clients/tests/test_embeddings_client.py | test_fake_provider_is_deterministic_and_right_dim (+1 more) | unit | yes |
| `r2-gucs` | Set the scope for this transaction | app/features/retrieval/tests/test_search_repo_gucs.py | test_emits_both_gucs_with_valid_values (+3 more) | unit | yes |
| `r2-dense` | Dense search | app/features/retrieval/tests/test_search_repo_knowledge_scope.py | test_dense_search_omits_predicate_when_knowledge_scopes_is_none (+2 more) | unit | yes |
| `r2-keyword` | Keyword search | app/features/retrieval/tests/test_search_repo_knowledge_scope.py | test_keyword_search_omits_predicate_when_knowledge_scopes_is_none (+1 more) | unit | yes |
| `r2-indexes` | The two search indexes | app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py | test_gin_index_is_plan_usable_for_tags_overlap | database | yes |
| `r3-reader` | rag_reader | app/platform/db/tests/test_reader_default_privileges.py | test_r3_reader_default_privileges_cover_a_table_created_after_role_provisioning | database | yes |
| `r3-source` | Source row security | app/features/confluence_sync/tests/test_retrieval_eval.py | test_retriever_wrong_source_scope_returns_zero | database | yes |
| `r3-acl` | Page-level access list | app/features/retrieval/tests/test_fusion_and_permission.py | test_classify_scope_splits_digit_strings_from_principal_ids (+4 more) | unit | yes |
| `r3-torerank` | Only permitted candidates move on | app/features/confluence_sync/tests/test_retrieval_eval.py | test_permission_enforcement_is_db_backed_not_fixture_fed | database | yes |
| `r3-deny` | A forgotten scope leaks nothing | app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py | test_flag_on_two_scopes_never_cross_leak | database | yes |
| `r3-groups` | Groups expanded at sync time | app/platform/clients/tests/test_confluence_client.py | test_group_only_restriction_resolves_to_fail_closed_sentinel (+1 more) | unit | yes |
| `r4-rerank` | Cohere cross-encoder rerank | app/platform/clients/tests/test_reranker_client.py | test_fake_is_deterministic_order_preserving_and_truncates (+11 more) | unit | yes |
| `r4-weak` | Is the best passage too weak? | app/features/rag_agent/tests/test_refusal.py | test_weak_score_when_between_offtopic_and_refusal_threshold (+6 more) | unit | yes |
| `r4-proceed` | Top-k children move on to stage 5 | app/features/retrieval/tests/test_retrieval_handoff_contract.py | test_r4_proceed_retrieval_output_shape_matches_what_evidence_assembly_consumes | unit | yes |
| `r5-evidence` | The evidence block | app/features/rag_agent/tests/test_prompt.py | test_build_evidence_block_numbers_markers_from_one_in_hit_order (+4 more) | unit | yes |
| `r5-generate` | Generate the answer | app/platform/clients/tests/test_anthropic_client.py | test_create_message_happy_path (+7 more) | unit | yes |
| `r5-enforce` | Valid citation-number checking | app/features/rag_agent/tests/test_citations.py | test_keeps_cited_sentence_and_reports_used_markers (+7 more) | unit | yes |
| `r5-stream` | Completed-answer replay and the trace row | app/features/rag_agent/tests/test_answer_service.py | test_grounded_answer_with_rewrite_and_persisted_trace (+10 more) | unit | yes |
| `r5-nocite` | Refuse: nothing survived the checks | app/features/rag_agent/tests/test_answer_service.py | test_no_citations_refusal_emits_human_handoff_log_with_verbatim_original_query (+3 more) | unit | yes |
| `r5-image` | Image analysis | app/platform/clients/tests/test_anthropic_client.py | test_create_message_content_shape (+17 more) | unit | yes |
| `r5-feedback` | Thumbs up or down | app/features/confluence_sync/tests/test_chat_endpoint.py | test_feedback_updates_trace_row (+14 more) | database | yes |
| `w-launcher` | Launcher and teaser | iframe-bridge.test.ts | invokes onOpen on obi:open without setting a token (the message carries no data) (+16 more) | component (jsdom, not a real browser) | yes |
| `w-panel` | The panel | chat-session-provider.test.tsx | clears messages and pending state (+12 more) | component (jsdom, not a real browser) | yes |
| `w-composer` | The composer | attachment-strip.test.tsx | renders nothing when there are no attachments (+16 more) | component (jsdom, not a real browser) | yes |
| `w-token` | The user token | iframe-bridge.test.ts | sets the token from obi:token when the origin is allowed and the source is the parent (+16 more) | component (jsdom, not a real browser) | yes |
| `w-proxy` | The proxy route | route-handlers.test.ts | rejects malformed JSON before calling the backend (+8 more) | component (jsdom, not a real browser) | yes |
| `w-i18n` | Six locales | language-menu.test.tsx | renders all six locales with English checked (+1 more) | component (jsdom, not a real browser) | yes |
| `w-screenshot` | Screenshot of the page behind the widget | panel-body.test.tsx | hides the widget root during capture and restores it after a successful capture (+3 more) | component (jsdom, not a real browser) | yes |
| `w-render` | Rendering the answer | assistant-mark.test.tsx | renders as a decorative SVG hidden from assistive tech (+14 more) | component (jsdom, not a real browser) | yes |
| `d-event_ledger` | event_ledger | app/features/confluence_sync/tests/test_event_ledger_constraints.py | test_d_event_ledger_payload_hash_is_unique (+2 more) | database | yes |
| `d-document` | document | app/features/confluence_sync/tests/test_versioning_document.py | test_i4_document_one_row_per_page_across_rebuilds (+1 more) | database | yes |
| `d-reconciliation_run` | reconciliation_run | app/features/confluence_sync/tests/test_reconciliation.py | test_complete_reconcile_deactivates_orphan_and_enqueues_new | database | yes |
| `d-page_restriction` | page_restriction | app/features/confluence_sync/tests/test_worker_sync.py | test_first_index_persists_restrictions | database | yes |
| `s-edge` | The edge | app/features/rag_agent/tests/test_edge_auth.py | test_s_edge_host_key_rejects_unconfigured_and_wrong_key (+2 more) | unit | yes |
| `s-source` | Source row security | app/platform/db/tests/test_migration_0010_scope_rls.py | test_0010_adds_restrictive_scope_policies (+1 more) | database | yes |
| `s-acl` | Page access list | app/features/confluence_sync/tests/test_retrieval_eval.py | test_s_acl_no_restriction_recorded_is_open_to_everyone (+1 more) | database | yes |
| `s-permitted` | The permitted rows | app/features/confluence_sync/tests/test_retrieval_eval.py | test_permission_no_leak_and_authorized_access | database | yes |
| `s-writer` | The writer (table owner) | app/features/confluence_sync/tests/test_force_rls_managed_postgres.py | test_non_superuser_owner_reads_own_rows | database | yes |
| `s-reader` | rag_reader | app/platform/db/tests/test_migration_0009_reader_rls_reconcile.py | test_0009_adds_reader_policy_and_keeps_rls_on (+8 more) | database | yes |
| `s-anon` | Supabase's public roles | app/features/confluence_sync/tests/test_reader_rls_reconcile.py | test_reader_freed_but_anon_stays_denied | database | yes |
| `s-audit` | The audit trail | app/features/rag_agent/tests/test_answer_service.py | test_subject_hash_persisted_is_the_hash_not_the_raw_subject (+2 more) | unit | yes |
| `ks-index` | Pages go in | app/features/confluence_sync/tests/test_knowledge_scope_backfill.py | test_all_active_chunks_scope_tagged_is_ready | database | yes |
| `vd-text` | The text that becomes a vector | app/features/ingestion/tests/test_contextualizer.py | test_llm_path_sends_cached_document_and_prepends_context | unit | yes |
| `vd-column` | chunk.embedding | app/features/confluence_sync/tests/test_vector_data_column.py | test_vd_column_embedding_is_nullable (+2 more) | database | yes |
| `vd-hnsw` | The HNSW index | app/features/confluence_sync/tests/test_reader_vector_access.py | test_reader_can_run_dense_halfvec_query | database | yes |
| `vd-nearest` | The nearest 75 | app/features/retrieval/tests/test_vector_data_nearest.py | test_vd_nearest_orders_by_distance_then_page_id_on_ties (+1 more) | database | yes |
| `vd-rls` | Row security covers vectors too | app/features/confluence_sync/tests/test_reader_vector_access.py | test_reader_can_run_dense_halfvec_query | database | yes |
| `vd-question` | The question vector | app/platform/clients/tests/test_embeddings_client.py | test_fake_provider_is_deterministic_and_right_dim (+1 more) | unit | yes |
| `vd-keyword` | The keyword side | app/features/confluence_sync/tests/test_ingestion_pipeline.py | test_keyword_tsv_is_queryable | database | yes |
| `vd-swap` | Vectors swap with the page | app/features/confluence_sync/tests/test_worker_sync.py | test_content_change_swaps_version_atomically | database | yes |
| `sc-frontend` | One frontend |  |  |  |  |
| `sc-backend` | One backend |  |  |  |  |
| `em-token` | The signed note (JWT) | test-host-content.test.tsx | builds the per-name token endpoint for %s (+2 more) | component (jsdom, not a real browser) | yes |
| `em-backend` | Obi checks the note and picks the pages | app/features/rag_agent/tests/test_token_verifier.py | test_valid_token (+20 more across test_token_verifier.py/test_auth_context.py/test_platforms.py) | unit | yes |
| `em-button` | The frame: the round button and the chat window | frame-csp.test.ts | includes every active domain and never emits a wildcard (+8 more) | component (jsdom, not a real browser) | yes |
| `em-loader` | obi.js: one script tag | loader.test.ts | Obi.init injects exactly one iframe pointed at the embed origin's /embed route (+2 more) | component (jsdom, not a real browser) | yes |

## 0.5.2 scope: ingestion stages 2–4 and the scope list (12 panels, 4 batches)

Ingestion stage 1 has no empty rows above (every `i1-*` panel already has a test). The 12 rows this
substep is responsible for filling, grouped into batches per the substep's own step 2 ("one generated
batch at a time... one obi-implementer subagent per panel, in parallel"):

- [x] **Batch A — Ingestion stage 2** (2 panels): `i2-tobuild`, `i2-fetch` — done 2026-09-16, `make test-unit`/`make test-db` both green (453 passed / 169 passed + 1 xfailed)
- [x] **Batch B — Ingestion stage 3** (1 panel): `i3-blocks` — done 2026-09-16, `make test-unit`/`make test-db` both green (456 passed / 169 passed + 1 xfailed)
- [x] **Batch C — Ingestion stage 4** (5 panels): `i4-document`, `i4-chunks`, `i4-gate`, `i4-failed`, `i4-gc` — done 2026-09-16, `make test-unit`/`make test-db` both green (458 passed / 178 passed + 1 xfailed). Two disclosed findings (not "red today"): `i4-failed`'s own page-disclosed GC gap, plus a further finding that a gate failure via the real job queue leaves no persisted row at all (full transaction rollback) — only a direct rebuild-time gate call leaves a `state=failed` record. See the two "Disclosed finding" sections below.
- [x] **Batch D — The scope list** (4 panels): `tg-add`, `tg-change`, `tg-first`, `tg-retag` — done 2026-09-16, `make test-unit`/`make test-db` both green (458 passed / 182 passed + 1 xfailed). 0.5.2 closed: all 12 in-scope panels ticked across Batches A-D.

The other 26 empty rows above (`ov-auth`, `ov-corpus`, `ov-widget`, `cm-sync`, `cm-ingest`,
`cm-retrieval`, `cm-agent`, `cm-docs`, `cm-web`, `cm-tokens`, `cm-infra`, `r1-proxy`, `r1-short`,
`r3-reader`, `r4-proceed`, `w-screenshot`, `d-event_ledger`, `d-document`, `s-edge`, `s-acl`,
`vd-column`, `vd-nearest`, `vd-question`, `sc-frontend`, `sc-backend`, `em-backend`) are retrieval,
widget, store, security, or cross-cutting overview/component-owner panels — out of this substep's
"Ingestion stages 1 to 4 and the scope list" boundary. They stay empty for 0.5.3 (retrieval/widget/
store/security) or a later substep; several (`ov-*`, `cm-sync`/`cm-ingest`/`cm-retrieval`/`cm-agent`/
`cm-web`, `sc-frontend`/`sc-backend`) are architecture-level claims that may never get a single
dedicated test and instead stay enforced by `make boundaries` — flagged here, not silently dropped.

## 0.5.3 scope: retrieval stages 1–5, the widget, the store and security (13 panels, 4 batches + live)

Of the 26 rows 0.5.2 left empty, 13 are testable panels grouped into the four named categories below;
the other 13 (`ov-auth`, `ov-corpus`, `ov-widget`, `cm-sync`, `cm-ingest`, `cm-retrieval`, `cm-agent`,
`cm-docs`, `cm-web`, `cm-tokens`, `cm-infra`, `sc-frontend`, `sc-backend`) are architecture-level/
component-owner claims with no single dedicated test, enforced by `make boundaries` instead — out of
this substep's scope, same reasoning as 0.5.2's own 14 architecture rows.

- [x] **Batch A — Retrieval stages 1–5** (4 panels): `r1-proxy`, `r1-short`, `r3-reader`, `r4-proceed` — done 2026-09-16, `make test-unit`/`make test-db`/frontend vitest all green (459 passed / 185 passed + 1 xfailed / 198 frontend tests passed)
- [x] **Batch B — The widget** (2 panels): `w-screenshot`, `em-backend` — done 2026-09-16, `make test-unit`/`make test-db`/`make test-ui` all green (459 passed / 185 passed + 1 xfailed / 1 passed). `em-backend` needed no new test (21 existing tests already covered it); `w-screenshot` got 4 new vitest tests.
- [x] **Batch C — The store** (5 panels): `d-event_ledger`, `d-document`, `vd-column`, `vd-nearest`, `vd-question` — done 2026-09-16, `make test-unit`/`make test-db` both green (459 passed / 193 passed + 1 xfailed). `d-document`/`vd-question` filled by citation (already covered); `d-event_ledger`/`vd-column`/`vd-nearest` got new tests (8 total). Note: a stray incident during `vd-nearest`'s authoring briefly touched the live Supabase project — logged and blocked from repeating, see docs/plan/ledger.md "Need from you".
- [x] **Batch D — Security** (2 panels): `s-edge`, `s-acl` — done 2026-09-16, `make test-unit`/`make test-db` both green (462 passed / 195 passed + 1 xfailed). All 13 in-scope 0.5.3 test-writing panels now ticked across Batches A-D; only the live isolation run remains for 0.5.3.
- [x] **Live isolation run** — done 2026-09-16 against staging (owner-confirmed), output saved to `final_docs/0.5-regression-tests/live-isolation-2026-09-16.txt` (exit 0, all isolation checks green). 11 "needs live" items from delta.md checked (12 rows, two grouped by panel-set): 6 green, 6 red (one open line per red item added to docs/plan/decisions.md). 0.5.3 fully closed: all 13 test-writing panels (Batches A-D) + the live run.

## Disclosed finding (0.5.2 Batch A, not a "red today" item — no test failed)

Writing `i2-fetch`'s test surfaced a design-text/code drift, separate from and in addition to the
already-recorded ones: the panel text says the body is fetched "only when `decide_body_fetch` says
the version **or the attachment list** moved." The real `decide_body_fetch`
(`app/features/ingestion/domain/change_detection.py:90-101`) only checks the served version number
against the locally-indexed one (plus pipeline-config drift) — it never inspects the attachment
manifest. Attachment-list changes are detected separately (`ChangeClass.attachment_changed` in
`classify()`) and, per `sync_service.py:44-55`'s `_REBUILD_CLASSES` comment, deliberately do **not**
trigger a body fetch or rebuild today — an already-disclosed, intentional scope decision from
earlier work, not new breakage. The new test asserts the real behavior (version-driven only), not
the panel's stronger "or the attachment list" claim, since that claim is not what the code does.
Not fixed here (test-writing substep, no application-code changes) and not put in "red today" (no
test is failing — the code and its test agree; it's the *panel text* that overstates the trigger
condition). Recorded here so it isn't lost; the design page's `i2-fetch` panel text should be
corrected in a future design-review pass along the lines of the 0.4.2/0.4.3 corrections.

## Disclosed finding (`i4-failed`, Batch C, not a "red today" item — no test failed)

The `i4-failed` panel already discloses its own gap in its own `today` line: "GC only reaps
versions in state=superseded; a failed-state version is never garbage-collected" — directly
contradicting its "Cleanup" fact line ("GC deletes failed versions later; chunks cascade"). The
new tests (`test_i4_failed_version_persists_as_a_record`,
`test_i4_failed_never_garbage_collected_by_gc`) assert the real (today) behavior: a gate-failed
`document_version` row persists and `_gc_superseded`'s query (`state == DocState.superseded`,
`versioning.py:378-399`) never selects, marks or deletes it. This is not a "red today" item — no
test fails against the untouched code; the code and its new tests agree. Only the panel's
"Cleanup" line overstates what happens today (the aspirational future state, not the current
one). Worth a future design-review pass to either implement failed-version GC or correct the
panel text/status — it is currently marked `st: built` despite carrying an unresolved `today` gap,
itself an inconsistent combination worth flagging.

A second, related finding surfaced while writing these tests, going beyond what the panel itself
discloses: reaching this same gate through the *real job-queue worker path* (`run_once`/`drain`)
leaves **no row at all**, not merely an unreaped one. `run_once`'s "transaction 2" (handle +
complete) wraps the whole sync in one commit-or-rollback session and rolls everything back on any
handler exception (`worker.py`'s own transaction-discipline docstring); confirmed empirically by
running an empty-body fixture page through `index_page` and finding zero `document_version` rows
afterward. Separately, a gate failure on a page's very *first* index cannot even be committed
directly either: `Document.page_id`'s FK to `page_source.page_id` is deferred to commit
("insert-order cycle on first index", `models.py:186-190`), and `page_source` is only ever created
inside `_activate`, which a gate failure never reaches — so a direct commit attempt in that case
raises `IntegrityError`, confirmed empirically. The two new tests therefore force the gate on a
*rebuild* of an already-indexed page (`document`/`page_source` already exist), calling
`stage_and_activate` directly with a test-controlled session, which is the one path under which
the panel's "stays as a record" claim actually holds today. Not fixed here (test-writing substep,
no application-code changes); recorded so the gap between "stays as a record" (true only for a
directly-committed rebuild-time failure) and "never persists at all" (true for the real
job-queue/first-index paths) isn't lost.

## needs live

Checked 2026-09-16 against staging (`aws-1-eu-west-1.pooler.supabase.com`, owner-confirmed not
production), commit `2ac7e7a`. Full isolation-script output: `live-isolation-2026-09-16.txt`. The
11 items below are `delta.md`'s "Needs live" list (392-405); the four embedding-related panels
there are grouped into one row, and the three migration-0010 panels into another, matching how
`delta.md` itself grouped them.

| panel | title | check | green / red | reason |
|---|---|---|---|---|
| `ov-corpus` | Is the live `alembic_version` actually 0009 as designed? | `SELECT version_num FROM alembic_version` | green | Actual: `0012_widen_document_version_idem` — the design's "0009 live" claim is stale; live is at head (0012), confirming the 0.4.2 correction, not the original design text. |
| `cm-infra` | Is production actually running on Supabase? | connect and query | red | Only the confirmed **staging** project was connected to this run, per this substep's "never against production" rule. Whether a separate production deployment also runs on Supabase (or where production traffic actually goes) cannot be inferred from staging alone. |
| `cm-docs` | Does an ADR exist for fingerprint/scope_state/label-gated-ingestion/edge-token? | `ls docs/adr/` (local, not DB) | red | Checked all 13 ADRs on disk (0001-0014, no 0012); none is titled or scoped to these four topics. No such ADR exists today. |
| `i3-children` | Live value of `KIND_CHILD` | `SELECT DISTINCT kind FROM chunk` + code grep | green | Code: `KIND_CHILD = 1` (`platform/db/models.py:57`). Live: only `{0, 1}` present in `chunk.kind` on staging — matches the parent=0/child=1 convention exactly. |
| `i3-embed` / `vd-model` / `vd-column` / `vd-question` | Deployed embedding provider/model/dimension | `pg_attribute` on `chunk.embedding` | green | Live: `vector(3072)` — confirms the `.env` OpenAI/3072 override is what's actually deployed on staging, not the code's Voyage/1024 default. Resolves the open ambiguity for this environment (does not itself pick a permanent default — that decision, `vd-model`, stays tracked as blocked/unscheduled in `delta.md`). |
| `ov-filter` | Is source RLS actually "live" (enabled + policy present) on Supabase? | `pg_class.relrowsecurity` + `pg_policy` on `chunk` | green (partial) | Live: `chunk.relrowsecurity = true`, policy `chunk_source_read` present (permissive). Confirms source RLS is live. The narrower "empty tags read as public" sub-claim was not independently behavior-tested this round (would need a live query as a real reader against an empty-tags row) — not claimed green. |
| `r3-scope` / `s-scope` / `tg-filter` | Is migration 0010 actually applied to Supabase? | `alembic_version` + `pg_policy` | green | Live head is 0012 (downstream of 0010) and the RESTRICTIVE `chunk_scope_read` policy from 0010 is present on `chunk`. Confirms `2435127`'s note over the design page's "not applied yet" claim. |
| `s-writer` | Owner role's actual RLS-exempt behavior | `pg_class.relforcerowsecurity` + `pg_tables.tableowner` + `current_user` | green (staging only) | Live: `chunk.relforcerowsecurity = false`, table owner and the connecting admin role are both `postgres` — standard Postgres behavior exempts the owner from RLS whenever FORCE is off. Verified on **staging**; not separately re-verified against a distinct production instance if one exists. |
| `sc-user` | Shape of a real per-person identity mapping | — | red | No real platform's per-person identity flow was available to check this session; only the local test-host scaffolding exists (already covered by unit/db tests elsewhere). |
| `e-ops` | p50 5.9s / p95 7.4s / $0.23-per-run figures | — | red | No code path in `features/evaluation` computes or stores these; they are a one-off manual local run recorded in `docs/rag/PLAN.md`, not reproducible from wired code. Unchanged by this run. |
| `em-hostbackend` | The panel's entire mechanism | — | red | Describes a system outside this repo entirely; nothing to connect to or check. Already tracked as `[Decision needed]` in `delta.md`. |
| `ov-auth` step 5 | Backend verifies alg/signature/issuer/audience/expiry against a *real* platform's key | — | red | Confirmed in code/tests against synthetic test-host keys only (`test_token_verifier.py` etc.); no real platform's live signing key was available to test end-to-end this session. |

## red today

| panel | title | check | reason | decisions.md line |
|---|---|---|---|---|
