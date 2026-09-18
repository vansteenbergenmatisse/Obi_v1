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
| `cm-root` | app/main.py: the wiring | app/tests/test_cm_root_wiring.py | test_cm_root_reads_settings (+2 more) | unit | yes |
| `cm-sync` | features/confluence_sync |  |  |  |  |
| `cm-ingest` | features/ingestion |  |  |  |  |
| `cm-retrieval` | features/retrieval |  |  |  |  |
| `cm-agent` | features/rag_agent |  |  |  |  |
| `cm-platform` | platform/: shared technical capabilities | app/platform/db/tests/test_models_constraints.py | test_chunk_has_exactly_one_canonically_named_source_type_check (+2 more) | unit | yes |
| `cm-shared` | shared/: small generic helpers | app/shared/tests/test_ttl_cache.py | test_hit_returns_the_stored_value (+13 more) | unit | yes |
| `cm-scripts` | scripts/: operator tools | app/features/confluence_sync/tests/test_knowledge_scope_backfill.py | test_all_active_chunks_scope_tagged_is_ready (+8 more) | database | yes |
| `cm-docs` | docs/adr: the decisions of record | tests/test_cm_docs.py | test_cm_docs_0001_stack_names_postgres_pgvector_fastapi_nextjs (+2 more) | unit | yes |
| `cm-web` | apps/web: the widget |  |  |  |  |
| `cm-contracts` | packages/contracts | app/features/rag_agent/tests/test_cm_contracts.py | test_data_cm_contracts_openapi_chat_yaml_is_the_source_of_truth (+2 more) | unit | yes |
| `cm-tokens` | packages/design-tokens | tests/code_map/test_cm_tokens.py | test_cm_tokens_holds_colors_type_and_tailwind_theme_mapping (+1 more) | unit | yes |
| `cm-infra` | infra/foundation: local Postgres | tests/tools/test_cm_infra.py | test_cm_infra_pgvector_image_pinned_to_0_8_x (+2 more) | unit | yes |
| `i1-checks` | Rate limit, size cap, HMAC, parse | app/features/confluence_sync/tests/test_webhook.py | test_missing_signature_is_rejected (+4 more) | database | yes |
| `i1-ledger` | The event ledger | app/features/confluence_sync/tests/test_webhook.py | test_duplicate_delivery_is_deduped (+3 more) | database | yes |
| `i1-self` | Was this our own write? | app/features/confluence_sync/tests/test_webhook.py | test_i1_self_ledger_row_marked_done_and_self_generated (+1 more) | database | yes |
| `i1-claim` | A worker claims the job | app/features/confluence_sync/tests/test_job_queue.py | test_claim_uses_skip_locked (+3 more) | database | yes |
| `i1-reaper` | The reaper | app/features/confluence_sync/tests/test_job_queue.py | test_reap_reclaims_expired_lease (+1 more) | database | yes |
| `i1-fail` | Retry with backoff, then dead letter | app/features/confluence_sync/tests/test_job_queue.py | test_fail_backs_off_then_dead_letters (+3 more) | database | yes |
| `i1-handle` | Handle and complete in one transaction | app/features/confluence_sync/tests/test_worker_sync.py | test_i1_handle_and_complete_roll_back_together_on_handler_failure (+3 more) | database | yes |
| `i2-fetch` | Fetch the page facts | app/features/confluence_sync/tests/test_worker_sync.py | test_i2_fetch_always_refetches_meta_labels_restrictions_attachments_even_when_unchanged (+2 more) | database | yes |
| `i2-meta` | Metadata only: update in place | app/features/confluence_sync/tests/test_worker_sync.py | test_permission_change_is_metadata_only (+2 more) | database | yes |
| `i2-nochange` | No change | app/features/confluence_sync/tests/test_attachment_wiring.py | test_i2_nochange_no_change_resync_still_stamps_last_reconciled_at (+1 more) | database | yes |
| `i2-tobuild` | On to ingestion stage 3 | app/features/confluence_sync/tests/test_attachment_wiring.py | test_i2_tobuild_body_and_attachment_blocks_both_reach_chunker | database | yes |
| `i2-inplace` | Update tags, state and restrictions in place | app/features/confluence_sync/tests/test_worker_sync.py | test_i2_inplace_writes_page_source_and_every_active_chunk (+2 more) | database | yes |
| `i3-blocks` | Normalize HTML into blocks | app/features/ingestion/tests/test_normalization.py | test_i3_blocks_input_is_storage_html_plus_attachment_text (+2 more) | unit | yes |
| `i3-parents` | Parent chunks | app/features/ingestion/tests/test_chunking.py | test_i3_parents_size_target_1200_hard_cap_2000 (+1 more) | unit | yes |
| `i3-children` | Child chunks | app/features/ingestion/tests/test_chunking.py | test_i3_children_size_target_400_min_150_max_750 (+2 more) | unit | yes |
| `i3-context` | Contextualize each child | app/features/ingestion/tests/test_contextualizer.py | test_i3_context_note_is_capped_at_128_tokens (+7 more) | unit | yes |
| `i3-tsv` | The keyword index | app/features/confluence_sync/tests/test_ingestion_pipeline.py | test_i3_tsv_column_is_children_only (+2 more) | database | yes |
| `i4-document` | Ensure the document row | app/features/confluence_sync/tests/test_versioning_document.py | test_i4_document_one_row_per_page_across_rebuilds (+1 more) | database | yes |
| `i4-chunks` | Insert the chunks inactive | app/features/confluence_sync/tests/test_versioning_chunks.py | test_i4_chunks_parents_persisted_before_children_are_linked (+2 more) | database | yes |
| `i4-gate` | Validation gate | app/features/confluence_sync/tests/test_versioning_gate.py | test_i4_gate_zero_children_marks_version_failed (+1 more) | database | yes |
| `i4-swap` | The pointer swap | app/features/confluence_sync/tests/test_versioning_swap.py | test_i4_swap_old_version_superseded_and_its_chunks_inactive (+2 more) | database | yes |
| `i4-failed` | A failed version never activates | app/features/confluence_sync/tests/test_versioning_failed.py | test_i4_failed_version_persists_as_a_record (+1 more) | database | yes |
| `i4-gc` | Garbage collect old versions | app/features/confluence_sync/tests/test_versioning_gc.py | test_i4_gc_keeps_the_two_most_recent_superseded_versions (+1 more) | database | yes |
| `i4-rollback` | Rollback to an older version | app/features/confluence_sync/tests/test_versioning_rollback.py | test_i4_rollback_same_content_sync_reports_no_change (+1 more) | database | yes |
| `tg-add` | Add a label | app/features/confluence_sync/tests/test_scope_tagging_add.py | test_tg_add_label_only_change_updates_tags_without_rebuild (+1 more) | database | yes |
| `tg-change` | Change a label | app/features/confluence_sync/tests/test_scope_tagging_change.py | test_tg_change_label_swap_leaves_no_stale_double_tag (+1 more) | database | yes |
| `tg-first` | The page is in the index | app/features/confluence_sync/tests/test_scope_tagging_first.py | test_tg_first_page_indexed_with_tags_already_resolved (+1 more) | database | yes |
| `tg-retag` | Tags updated without a re-embed | app/features/confluence_sync/tests/test_scope_tagging_retag.py | test_tg_retag_metadata_only_touches_tags_and_scope_state_not_version_or_embeddings | database | yes |
| `r1-proxy` | The widget's proxy route | apps/web/src/platform/automation-api/tests/client.test.ts | r1_proxy_forwards_chat_api_key_as_bearer_auth (+1 more) | component (jsdom, not a real browser) | yes |
| `r1-auth` | Verify who is asking | app/platform/config/tests/test_platforms.py | test_hs256_alg_is_forbidden (+15 more) | unit | yes |
| `r1-limits` | Limits and validation | app/features/confluence_sync/tests/test_chat_endpoint.py | test_r1_limits_rate_limit_keyed_on_token_subject_when_tokened (+25 more) | unit, database | yes |
| `r1-small` | Small talk short-circuit | app/features/rag_agent/tests/test_small_talk.py | test_r1_small_match_is_the_whole_message_trailing_punct_stripped_whitespace_collapsed (+10 more) | unit | yes |
| `r1-clarify` | Too vague to search? | app/features/rag_agent/tests/test_clarification.py | test_r1_clarify_twelve_words_is_the_heuristic_boundary (+31 more) | unit | yes |
| `r1-idem` | Idempotency replay | app/features/confluence_sync/tests/test_chat_endpoint.py | test_r1_idem_cache_key_is_scoped_to_token_subject_not_body_principal (+6 more) | database | yes |
| `r1-short` | A short reply without search | app/features/confluence_sync/tests/test_chat_endpoint.py | test_r1_short_small_talk_writes_no_query_trace_row (+1 more) | database | yes |
| `r2-embed` | Embed the question | app/platform/clients/tests/test_embeddings_client.py | test_r2_embed_page_model_matches_question_model (+1 more) | unit | yes |
| `r2-gucs` | Set the scope for this transaction | app/features/retrieval/tests/test_search_repo_gucs.py | test_r2_gucs_source_scope_uses_bound_param_not_interpolated (+4 more) | unit | yes |
| `r2-dense` | Dense search | app/features/retrieval/tests/test_search_repo_dense.py | test_r2_dense_uses_cosine_operator (+5 more) | unit | yes |
| `r2-keyword` | Keyword search | app/features/retrieval/tests/test_search_repo_keyword.py | test_r2_keyword_and_rewritten_to_or_in_query (+4 more) | unit | yes |
| `r2-indexes` | The two search indexes | app/platform/db/tests/test_models_indexes.py | test_r2_indexes_hnsw_uses_hnsw_method_with_dimension_correct_opclass (+4 more) | database | yes |
| `r3-reader` | rag_reader | app/platform/db/tests/test_reader_default_privileges.py | test_r3_reader_default_privileges_cover_a_table_created_after_role_provisioning (+3 more: role attributes + pre-existing-table grant in test_r3_reader_role_protect.py, engine binding in test_engine_reader_role.py) | database, unit | yes |
| `r3-source` | Source row security | app/features/confluence_sync/tests/test_retrieval_eval.py | test_r3_source_no_guc_returns_zero_rows (+2 more) | database | yes |
| `r3-acl` | Page-level access list | app/features/retrieval/tests/test_permission_filter.py | test_r3_acl_restricted_page_never_reaches_reranker_for_unlisted_principal (+1 more) | unit | yes |
| `r3-torerank` | Only permitted candidates move on | app/features/retrieval/tests/test_torerank_handoff.py | test_rt3_torerank_caps_at_rerank_depth_after_locks_pass (+1 more) | unit | yes |
| `r3-deny` | A forgotten scope leaks nothing | app/features/confluence_sync/tests/test_retrieval_eval.py | test_rls_default_deny_on_reader_role | database | yes |
| `r3-groups` | Groups expanded at sync time | app/features/confluence_sync/tests/test_worker_sync.py | test_rt3_duplicate_restriction_principal_stores_one_row_per_account_id (+ endpoint/cache/fail-closed proven in test_confluence_client.py's test_http_client_group_restriction_expands_via_group_member_lookup, test_http_client_group_member_lookup_is_cached_across_pages, test_group_restriction_resolver_finding_no_members_still_fails_closed) | database, unit | yes |
| `r4-rerank` | Cohere cross-encoder rerank | app/platform/clients/tests/test_reranker_client.py | test_fake_is_deterministic_order_preserving_and_truncates (+10 more, incl. test_r4_rerank_retries_on_retryable_status_then_succeeds) | unit | yes |
| `r4-weak` | Is the best passage too weak? | app/features/rag_agent/tests/test_refusal.py | test_weak_score_when_between_offtopic_and_refusal_threshold (+6 more) | unit | yes |
| `r4-proceed` | Top-k children move on to stage 5 | app/features/retrieval/tests/test_retrieval_handoff_contract.py | test_r4_proceed_retrieval_output_shape_matches_what_evidence_assembly_consumes | unit | yes |
| `r5-evidence` | The evidence block | app/features/rag_agent/tests/test_prompt.py | test_build_evidence_block_numbers_markers_from_one_in_hit_order (+4 more) | unit | yes |
| `r5-generate` | Generate the answer | app/features/rag_agent/tests/test_llm_client.py | test_generate_redacts_pii_and_sends_cached_system_block (+3 more) | unit | yes |
| `r5-enforce` | Valid citation-number checking | app/features/rag_agent/tests/test_citations.py | test_keeps_cited_sentence_and_reports_used_markers (+7 more) | unit | yes |
| `r5-stream` | Completed-answer replay and the trace row | app/features/confluence_sync/tests/test_chat_endpoint.py | test_grounded_answer_streams_start_token_citations_done (+4 more) | database | yes |
| `r5-nocite` | Refuse: nothing survived the checks | app/features/rag_agent/tests/test_answer_service.py | test_no_citations_refusal_emits_human_handoff_log_with_verbatim_original_query (+1 more) | unit | yes |
| `r5-image` | Image analysis | app/features/rag_agent/tests/test_llm_client.py + test_answer_service.py | test_generate_image_analysis_redacts_query_and_sends_image_blocks (+6 more, incl. test_r5_image_only_the_newest_turns_image_triggers_analysis in test_answer_service.py) | unit | yes |
| `r5-feedback` | Thumbs up or down | app/features/confluence_sync/tests/test_chat_endpoint.py | test_feedback_updates_trace_row (+3 more) | database | yes |
| `w-launcher` | Launcher and teaser | use-widget-visibility.test.tsx | w_launcher_teaser_shows_3s_after_load_and_reschedules_20s_after_close_or_dismiss (+7 more) | component (jsdom, not a real browser) | yes |
| `w-panel` | The panel | panel-body.test.tsx | w_panel_layout_is_fixed_right_edge_full_height_clamped_width (+3 more) | component (jsdom, not a real browser) | yes |
| `w-composer` | The composer | composer.test.tsx | w_composer_screenshot_button_reaches_the_same_attachment_state_as_file_picker_and_paste (+6 more) | component (jsdom, not a real browser) | yes |
| `w-scope` | Which platform is this widget in? | chat-session-provider.test.tsx | w_scope_set_once_from_mount_prop_ignores_later_prop_changes (+3 more) | component (jsdom, not a real browser) | yes |
| `w-token` | The user token | iframe-bridge.test.ts | sets the token from obi:token when the origin is allowed and the source is the parent (+16 more) | component (jsdom, not a real browser) | yes |
| `w-proxy` | The proxy route | route-handlers.test.ts | w_proxy_post_chat_route_wires_to_handle_post_chat (+5 more) | component (jsdom, not a real browser) | yes |
| `w-i18n` | Six locales | i18n.test.ts | w_i18n_every_locale_has_every_required_copy_key (+4 more) | component (jsdom, not a real browser) | yes |
| `w-screenshot` | Screenshot of the page behind the widget | panel-body.test.tsx | w_screenshot_uses_html_to_image_toBlob (+5 more) | component (jsdom, not a real browser) | yes |
| `w-render` | Rendering the answer | message-bubble.test.tsx | w_render_appends_streamed_tokens_as_they_arrive (+4 more) | component (jsdom, not a real browser) | yes |
| `d-event_ledger` | event_ledger | app/features/confluence_sync/tests/test_event_ledger_constraints.py | test_d_event_ledger_payload_hash_is_unique (+2 more) | database | yes |
| `d-document` | document | app/features/confluence_sync/tests/test_document_constraints.py | test_d_document_page_id_unique_constraint (+2 more, plus 2 in test_versioning_document.py) | database | yes |
| `d-reconciliation_run` | reconciliation_run | app/features/confluence_sync/tests/test_reconciliation.py | test_d_reconciliation_run_persists_scope_kind_status_and_counts (+2 more, plus 4 pre-existing) | database | yes |
| `d-page_restriction` | page_restriction | app/features/confluence_sync/tests/test_worker_sync.py | test_d_page_restriction_unchanged_hash_leaves_rows_untouched (+3 pre-existing covering the panel) | database | yes |
| `s-edge` | The edge | app/features/rag_agent/tests/test_edge_auth.py | test_s_edge_host_key_rejects_unconfigured_and_wrong_key (+2 more) | unit | yes |
| `s-source` | Source row security | app/features/confluence_sync/tests/test_retrieval_eval.py; app/features/confluence_sync/tests/test_reader_vector_access.py | test_s_source_fails_closed_with_no_guc_set (+1 more: test_s_source_separates_whole_source_systems_by_source_id) | database | yes |
| `s-acl` | Page access list | app/features/confluence_sync/tests/test_retrieval_eval.py | test_s_acl_no_restriction_recorded_is_open_to_everyone (+2 more: test_s_acl_unexpandable_group_denies_everyone, test_s_acl_filter_runs_before_rerank_in_the_app_on_candidates) | database | yes |
| `s-permitted` | The permitted rows | app/features/confluence_sync/tests/test_retrieval_eval.py | test_s_permitted_denied_row_text_never_reaches_reranker (+1 more: test_s_permitted_trace_records_allowed_sources_and_knowledge_scopes) | database | yes |
| `s-writer` | The writer (table owner) | app/features/confluence_sync/tests/test_force_rls_managed_postgres.py | test_s_writer_owner_reads_and_writes_without_rls_policy_match (+2 more: test_s_writer_chunk_rls_enabled_but_not_forced, test_s_writer_owner_role_has_no_superuser_or_bypassrls) | database | yes |
| `s-reader` | rag_reader | app/features/retrieval/tests/test_s_reader_role_usage.py; app/features/rag_agent/tests/test_s_reader_curated_fetch.py; app/features/confluence_sync/tests/test_reader_vector_access.py | test_s_reader_hybrid_retriever_search_transaction_runs_as_rag_reader (+4 more: test_s_reader_hybrid_retriever_parent_fetch_runs_as_rag_reader, test_s_reader_answer_service_curated_fetch_runs_as_rag_reader, test_s_reader_no_guc_set_returns_zero_rows, test_s_reader_cannot_insert_update_delete_or_create_table) | database | yes |
| `s-anon` | Supabase's public roles | app/platform/db/tests/test_s_anon_public_grant.py; app/features/confluence_sync/tests/test_reader_rls_reconcile.py | test_s_anon_schema_module_never_revokes_the_supabase_grant (+3 more: test_s_anon_migrations_never_revoke_the_supabase_grant, test_s_anon_no_policy_ever_names_anon_or_authenticated, test_s_anon_denied_by_rls_despite_grant_independent_of_reader_policy) | unit, database | yes |
| `s-audit` | The audit trail | app/features/confluence_sync/tests/test_chat_endpoint.py; app/features/rag_agent/tests/test_answer_service.py; app/features/confluence_sync/tests/test_webhook.py; app/features/confluence_sync/tests/test_reconciliation.py; app/features/confluence_sync/tests/test_ingestion_pipeline.py | test_s_audit_query_trace_persists_every_named_field_plus_subject_and_feedback (+3 more: test_s_audit_refusal_emits_human_handoff_log_with_trace_id_raw_query_and_reason, test_s_audit_reconciliation_run_row_persisted_per_sweep, test_s_audit_knowledge_scope_conflict_log_line_emitted_on_conflicting_labels; webhook_event proven by test_s_audit_webhook_event_log_line_carries_type_page_actor_and_outcome) | unit, database | yes |
| `ks-index` | Pages go in | app/features/confluence_sync/tests/test_scope_tagging_ks_index.py | test_ks_index_page_tagged_by_real_pipeline_is_searchable_in_its_scope (+3 more) | database | yes |
| `vd-text` | The text that becomes a vector | app/features/ingestion/tests/test_contextualizer.py; app/features/confluence_sync/tests/test_vector_data_text.py | test_vd_text_input_composed_title_heading_context_then_child_text (+2 more: test_vd_text_size_lands_near_400_tokens in the same file, test_vd_text_child_text_kept_separately_for_citations in app/features/confluence_sync/tests/test_vector_data_text.py) | unit; database | yes |
| `vd-column` | chunk.embedding | app/features/confluence_sync/tests/test_vector_data_column.py | test_vd_column_embedding_is_nullable (+2 more) | database | yes |
| `vd-hnsw` | The HNSW index | app/features/confluence_sync/tests/test_reader_vector_access.py | test_vd_hnsw_name_is_ix_chunk_embedding_hnsw (+2 more) | database | yes |
| `vd-nearest` | The nearest 75 | app/features/retrieval/tests/test_vector_data_nearest.py | test_vd_nearest_orders_by_distance_then_page_id_on_ties (+2 more) | database | yes |
| `vd-rls` | Row security covers vectors too | app/features/confluence_sync/tests/test_reader_vector_access.py | test_vd_rls_the_vector_sits_on_the_chunk_row (+2 more) | database | yes |
| `vd-question` | The question vector | app/platform/clients/tests/test_embeddings_client.py; app/features/retrieval/tests/test_search_repo_dense.py | test_vd_question_uses_the_same_embedding_model_as_page_embedding, test_vd_question_embed_produces_exactly_one_vector_of_3072_numbers, test_vd_question_compared_to_child_vectors_by_cosine_distance (+2 pre-existing: test_fake_provider_is_deterministic_and_right_dim, test_r2_embed_page_model_matches_question_model) | unit | yes |
| `vd-keyword` | The keyword side | app/features/confluence_sync/tests/test_ingestion_pipeline.py | test_vd_keyword_column_built_from_title_heading_path_and_text_english (+2 more: test_vd_keyword_gin_index_exists_over_tsv in the same file, test_vd_keyword_query_or_joins_words_and_ranks_by_ts_rank in app/features/retrieval/tests/test_vector_data_keyword.py) | database | yes |
| `vd-swap` | Vectors swap with the page | app/features/confluence_sync/tests/test_worker_sync.py | test_vd_swap_new_chunks_and_vectors_inserted_inactive (+2 more) | database | yes |
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

## p0-s0_5-reg-ingestion-stage-3 — Protect: Ingestion, stage 3 (5 panels)

Done 2026-09-17, one obi-implementer subagent per panel (i3-parents/i3-children shared one subagent —
same test file), running in parallel. `make test-unit` 466 passed (was 460, per the
`p0-s0_5-reg-ingestion-stage-2` re-verify entry — 6 new unit tests), `make test-db` 215 passed +
1 xfailed (was 212 — 3 new i3-tsv tests). All 5 rows above
updated to cite the panel-id-named test proving each check.

- `i3-blocks` (3 checks: Input, Output, Kept whole) — already fully covered by 3 pre-existing
  panel-id-named tests from an earlier batch (`test_i3_blocks_input_is_storage_html_plus_attachment_text`,
  `test_i3_blocks_output_is_flat_block_list_with_heading_path`,
  `test_i3_blocks_kept_whole_table_and_code_never_split`). No new test needed.
- `i3-parents` (2 checks: Size, Boundary) — 2 new tests added to `test_chunking.py`:
  `test_i3_parents_size_target_1200_hard_cap_2000`, `test_i3_parents_boundary_never_crosses_heading_section`.
- `i3-children` (3 checks: Size, Overlap, Identity) — 3 new tests added to `test_chunking.py`:
  `test_i3_children_size_target_400_min_150_max_750`, `test_i3_children_overlap_12_percent`,
  `test_i3_children_identity_four_keys_present`.
- `i3-context` (3 checks: Prefix, Note, Cost) — Prefix and Cost were already covered by existing tests;
  the Note check's max-128-token cap had never been asserted anywhere — 1 new test added:
  `test_i3_context_note_is_capped_at_128_tokens`. Disclosed finding, not "red today": this was a real
  gap in existing coverage (not a code defect — the cap is honored in code, just previously unproven).
- `i3-tsv` (3 checks: Column, Built from, Index) — none of the 3 checks were actually proven by the two
  pre-existing citing tests (they proved adjacent facts, not these exact checks) — 3 new database-level
  tests added to `test_ingestion_pipeline.py`: `test_i3_tsv_column_is_children_only`,
  `test_i3_tsv_built_from_title_heading_path_and_text`, `test_i3_tsv_gin_index_scoped_to_active_children`.

9 new tests total (0 + 2 + 3 + 1 + 3). No production code changed — every check in scope was already
true today; this batch only closed gaps in what proved it.

## p0-s0_5-reg-knowledge-scopes — Protect: Knowledge scopes (5 panels)

Done 2026-09-17, one obi-implementer subagent per panel (`tg-add`, `tg-change`, `tg-first`,
`tg-retag`, `ks-index` — none shared a test file, so 5 subagents ran fully in parallel). `make
test-unit` 466 passed (unchanged from the prior `p0-s0_5-reg-ingestion-stage-4` entry — no new
unit tests here), `make test-db` 222 passed + 1 xfailed (was 218 — 4 new database tests: 1 tg-add
+ 1 tg-change + 2 ks-index). All 5 rows above updated to cite the panel-id-named test proving
each check.

- `tg-add` (2 checks: `active_doc_version_id` unchanged, page appears in the new scope's results) —
  the first check was already covered by the pre-existing `test_tg_add_label_only_change_updates_tags_without_rebuild`.
  The second check had no test anywhere proving a label-add makes a page searchable through the
  real sync → retrieval path (the only retrieval-side test stamped `chunk.tags` directly via SQL,
  bypassing the tagging pipeline) — 1 new end-to-end test added:
  `test_tg_add_label_only_change_makes_page_appear_in_new_scope_on_next_question`.
- `tg-change` (1 check: no stale double tag after mews to toast) — the existing
  `test_tg_change_label_swap_leaves_no_stale_double_tag` covered the coalesced-delivery path
  (one pending job) but not the panel's other named-equivalent path (`label_deleted` then
  `label_added` as two distinct queued jobs, which get distinct idempotency keys and never dedupe
  at enqueue time) — 1 new test added: `test_tg_change_sequential_label_jobs_converge_without_double_tag`.
- `tg-first` (2 checks: first build activates with label tags, a later label is metadata-only) —
  both already fully covered: the first by the file's own `test_tg_first_page_indexed_with_tags_already_resolved`,
  the second by `tg-add`'s and `tg-retag`'s own tests (the identical metadata-only/no-rebuild
  transition, proven more precisely there). No new test needed.
- `tg-retag` (1 check, enumerated touched/untouched surfaces) — the existing
  `test_tg_retag_metadata_only_touches_tags_and_scope_state_not_version_or_embeddings` already
  asserts every named field. No new test needed.
- `ks-index` (3 checks: stages 2-4 run on the queued page, chunks carry the recognized labels,
  the page is now searchable) — the first two checks were already proven generically by the
  ingestion-stage panels and by `tg-first`'s own test; the third had no test anywhere combining
  the real label-driven tagging pipeline with a knowledge-scope-filtered retrieval query (the only
  prior citation, `test_all_active_chunks_scope_tagged_is_ready`, checks chunk tags directly, not
  searchability, and isn't named after this panel) — 2 new tests added in a new file
  `test_scope_tagging_ks_index.py`: `test_ks_index_page_tagged_by_real_pipeline_is_searchable_in_its_scope`,
  `test_ks_index_page_not_searchable_outside_its_scope`.

4 new database tests total (1 + 1 + 0 + 0 + 2). No production code changed — every check in scope
was already true today; this batch only closed gaps in what proved it.

### Follow-up: `tg-first` and `ks-index` naming gaps closed (2026-09-17)

The re-verify pass above found 3 checks proven only under another panel's test name, not their
own (`tg-first`'s second check; `ks-index`'s first and second checks). Rather than leave those as
a disclosed letter-of-the-rule gap, the owner asked for dedicated panel-id-named tests. 3 new
tests added, all green, no production code changed:

- `tg-first`'s second check ("a later label on an indexed page is a metadata-only update") — 1 new
  test in `test_scope_tagging_first.py`: `test_tg_first_later_label_after_first_build_is_metadata_only`
  (page 3004, first build then a later label change, asserts `metadata_only` outcome and no new
  `document_version`).
- `ks-index`'s first check ("the queued job runs ingestion stages 2 to 4") — 1 new test in
  `test_scope_tagging_ks_index.py`: `test_ks_index_queued_job_runs_stages_2_to_4_on_the_page`
  (enqueues a real `sync_page` job for a never-before-indexed page via `enqueue_sync`/`run_once`
  directly, not the `index_page` convenience wrapper, then asserts stage 2/3/4's outcomes: tagged
  `page_source`, active chunks, active `document_version`).
- `ks-index`'s second check ("tags on the chunks are the recognized labels") — 1 new test in the
  same file: `test_ks_index_chunk_tags_carry_the_recognized_label` (asserts every active child
  chunk's own `tags` field, not just `page_source.tags`, carries the recognized label).

All 5 panels in this substep now have every one of their checks proven by a test literally named
for that panel: `tg-add` 2/2, `tg-change` 1/1, `tg-first` 2/2, `tg-retag` 1/1, `ks-index` 3/3.
`make test-unit` 466 passed (unchanged), `make test-db` 225 passed + 1 xfailed (was 222 — 3 new
tests) — both from the repo root, whole-fix run. `uv run ruff check`/`ruff format --check`/
`uv run pyright` clean on both touched files, 0 new errors.

## p0-s0_5-reg-retrieval-stage-3 — Protect: Retrieval, stage 3 (6 panels)

One obi-implementer subagent per panel (`r3-reader`, `r3-source`, `r3-acl`, `r3-torerank`,
`r3-deny`, `r3-groups`), run in parallel. This entry covers only `r3-groups`'s own subagent; the
other five panels' work is recorded by their own edits to the table rows above.

- `r3-groups` (3 checks: v1 group member list endpoint per group cached per sync run, an
  unexpandable group fails closed via a sentinel no real caller can hold, one `page_restriction`
  row per (page, account id)) — the first two checks were already proven by pre-existing tests in
  `app/platform/clients/tests/test_confluence_client.py`
  (`test_http_client_group_restriction_expands_via_group_member_lookup`,
  `test_http_client_group_member_lookup_is_cached_across_pages`,
  `test_http_client_group_member_lookup_paginates_without_doubling_wiki_prefix`,
  `test_group_restriction_resolver_finding_no_members_still_fails_closed`,
  `test_http_client_group_member_lookup_failure_stays_fail_closed`) and, for fail-closed actually
  denying access at retrieval time rather than just persisting the sentinel,
  `app/features/confluence_sync/tests/test_retrieval_eval.py::test_s_acl_unexpandable_group_denies_everyone`.
  No new test needed for either. The third check had no test anywhere: `_replace_restrictions`
  (`app/features/confluence_sync/application/sync_service.py`) dedupes via `dict.fromkeys(principals)`
  before insert, but nothing asserted a duplicate account id (e.g. an individually-restricted user
  who is also a member of a restricted group) persists as one row, not one per source — 1 new
  database test added to `app/features/confluence_sync/tests/test_worker_sync.py`:
  `test_rt3_duplicate_restriction_principal_stores_one_row_per_account_id`. No production code
  changed — the dedup already worked; this closed the one gap in what proved it.

## p0-s0_5-reg-the-relational-database — Protect: The relational database (4 panels)

Done 2026-09-17, one obi-implementer subagent per panel (`d-event_ledger`, `d-document`,
`d-reconciliation_run`, `d-page_restriction` — none shared a test file, so all 4 subagents ran
fully in parallel). `make test-unit` 507 passed (unchanged — no new unit tests here), `make
test-db` 254 passed + 1 xfailed (was 247 — 7 new database tests: 0 event_ledger + 3 document +
3 reconciliation_run + 1 page_restriction). All 4 rows above updated to cite the panel-id-named
test(s) proving each check.

- `d-event_ledger` (checks: `payload_hash` unique, `delivery_id` partial-unique, `proc_status`
  enum) — already fully covered by 3 pre-existing panel-id-named tests in
  `test_event_ledger_constraints.py` (`test_d_event_ledger_payload_hash_is_unique`,
  `test_d_event_ledger_delivery_id_partial_unique`, `test_d_event_ledger_proc_status_enum_values`).
  No new test needed. Disclosed finding, not "red today": the panel's Columns list names `actor`,
  but `EventLedger` has no `actor` column — only `actor_account_id`, used for logging and the
  self-generated check but never persisted to `event_ledger`. Not fixed here (test-writing
  substep); flagged for a future design-review pass.
- `d-document` (checks: one row per page across rebuilds, `page_id` UNIQUE, deferrable FK to
  `page_source`) — "one row per page" and the stable-id purpose were already covered by
  `test_versioning_document.py`'s 2 existing tests. The `page_id UNIQUE` constraint and the
  deferred-FK behavior had never been directly exercised — 3 new tests added in a new file
  `test_document_constraints.py`: `test_d_document_page_id_unique_constraint`,
  `test_d_document_page_id_fk_deferred_to_commit`,
  `test_d_document_page_id_fk_satisfied_before_commit`.
- `d-reconciliation_run` (checks: one row per sweep, columns scope/kind/status/pages_scanned/
  drift_detected/jobs_enqueued/orphans_deleted/errors/report) — the existing tests only asserted
  the in-memory counters `run_reconciliation()` returns, never the persisted row's own columns —
  3 new tests added to `test_reconciliation.py`:
  `test_d_reconciliation_run_persists_scope_kind_status_and_counts` (re-queries the committed row,
  asserts every named column plus the `report` JSONB),
  `test_d_reconciliation_run_scope_column_reflects_space_scoped_sweep` (`reconcile_space` writes
  `scope="space:100"`, not `"all"`), and
  `test_d_reconciliation_run_records_errors_and_failed_status_on_sweep_exception` (a sweep that
  errors lands `status=failed`, `errors=1`, not silently `completed`).
- `d-page_restriction` (checks: one row per (page, principal), zero-rows-means-open, written as
  delete-plus-insert when `access_scope_hash` changes) — the first two checks and the "changes"
  half of the third were already covered by pre-existing tests
  (`test_rt3_duplicate_restriction_principal_stores_one_row_per_account_id`,
  `test_first_index_persists_restrictions`, `test_permission_change_is_metadata_only`,
  `test_dropped_restriction_leaves_page_unrestricted`). The "when it changes" guard's converse —
  that an unrelated metadata-only sync leaves the rows untouched when `access_scope_hash` is
  unchanged — had no test anywhere; 1 new test added to `test_worker_sync.py`:
  `test_d_page_restriction_unchanged_hash_leaves_rows_untouched` (plants a sentinel `created_at`,
  triggers an unrelated label-only resync, asserts the restriction rows' `created_at` survives
  unchanged — proving no delete+insert ran).

7 new database tests total (0 + 3 + 3 + 1). No production code changed — every check in scope
was already true today; this batch only closed gaps in what proved it.

## p0-s0_5-reg-the-vector-database — Protect: The vector database (8 panels)

Done 2026-09-17, one obi-implementer subagent per panel (`vd-text`, `vd-column`, `vd-nearest`,
`vd-question`, `vd-keyword`, `vd-swap` each solo; `vd-hnsw` + `vd-rls` paired since both shared
one pre-existing citing test — 7 subagents total, no file conflicts). `make test-unit` 512 passed
(was 507 — 5 new unit tests: 2 vd-text + 3 vd-question), `make test-db` 268 passed + 1 xfailed
(was 254 — 14 new database tests: 1 vd-text + 6 vd-hnsw/vd-rls + 1 vd-nearest + 3 vd-keyword + 3
vd-swap; `vd-column` added 0 new tests, strengthening an existing one instead). All 8 rows above
updated to cite the panel-id-named test(s) proving each check; no production code changed anywhere
in this batch — every check was already true today, this batch only closed gaps in what proved it.

- `vd-text` (checks: input = title + heading path + context note + child text; ~400 tokens; child
  text kept separately for citations) — the one pre-existing citing test only proved part of the
  first check. 3 new tests added across 2 files:
  `test_contextualizer.py::test_vd_text_input_composed_title_heading_context_then_child_text`,
  `test_contextualizer.py::test_vd_text_size_lands_near_400_tokens`,
  `test_vector_data_text.py::test_vd_text_child_text_kept_separately_for_citations` (new file).
- `vd-column` (checks: `vector(3072)` nullable; child chunks only; same row as text/tags/
  scope_state/tsv) — all three checks already had panel-id-named tests from 0.5.3's "the store"
  batch; the "same row" test only asserted `tags`/`tsv` alongside the embedding. Closed by adding
  `retrieval_content`/`display_content` assertions to the existing
  `test_vd_column_embedding_colocated_with_tags_and_tsv_on_same_row` rather than a new test —
  `scope_state` has no separate column (it is `chunk.tags`, same disclosure as `tg-retag`).
- `vd-hnsw` + `vd-rls` (6 checks combined: index name, halfvec/cosine cast, m=16/ef_construction=200
  build; embedding on the chunk row, source+scope policies cover every SELECT on chunk, a forbidden
  row's nearest-neighbor hit never returns) — both panels shared one pre-existing citing test that
  proved neither. 6 new tests added to `test_reader_vector_access.py`, all read directly off the
  real Postgres catalog (`pg_indexes`/`pg_class`/`pg_policies`) or proven behaviorally against
  `rag_reader`, never off `models.py`'s Python text. Disclosed finding, not "red today": the repo's
  test-suite `EMBEDDING_DIM=256` override falls under pgvector's halfvec threshold, so a stock
  `make test-db` run builds the index's plain `vector_cosine_ops` branch rather than
  `halfvec_cosine_ops` — already identically disclosed under `r2-indexes`; the new test branches on
  the model's own dimension so it stays honest either way.
- `vd-nearest` (checks: `ORDER BY ... LIMIT 75`; row security filters first; ties broken by page
  id) — the tie-break and row-security-first checks already had dedicated tests from 0.5.3. Only
  the 75-row cap itself had no test exercising the actual boundary (the existing test never
  returned more than 60 rows). 1 new test added:
  `test_vector_data_nearest.py::test_vd_nearest_limit_caps_the_result_at_75_nearest` (seeds 80
  chunks at 80 distinct distances, asserts exactly the 75 nearest come back).
- `vd-question` (checks: same embedding model as the page; exactly one 3072-number vector; compared
  to child vectors by cosine distance) — the first two checks were only covered by citation from
  other panels; the third had no dedicated proof at all (only `r2-dense`'s SQL-shape assertions
  against a spy session). 3 new unit tests added:
  `test_embeddings_client.py::test_vd_question_uses_the_same_embedding_model_as_page_embedding`,
  `test_embeddings_client.py::test_vd_question_embed_produces_exactly_one_vector_of_3072_numbers`,
  `test_search_repo_dense.py::test_vd_question_compared_to_child_vectors_by_cosine_distance`.
- `vd-keyword` (checks: `tsv` built from title/heading path/text, English config; GIN index
  `ix_chunk_tsv_gin`; OR-joined query ranked by `ts_rank`) — the one pre-existing citing test only
  proved a weaker claim (some word findable via `plainto_tsquery`). 3 new tests added:
  `test_ingestion_pipeline.py::test_vd_keyword_column_built_from_title_heading_path_and_text_english`,
  `test_ingestion_pipeline.py::test_vd_keyword_gin_index_exists_over_tsv`,
  `test_vector_data_keyword.py::test_vd_keyword_query_or_joins_words_and_ranks_by_ts_rank` (new
  file). The Column check deliberately duplicates `i3-tsv`'s own proof under a new name, following
  this batch's established precedent.
- `vd-swap` (checks: new chunks/vectors inserted inactive; one atomic transaction flips the
  pointer; old vectors go inactive at once, rows persist until two more versions supersede them) —
  the one pre-existing citing test proved only the swap's end state, none of the three checks by
  name. 3 new tests added to `test_worker_sync.py`:
  `test_vd_swap_new_chunks_and_vectors_inserted_inactive` (a `before_flush` SQLAlchemy hook, to
  avoid a cross-feature deep import `make boundaries` would reject),
  `test_vd_swap_pointer_flip_is_one_atomic_transaction`,
  `test_vd_swap_old_vectors_go_inactive_at_once_but_rows_persist` (explicitly does not re-prove the
  two-more-versions deletion count, which is `i4-gc`'s own panel).

19 new tests total across the batch (5 unit + 14 database, by the count above), plus one existing
test strengthened for `vd-column`. Whole-batch verification run centrally after all 7 subagents
returned: `make test-unit` → 512 passed; `make test-db` → 268 passed, 1 xfailed (pre-existing,
unrelated) — both green.

## p0-s0_5-reg-security — Protect: Security (7 panels)

Done 2026-09-18, one obi-implementer subagent per panel (`s-source`, `s-writer`, `s-reader`,
`s-anon`, `s-audit` each solo; `s-acl` + `s-permitted` paired since both cite the same test file,
`test_retrieval_eval.py` — 6 subagents total). `make test-unit` 516 passed (was 512 — 4 new unit
tests: 3 s-anon + 1 s-audit), `make test-db` 280 passed + 1 xfailed (was 268 — 12 new database
tests: 2 s-source + 1 s-acl + 1 s-permitted + 2 s-writer + 5 s-reader + 1 s-audit). All 7 rows
above updated to cite the panel-id-named test(s) proving each check; no production code changed
anywhere in this batch — every check was already true today, this batch only closed gaps in what
proved it.

- `s-source` (2 checks: fails closed with no GUC, separates whole source systems by `source_id`) —
  the row's prior citation (`test_0010_adds_restrictive_scope_policies`) only proved the migration
  adds a policy row, never either check behaviorally. Check 1 was already proven under other
  panels' names (`r3-source`, `r3-deny`); check 2 was proven only for two namespaces of the same
  connector (`vd-rls`), not two genuinely different source systems. 2 new database tests added to
  `test_retrieval_eval.py` / `test_reader_vector_access.py`:
  `test_s_source_fails_closed_with_no_guc_set`, `test_s_source_separates_whole_source_systems_by_source_id`
  (the latter seeds a second `source_type="zendesk"` chunk via a new optional param on the shared
  `_seed_chunk` helper, defaulted so existing callers are unaffected).
- `s-acl` (3 checks: no-restriction is open, unexpandable group denies everyone, filtering runs
  before rerank in the app on candidates) — checks 1-2 already had dedicated panel-named tests;
  check 3 had never been proven. 1 new database test added: `test_s_acl_filter_runs_before_rerank_in_the_app_on_candidates`,
  using a new `_SpyReranker` test helper to show a restricted page's rows are visible under raw RLS
  alone yet never reach the reranker's recorded input.
- `s-permitted` (3 checks: only permitted rows become text, only that text reaches reranker/
  generator, trace records allowed sources/scopes) — checks 1 (partially) and 3 already covered;
  the "only reaches reranker/generator" half of checks 1-2 had no direct proof. 1 new database test
  added: `test_s_permitted_denied_row_text_never_reaches_reranker` (reusing the same `_SpyReranker`
  helper as `s-acl`), showing a denied page's text is never fetched or passed to `rerank()` at all.
- `s-writer` (3 checks: owner reads/writes without RLS policy match, RLS enabled but not FORCEd at
  the catalog level, owner role has neither SUPERUSER nor BYPASSRLS) — check 1 already covered;
  checks 2-3 had only a live/staging equivalent in the "needs live" table, never a local database
  test. 2 new database tests added to `test_force_rls_managed_postgres.py`:
  `test_s_writer_chunk_rls_enabled_but_not_forced` (queries `pg_class.relrowsecurity`/
  `relforcerowsecurity`), `test_s_writer_owner_role_has_no_superuser_or_bypassrls` (queries
  `pg_roles.rolsuper`/`rolbypassrls`).
- `s-reader` (3 checks: `rag_reader` is the role actually bound by `HybridRetriever`'s search
  transaction/curated fetch/parent fetch, fails closed with no GUC, cannot write or create) — none
  of the 3 checks had a test proving the real production wiring end-to-end; the existing `r3-reader`
  tests proved role attributes/grants and a mocked engine binding, not the live call sites. 5 new
  database tests added across 3 files: `test_s_reader_role_usage.py` (new,
  `test_s_reader_hybrid_retriever_search_transaction_runs_as_rag_reader`,
  `test_s_reader_hybrid_retriever_parent_fetch_runs_as_rag_reader`), `test_s_reader_curated_fetch.py`
  (new, `test_s_reader_answer_service_curated_fetch_runs_as_rag_reader` — each spies on a real
  search-repo function already inside the production transaction, captures `SELECT current_user`
  from the actual session `main.py::build_answer_service` wires up, then delegates to the real
  implementation), and `test_reader_vector_access.py`
  (`test_s_reader_no_guc_set_returns_zero_rows`, `test_s_reader_cannot_insert_update_delete_or_create_table`).
- `s-anon` (3 checks: `anon`/`authenticated` hold GRANT SELECT, RLS+no-matching-policy denies
  despite the grant, denial holds independent of `rag_reader`'s own policies) — checks 2-3 already
  covered by the existing `test_reader_freed_but_anon_stays_denied`. Check 1 is **not locally
  testable as a live database fact**: a vanilla local Postgres has no `anon`/`authenticated` roles
  at all — they are a Supabase platform bootstrap, not created by this repo's migrations (mirrors
  `scripts/setup_supabase.py`'s own skip of its anon-impersonation proof for the same reason).
  Disclosed rather than faked: 3 new unit tests added instead, asserting the codebase's side of the
  contract by source scan — `test_s_anon_public_grant.py` (new):
  `test_s_anon_schema_module_never_revokes_the_supabase_grant`,
  `test_s_anon_migrations_never_revoke_the_supabase_grant`,
  `test_s_anon_no_policy_ever_names_anon_or_authenticated`.
- `s-audit` (3 checks: per-query trace persists allowed_sources/allowed_knowledge_scopes/
  candidates/scores/answer/citations/feedback plus subject+decision, per-refusal `human_handoff`
  log line with trace id/raw query/reason, per-sync `reconciliation_run` row plus `webhook_event`/
  `knowledge_scope_conflict` log lines) — check 1 already covered (the "decision" column is
  correctly out of scope: the panel's own `today` line says it stays target-only until action-plan
  substep 3.6.6 builds it); `reconciliation_run` and `knowledge_scope_conflict` logging already
  covered. Only the `human_handoff` panel-named proof and the `webhook_event` log line were
  missing. 2 new tests added: `test_answer_service.py::test_s_audit_refusal_emits_human_handoff_log_with_trace_id_raw_query_and_reason`
  (unit, a different refusal reason than `r5-nocite`'s own test so `s-audit` has independent proof),
  `test_webhook.py::test_s_audit_webhook_event_log_line_carries_type_page_actor_and_outcome`
  (database).

16 new tests total (4 unit + 12 database, by the count above). No production code changed —
every check in scope was already true today; this batch only closed gaps in what proved it.

Deviations and pre-existing issues disclosed unprompted by the subagents (none caused by this
batch's changes, none fixed here since this is a test-writing batch):

- `s-anon`'s check 1 (the GRANT SELECT fact itself) has no local equivalent to test against — see
  above; recorded as a disclosed scope limit, not a gap silently dropped.
- `test_webhook.py` and the full `test_retrieval_eval.py` file both showed intermittent,
  environment-level flakiness (job-count races; Docker/Postgres deadlocks and connection drops in
  older, untouched tests) reproducible on the unmodified base via `git stash` — confirmed unrelated
  to the new tests in both cases, flagged here for a future look rather than fixed in this batch.
- `test_reader_rls_reconcile.py` fails under `pytest-randomly`'s reordering when run in isolation —
  a pre-existing order-sensitivity against its session-scoped fixture, not introduced or fixed here.
- The `s-reader` subagent's own first draft of `test_s_reader_no_guc_set_returns_zero_rows` opened
  an unmanaged owner-role session that deadlocked the next test's autouse `TRUNCATE` fixture; caught
  and fixed before finalizing (reused the fixture-managed session instead) — never landed in the
  committed test.

### Follow-up: literal "named for its own panel" gap closed on re-verify (2026-09-18)

A re-verify pass (run centrally, not per-subagent) checked the letter of the batch's own "Must be
true" bar — every check provable by a test literally named for its own panel, the same bar the
`tg-first`/`ks-index` follow-up above established — against the 7 rows this batch had just filled.
4 panels had at least one check proven only by a citation to a *different* panel's test name, not
their own: `s-permitted` (check 3, trace-scope), `s-writer` (check 1, owner reads/writes), `s-anon`
(checks 2-3, RLS-denies-despite-grant / independent-of-reader-policy), `s-audit` (check 1, the full
per-query trace; and the `reconciliation_run`/`knowledge_scope_conflict` halves of check 3). Rather
than leave those as a disclosed letter-of-the-rule gap, closed all of them with dedicated tests
(none required by a code defect — every underlying fact was already true, following the same
"duplicates X's proof under this panel's own name" precedent as `vd-keyword`'s Column check):

- `s-permitted`: `test_s_permitted_trace_records_allowed_sources_and_knowledge_scopes` added to
  `test_retrieval_eval.py` — a full `retrieve_with_context` call with knowledge-scope filtering
  enabled, asserting the trace row's `allowed_sources` and `allowed_knowledge_scopes` columns.
- `s-writer`: `test_s_writer_owner_reads_and_writes_without_rls_policy_match` added to
  `test_force_rls_managed_postgres.py` — duplicates the pre-existing read proof and extends it to
  an UPDATE as the non-superuser owner role, no GUC set.
- `s-anon`: `test_s_anon_denied_by_rls_despite_grant_independent_of_reader_policy` added to
  `test_reader_rls_reconcile.py` — duplicates `test_reader_freed_but_anon_stays_denied`'s two
  anon-side assertions (before and after `rag_reader` gets its own policy) in one test under this
  panel's own name.
- `s-audit`: 3 tests added — `test_s_audit_query_trace_persists_every_named_field_plus_subject_and_feedback`
  (`test_chat_endpoint.py`, database) is one end-to-end `/chat` + `PATCH .../feedback` request
  proving every column the panel's check 1 names (candidates, scores, allowed sources/scopes,
  answer, citations, feedback, subject hash) in a single test rather than by citation to five
  different panels' tests; `test_s_audit_reconciliation_run_row_persisted_per_sweep`
  (`test_reconciliation.py`, database) and
  `test_s_audit_knowledge_scope_conflict_log_line_emitted_on_conflicting_labels`
  (`test_ingestion_pipeline.py`, database) close the remaining two named artifacts of check 3
  (the `webhook_event` half was already named from the original batch).

6 new tests total (all database). No production code changed. Re-verification run centrally after
all 6 were added: `make test-unit` → 516 passed (unchanged); `make test-db` → 286 passed, 1 xfailed
(was 280 — the 6 new tests); `make boundaries` → clean. All 7 rows above updated so every citation
is now a test literally named for its own panel — `s-source`, `s-acl`, and `s-reader` already met
this bar from the original batch and needed no change here.

## p0-s0_5-reg-code-map — Protect: Code map (5 panels)

Done 2026-09-18, one obi-implementer subagent per panel (`cm-root`, `cm-docs`, `cm-contracts`,
`cm-tokens`, `cm-infra` — none shared a test file, so all 5 subagents ran fully in parallel;
coverage-map rows, this section, the ledger and the progress-log were written centrally by the
orchestrator after all 5 returned, single-writer, to avoid concurrent edits to shared docs). `make
test-unit` 530 passed (was 516 — 14 new unit tests: 3 cm-root + 3 cm-docs + 3 cm-contracts + 2
cm-tokens + 3 cm-infra), `make test-db` 286 passed + 1 xfailed (unchanged — every new test is
unit-level), `make boundaries` clean. No production code changed anywhere in this batch — every
check was already true today; this batch only wrote the net that protects it. All 5 rows above
updated to cite the panel-id-named test(s). Two rows (`cm-root`, `cm-contracts`) previously cited a
real but not-panel-named test (`test_create_app_wires_the_answer_cache_by_default`,
`test_required_claims_match_the_verifier`); repointed to the new dedicated `test_cm_*` files so each
row's citation is literally named for its own panel, same bar as the security/vector batches.

- `cm-root` (3 checks: read settings; build the reader engine, fails closed without
  `DATABASE_READER_URL` outside local; build `HybridRetriever` with embedder, reranker, scope flag) —
  3 new unit tests in `apps/automation/app/tests/test_cm_root_wiring.py` (new package, `__init__.py`
  added): `test_cm_root_reads_settings`, `test_cm_root_reader_engine_fails_closed_without_reader_url_outside_local`,
  `test_cm_root_builds_hybrid_retriever_with_embedder_reranker_and_scope_flag`. Disclosed, not "red
  today": the fail-closed raise itself lives one module down in `platform/db/engine.py`
  (`ReaderRoleMisconfiguredError`); the test drives the real wiring path (`main.build_answer_service`,
  `env="production"`) so it proves the wiring fails closed, and the true fail-open exemption is the
  whole offline set `{local,test,dev,ci}` (`Settings.is_offline_env()`), not literally "local" alone.
  Constructor args are asserted via a spy on `main.HybridRetriever`, not private `_embedder` state.
- `cm-docs` (3 checks: ADR 0001 stack = Postgres+pgvector/FastAPI/Next.js; 0002 retrieval core =
  hybrid/RRF/versioned store; 0003 feature boundaries) — 3 new unit tests in
  `apps/automation/tests/test_cm_docs.py`, each reads `docs/adr/000X-*.md` and asserts the named
  terms (repo root walked up from the test file, ADRs live outside `apps/automation`). Disclosed:
  ADR 0002 writes the concept in full as "Reciprocal Rank Fusion" and never uses the acronym "RRF";
  the test asserts the full phrase (whitespace-collapsed) and guards that "RRF" is absent, with a
  note to update if 0002 ever adopts the acronym.
- `cm-contracts` (3 checks: `src/openapi/chat.yaml` is the source of truth; 6 named types
  ChatRequest/ChatTurn/ImageAttachment/ChatStreamEvent/Citation/FeedbackRequest; the "Planned"
  token-claims.json + iframe-messages.ts) — 3 new unit tests in
  `apps/automation/app/features/rag_agent/tests/test_cm_contracts.py` (placed in the feature that
  owns the chat contract, beside the existing `test_token_claims_contract.py`; PyYAML-parsed).
  Disclosed: both artifacts the panel's Settings still label "Planned" actually exist on disk and are
  wired today (`packages/contracts/src/token-claims.json` carries all note fields;
  `iframe-messages.ts` carries exactly `obi:open`/`obi:token`/`obi:clear`) — matching the panel's own
  Today line, so the test asserts their present wired state; the stale "Planned" label on the design
  page is worth a future design-review correction.
- `cm-tokens` (2 checks: holds colors/type/Tailwind theme mapping; style = light theme, indigo
  accent, Inter) — 2 new unit tests in `apps/automation/tests/code_map/test_cm_tokens.py`, reading
  `packages/design-tokens/src/tokens.ts` and `tailwind-theme.ts`. Disclosed word→value mappings
  (tokens use hex/stacks, not the literal words): "indigo" → accent `#635bff` (asserted the hex and
  its blue-dominance, not the word); "light theme" → near-white surface `#f6f8fa` with dark text
  `#30313d`, asserted via luminance (dark-on-light), not the word; "Inter" → literal substring in
  `font.sans`, asserted directly.
- `cm-infra` (2 checks: docker-compose pgvector pinned to 0.8.x; use = local dev + test DB,
  production is Supabase) — 3 new unit tests in `apps/automation/tests/tools/test_cm_infra.py`
  reading `infra/foundation/docker-compose.yml`. Disclosed: the literal image tag is
  `pgvector/pgvector:pg16@sha256:…`, not a `0.8.x` string — reproducibility is by the digest pin, and
  pgvector 0.8.5 is stated only in the file's comment; the test asserts the actual `pg16` tag, the
  digest pin, and the 0.8.x version at the comment level rather than pretending the tag contains
  "0.8.x". Also disclosed: "production is Supabase" is not provable from the compose (which defines
  only the local/test DB); the test asserts *where the claim is documented* (`CLAUDE.md`) and records
  that `docs/plan/decisions.md` row `live-0.5.3-cm-infra` currently flags it open/red/unconfirmed —
  it never claims production actually runs on Supabase.

14 new unit tests total (3 + 3 + 3 + 2 + 3). No production code changed — every check in scope was
already true today; this batch only closed the gap in what proved it. All 5 panels' every check is
now proven by a test literally named for its own panel: `cm-root` 3/3, `cm-docs` 3/3, `cm-contracts`
3/3, `cm-tokens` 2/2, `cm-infra` 2 checks / 3 tests (the "production is Supabase" half proven as a
documented-claim assertion, not an infra fact — disclosed above).
