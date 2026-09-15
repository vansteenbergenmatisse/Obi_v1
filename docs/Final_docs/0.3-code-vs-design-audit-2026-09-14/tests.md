# 0.3.2 — Test inventory (backend + web) vs. design panels

Audit date: 2026-09-14/15. Backend collected with `uv run pytest --collect-only -q` (612 tests,
0 collection errors). Backend run with `uv run pytest -q` against the local Postgres on :5434 (a
prior attempt reported it up; this run reused that state). Web counted by reading every file under
`apps/web/src` matching `*.test.ts`/`*.test.tsx` (vitest; no `pnpm test` run — source-level count
only, see the note under the web count below).

## Four counts

| Count | Backend | Web | Total |
|---|---|---|---|
| Test files | 71 | 27 | 98 |
| Test functions | 612 (pytest-collected, parametrize expanded) | 181 source `it`/`it.each` blocks (≈196 expanded at runtime — 2 files use `it.each`: `test-host-content.test.tsx` 3→9, `validation.test.ts` 16→25; vitest was not run to confirm the exact runtime count) | 793 source-level / ≈808 expanded |
| Implemented panels (`built`) | 101 (of 192 total; `python3 tools/panel.py --list \| grep '| built$'` → 101 lines) | — | 101 |
| Implemented panels with no test | 35 | — | 35 |

Panel statuses in the file: `built | change | build | unverified | discuss`. Only `built` counts as
"Implemented" per the brief.

---

## 1. Backend test files

### app/features/confluence_sync/tests/test_answer_workflow.py
Level: db (real Postgres, fixture Confluence corpus; only rewrite/generate LLM stages are faked).
- `test_answer_service_grounds_a_cited_answer_end_to_end` — a real indexed question returns a cited, non-refused answer and its query_trace row matches — `r5-generate`
- `test_answer_service_refuses_when_source_scope_excludes_everything` — wrong `allowed_sources` refuses with `no_candidates` — `r4-refuse`
- `test_answer_service_refuses_when_generator_cites_nothing` — an ungrounded generator reply is never persisted; refuses `no_citations` — `r5-nocite`
- `test_answer_service_small_talk_skips_retrieval_even_with_a_real_indexed_corpus` — small talk bypasses retrieval even with real content indexed — `r1-small`

### app/features/confluence_sync/tests/test_attachment_wiring.py
Level: db.
- `test_text_attachment_content_is_indexed_and_searchable` — .txt/.csv attachment text is chunked and searchable — `i3-attach`
- `test_markdown_attachment_content_is_indexed` — .md attachment content indexed — `i3-attach`
- `test_placeholder_pdf_and_xlsx_degrade_to_no_chunk_not_a_crash` — unparseable binaries degrade to no chunk, not a crash — `i3-attach`
- `test_attachment_chunks_inherit_page_acl_and_source` — attachment chunks inherit page_id/source_type/is_active — `i3-attach`
- `test_resyncing_unchanged_page_is_a_true_no_change_not_a_spurious_rebuild` — content_hash stays body-only so an unrelated resync is `no_change` — `i2-nochange`
- `test_unchanged_attachment_reuses_embedding_across_a_body_driven_rebuild` — an unrelated body edit still reuses the unchanged attachment's embedding — `i3-attach`
- `test_oversized_attachment_metadata_is_skipped_before_download` — a byte cap skips download before fetching — `i3-attach`
- `test_unfetchable_attachment_is_skipped_not_a_sync_failure` — a failed download is skipped, sibling attachment still indexed — `i3-attach`
- `test_attachment_only_change_is_metadata_only_disclosed_limitation` — new-attachment-only change is `metadata_only`, picked up on the next rebuild trigger — `i3-attach`

### app/features/confluence_sync/tests/test_chat_endpoint.py
Level: db (real FastAPI TestClient + real indexed corpus; rewrite/generate faked).
- `test_missing_api_key_is_rejected` — no bearer key → 401 — `r1-auth`
- `test_unconfigured_api_key_fails_closed` — empty configured key → 503 — `r1-auth`
- `test_previous_api_key_is_accepted_during_rotation_overlap` — old and new keys both work during rotation — `r1-auth`
- `test_key_outside_current_and_previous_is_rejected` — a third key → 401 — `r1-auth`
- `test_previous_key_stops_working_once_rotation_completes` — dropped previous key → 401 — `r1-auth`
- `test_history_must_end_on_user_turn` — assistant-ending history → 400 — `r1-limits`
- `test_history_too_long_is_rejected` — over `chat_max_history_turns` → 400 — `r1-limits`
- `test_message_too_long_is_rejected` — over `chat_max_message_chars` → 400 — `r1-limits`
- `test_too_many_images_on_a_turn_is_rejected` — over `chat_max_images_per_turn` → 400 — `r1-limits`
- `test_oversized_image_is_rejected` — over `chat_max_image_bytes` → 400 — `r1-limits`
- `test_image_within_caps_is_accepted_and_analysis_reaches_the_done_event` — an accepted image's analysis lands on `done.imageAnalysis`, separate from `answer` — `r5-image`
- `test_tokenless_request_forwards_general_only_and_ignores_body_scope` — no token → general-only scope; body `knowledge_scope` never reaches the service — `r1-ctx`
- `test_malformed_knowledge_scope_is_rejected` — a badly-shaped scope value → 422 — `r1-limits`
- `test_idempotency_key_replay_with_different_field_is_not_the_first_callers_answer[history]` — same Idempotency-Key, different history → distinct trace ids, not a stale replay — `r1-idem`
- `test_numeric_principal_is_rejected_not_treated_as_space_wide_trust` — an all-digit body `principal` → 422 — `r1-limits`
- `test_rate_limit_returns_429` — second call within the window → 429 — `r1-limits`
- `test_rate_limit_is_keyed_by_ip_not_by_rotating_principal` — a rotating body `principal` still hits the same IP-keyed bucket — `r1-limits`
- `test_idempotency_cache_evicts_the_oldest_key_once_max_entries_exceeded` — bounded idempotency cache evicts oldest key — `r1-idem`
- `test_grounded_answer_streams_start_token_citations_done` — SSE emits start/token/citations/done in order, reassembled tokens equal the final answer — `r5-stream`
- `test_refusal_streams_done_with_refused_true` — a refusal's `done` event carries `refused: true`, empty citations — `r4-refuse`
- `test_clarification_done_payload_never_leaks_internal_refusal_categories` — the clarifying `done` payload's key set is exactly the whitelisted PLAN 9.3 fields — `r1-clarify`
- `test_chat_request_log_includes_refusal_reason_when_refused` — the `chat_request` log line carries a populated `refusal_reason` on refusal — `r4-refuse`
- `test_chat_request_log_has_no_refusal_reason_when_not_refused` — no `refusal_reason` on a normal answer's log line — `r5-stream`
- `test_idempotency_key_replays_cached_answer_without_rerunning` — a repeated Idempotency-Key returns the same trace id — `r1-idem`
- `test_answer_cache_replays_without_rerunning_retrieval` — identical request with no Idempotency-Key header still hits the exact-match cache — `r1-idem`
- `test_answer_cache_does_not_cross_token_subject_boundary` — two token subjects never share a cached answer — `r1-idem`
- `test_create_app_wires_the_answer_cache_by_default` — `main.create_app` wraps the real service in `CachingAnswerService` — `cm-root`
- `test_feedback_updates_trace_row` — PATCH feedback updates the query_trace row — `r5-feedback`
- `test_feedback_requires_auth` — unauthenticated feedback PATCH → 401 — `r5-feedback`
- `test_feedback_rejects_invalid_value` — a feedback value outside {-1,1} → 422 — `r5-feedback`

### app/features/confluence_sync/tests/test_curated_knowledge_repo.py
Level: db.
- `test_empty_tags_entry_is_always_included_regardless_of_allowed_scopes` — an empty-tags curated entry is global — `r2-curated`
- `test_scoped_entry_only_returned_when_its_scope_is_allowed` — a scoped entry excluded/included by allow-list — `r2-curated`
- `test_inactive_entry_is_never_returned` — `is_active=false` never returned — `r2-curated`
- `test_cap_enforcement_limits_the_result_count` — `limit` bounds the result count — `r2-curated`
- `test_ordering_is_stable_by_id_for_deterministic_citation_numbering` — stable id-ordering for citation numbering — `r2-curated`
- `test_two_differently_scoped_entries_never_cross_leak` — two customer-scoped entries never cross-leak — `r2-curated`

### app/features/confluence_sync/tests/test_customer_isolation_backstop.py
Level: db (real RLS as `rag_reader`, no app-layer predicate).
- `test_scope_rls_blocks_cross_customer_read_via_guc_alone` — scope GUC alone blocks a cross-customer chunk — `r3-scope`
- `test_scope_rls_fails_closed_when_scope_guc_unset` — unset scope GUC → zero rows (fail closed) — `r3-scope`
- `test_scope_rls_wildcard_is_an_explicit_opt_out` — `'*'` GUC restores unrestricted reads — `r3-scope`
- `test_scope_rls_untagged_chunk_is_global_visible_under_any_scope` — an untagged chunk stays visible under any scope — `r3-scope`
- `test_curated_scope_rls_isolates_tagged_entries_but_keeps_global` — the curated-table analogue of the same RLS backstop — `r2-curated`

### app/features/confluence_sync/tests/test_event_dedup.py
Level: db.
- `test_duplicate_delivery_is_idempotent` — a repeated envelope writes one ledger row, one job — `i1-ledger`
- `test_same_delivery_id_different_payload_dedupes_gracefully_not_500` — a redelivery with a different payload hash still dedupes, no IntegrityError — `i1-ledger`

### app/features/confluence_sync/tests/test_fallback_eval.py
Level: db + eval (real AnswerService, `evaluation` metrics module).
- `test_ambiguity_dataset_cases_trigger_clarification_end_to_end` — every `ambiguity.json` case bypasses retrieval and returns `needs_clarification` — `r1-clarify`
- `test_out_of_corpus_case_refuses_not_clarifies_or_hallucinates` — a genuinely out-of-corpus question refuses `no_candidates` — `r4-refuse`
- `test_citation_grounding_rate_on_a_real_grounded_answer` — the faithfulness-proxy metric scores 1.0 against a real grounded answer — `e-stage4`

### app/features/confluence_sync/tests/test_force_rls_managed_postgres.py
Level: db (ADR-0013, non-superuser owner via `SET ROLE`).
- `test_non_superuser_owner_reads_own_rows` — a non-superuser table owner still reads its own rows (FORCE dropped) — `s-writer`
- `test_non_owner_reader_still_isolated` — the non-owner reader stays source-scoped after the FORCE drop — `s-reader`

### app/features/confluence_sync/tests/test_ingestion_pipeline.py
Level: db.
- `test_children_have_embeddings_and_tsv` — every active child has an embedding of the configured dim and a populated tsv — `i3-embed`
- `test_keyword_tsv_is_queryable` — a keyword query against tsv returns hits — `i3-tsv`
- `test_version_upgrade_is_atomic_and_updates_content` — re-index leaves exactly one active version with updated content — `i4-swap`
- `test_only_one_document_version_active_after_reindex` — exactly one `DocumentVersion.state==active` row, all active chunks point at it — `i4-swap`
- `test_reuse_guard_disables_on_config_change` — a retrieval-schema-version bump disables reuse eligibility — `i3-embed`
- `test_schema_bump_triggers_full_reembed_release` — a schema bump forces a full rebuild at the same cf_version — `i4-swap`
- `test_label_driven_knowledge_scope_tag_unions_with_source_scope` — a recognized label's tag unions with the existing source_scope tag — `tg-retag`
- `test_conflicting_provider_labels_contribute_no_tag_and_log_conflict` — two provider labels contribute no tag and log `knowledge_scope_conflict` — `tg-conflict`

### app/features/confluence_sync/tests/test_job_queue.py
Level: db.
- `test_claim_uses_skip_locked` — two claimants never get the same locked row — `i1-claim`
- `test_fail_backs_off_then_dead_letters` — repeated failure reaches `dead_letter` at `max_attempts` — `i1-fail`
- `test_reap_reclaims_expired_lease` — an expired lease is reclaimed to `pending` — `i1-reaper`

### app/features/confluence_sync/tests/test_knowledge_scope.py
Level: unit (pure, no DB).
- `test_recognized_label_becomes_a_tag` — a recognized label maps to a tag — `i2-labels`
- `test_unrecognized_label_is_ignored` — an unrecognized label contributes no tag — `i2-labels`
- `test_general_plus_one_provider_label_yields_both_tags_no_conflict` — general + one provider label → both tags, no conflict — `i2-labels`
- `test_two_provider_labels_conflict_mews_and_opera_cloud` — two provider labels → conflict, zero tags — `i2-labels`
- `test_two_provider_labels_conflict_mews_and_toast` — the repo's own codename ("toast") is a normal provider label, not special-cased — `i2-labels`
- `test_empty_labels_yield_empty_result` — no labels → empty result — `i2-labels`
- `test_labels_are_trimmed_and_lowercased_before_matching` — label matching is case/whitespace-insensitive — `i2-labels`

### app/features/confluence_sync/tests/test_knowledge_scope_backfill.py
Level: db (`verify_knowledge_scope_coverage` readiness gate).
- `test_all_active_chunks_scope_tagged_is_ready` — a fully-tagged corpus reports ready — `tg-state`
- `test_untagged_active_chunk_is_not_ready` — an untagged active chunk reports not ready — `tg-state`
- `test_source_scope_tag_alone_does_not_count` — `source_scope`'s own tag (`base`) does not count as a knowledge-scope tag — `tg-state`
- `test_each_recognized_scope_tag_counts` (×4, parametrized over each recognized scope) — every recognized scope tag individually satisfies readiness — `tg-state`
- `test_partial_coverage_lists_only_untagged_pages` — partial coverage lists only the untagged page ids — `tg-state`
- `test_inactive_untagged_chunks_are_ignored` — an inactive untagged chunk does not block readiness — `tg-state`
- `test_empty_corpus_is_vacuously_ready` — an empty corpus reports ready — `tg-state`

### app/features/confluence_sync/tests/test_reader_rls_reconcile.py
Level: db (Phase 13.1, non-`chunk` reader RLS reconcile).
- `test_reader_freed_but_anon_stays_denied` — `apply_reader_rls` lets `rag_reader` read `page_source`; an anon-like role stays denied — `r3-reader`
- `test_apply_reader_rls_leaves_chunk_source_isolation_intact` — the reconcile does not weaken `chunk`'s own source isolation — `r3-reader`
- `test_apply_reader_rls_skips_policy_when_role_absent` — RLS stays enabled with no policy when the reader role does not yet exist — `r3-reader`

### app/features/confluence_sync/tests/test_reader_vector_access.py
Level: db (reader access to the `extensions` schema for pgvector types).
- `test_reader_can_run_dense_halfvec_query` — `rag_reader` can cast `halfvec` — `r3-reader`
- `test_ensure_reader_role_grants_extensions_usage_when_schema_exists` — the reader gets USAGE + search_path on an `extensions` schema when present — `r3-reader`
- `test_ensure_reader_role_no_extensions_schema_is_a_noop_for_extensions` — no `extensions` schema locally → no-op, idempotent re-provision — `r3-reader`

### app/features/confluence_sync/tests/test_reconciliation.py
Level: db.
- `test_complete_reconcile_deactivates_orphan_and_enqueues_new` — a vanished page is deactivated, a new live page enqueued — `d-reconciliation_run`
- `test_lightweight_reconcile_repairs_version_drift` — a missed-event version drift is detected and enqueued, then repaired by the worker — `i1-sweep`
- `test_page_root_scopes_reconciliation_to_its_subtree_and_tags_it` — a page-type scope root syncs only its subtree and tags it — `d-source_scope`
- `test_deactivating_root_purges_previously_synced_now_uncovered_pages` — deactivating a scope root purges pages it uniquely covered — `d-source_scope`

### app/features/confluence_sync/tests/test_retrieval_eval.py
Level: db + eval.
- `test_smoke_maintains_recall_and_beats_ranking` — recall@5 stays 1.0, mrr/ndcg@5 beat the baseline — `e-stage2`
- `test_permission_no_leak_and_authorized_access` — no restricted page leaks to an unauthorized scope; an authorized principal still gets its page — `r3-acl`
- `test_permission_enforcement_is_db_backed_not_fixture_fed` — an empty injected policy object still enforces correctly (DB-backed, not fixture-backed) — `r3-acl`
- `test_rls_default_deny_on_reader_role` — bare RLS with no app filter default-denies the reader — `r3-source`
- `test_retriever_wrong_source_scope_returns_zero` — wrong `allowed_sources` → zero results end-to-end — `r3-source`
- `test_retrieval_writes_one_query_trace_row` — one traced retrieval writes exactly one query_trace row with chunk ids/scores — `d-query_trace`
- `test_retrieve_with_context_surfaces_chunk_ids_scores_and_parent_text` — `retrieve_with_context` exposes chunk ids/scores/parent text; children retrieve, parents ground — `r5-parents`
- `test_retrieve_with_context_empty_on_no_hits` — no candidates → empty `RetrievalResult`, no crash — `r4-proceed`
- `test_update_query_trace_answer_and_feedback` — the answer runtime and feedback both UPDATE the same trace row — `d-query_trace`
- `test_rerank_lift_before_vs_after` — before/after Precision@5/NDCG@10 lift measurement; zero lift under `FakeReranker` on both sides — `r4-rerank`

### app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py
Level: db.
- `test_flag_off_still_enforces_scope_via_rls_backstop` — flag off still excludes a cross-customer page via the RLS backstop — `r3-scope`
- `test_no_knowledge_scopes_argument_is_unrestricted` — no `knowledge_scopes` argument (internal/eval path) is unrestricted — `tg-filter`
- `test_flag_on_excludes_page_tagged_for_a_different_scope` — flag on structurally excludes a page tagged for a scope not in the allow-list — `tg-filter`
- `test_flag_on_includes_page_when_its_scope_is_allowed` — flag on includes a page whose scope is in the allow-list — `tg-filter`
- `test_flag_on_two_scopes_never_cross_leak` — two differently-scoped pages never cross-leak under the flag — `tg-filter`
- `test_flag_on_chunk_with_no_knowledge_scope_tag_never_participates` — an untagged chunk never participates once the flag is on — `tg-filter`
- `test_query_trace_records_allowed_knowledge_scopes` — the trace row records the allowed knowledge scopes used — `d-query_trace`
- `test_gin_index_is_plan_usable_for_tags_overlap` — the `tags &&` GIN index (0007/PLAN 10.3) is plan-usable — no panel (protects the tags GIN index specifically; distinct from the HNSW vector index panels)

### app/features/confluence_sync/tests/test_router_auth_context.py
Level: db (PLAN 11.1c edge-binding proof).
- `test_token_integration_drives_scopes` — a verified token's integration drives the resolved scopes — `r1-ctx`
- `test_body_scope_disagreeing_with_token_is_ignored` — a body scope that disagrees with the token is logged and ignored — `r1-ctx`
- `test_unknown_body_scope_is_400_before_search` — an unrecognized body scope → 400 before any search — `r1-ctx`
- `test_unknown_integration_is_401` — an unmapped token integration → 401 — `r1-ctx`
- `test_tokenless_request_is_general_only` — no token → general-only scope, no subject — `r1-ctx`
- `test_bad_token_is_401_before_search` — an invalid token → 401 before search — `r1-ctx`

### app/features/confluence_sync/tests/test_scheduler.py
Level: unit (apscheduler jobs inspected, not run).
- `test_dev_reconcile_job_absent_by_default` — no dev poll job when the interval is unset — `cm-root`
- `test_dev_reconcile_job_registered_when_interval_set` — an extra interval job registers when the dev interval is set — `cm-root`

### app/features/confluence_sync/tests/test_scope_resolver.py
Level: unit (pure, no DB).
- `test_page_root_resolves_to_self_and_descendants_only` — a page root resolves to itself + descendants — `d-source_scope`
- `test_page_root_never_includes_siblings_or_ancestors` — excludes ancestors/siblings — `d-source_scope`
- `test_space_root_resolves_to_every_live_page` — a space root covers every live page — `d-source_scope`
- `test_page_root_missing_from_live_listing_resolves_to_empty` — a vanished root resolves to empty — `d-source_scope`
- `test_overlapping_page_roots_resolve_independently` — overlapping roots each resolve independently — `d-source_scope`
- `test_no_roots_is_unrestricted_and_untagged` — no roots → unrestricted, untagged — `d-source_scope`
- `test_only_page_roots_restricts_to_their_union` — page roots restrict to their union, with tags — `d-source_scope`
- `test_overlapping_roots_union_tags_on_shared_pages` — overlapping roots union tags on shared pages — `d-source_scope`
- `test_space_root_present_covers_everything_even_with_page_roots_on_top` — a space root covers everything regardless of extra page roots — `d-source_scope`
- `test_page_outside_every_root_resolves_to_nothing` — a page outside every root gets no coverage/tags — `d-source_scope`
- `test_deactivating_the_last_root_purges_rather_than_reverting_to_unrestricted` — deactivating the last root restricts to nothing, not unrestricted — `d-source_scope`
- `test_inactive_roots_do_not_contribute_coverage_or_tags_alongside_active_ones` — inactive roots contribute nothing alongside active ones — `d-source_scope`

### app/features/confluence_sync/tests/test_verify_isolation_script.py
Level: db (`scripts/setup_supabase.verify_isolation`).
- `test_verify_isolation_passes_and_runs_reader_readpath_checks` — every 13.2 reader read-path check runs and passes on a loaded corpus — `cm-scripts`
- `test_verify_isolation_proves_scope_isolation_on_tagged_corpus` — the scope axis is measured and passes on a tagged corpus — `cm-scripts`

### app/features/confluence_sync/tests/test_versioning_rollback.py
Level: db.
- `test_rollback_restores_prior_version` — rollback is an atomic pointer swap to the target version — `i4-rollback`
- `test_rollback_restores_page_source_hashes_and_pipeline_stamps` — rollback repoints PageSource's cached hashes/stamps at the target version — `i4-rollback`
- `test_rollback_then_unchanged_sync_reports_no_change` — re-syncing the rolled-back-to content reports `no_change` — `i4-rollback`
- `test_rollback_then_real_newer_revision_is_detected_not_masked` — a real newer revision after rollback is still detected, not masked — `i4-rollback`

### app/features/confluence_sync/tests/test_webhook.py
Level: db.
- `test_valid_signed_event_is_accepted_and_enqueued` — a validly-signed event is accepted and enqueues a job — `i1-checks`
- `test_missing_signature_is_rejected` — no signature → 401 — `i1-checks`
- `test_bad_signature_is_rejected` — a wrong-secret signature → 401 — `i1-checks`
- `test_duplicate_delivery_is_deduped` — a repeated delivery is deduped — `i1-ledger`
- `test_self_generated_event_enqueues_no_job` — our own service-account write enqueues nothing — `i1-self`
- `test_oversized_body_is_rejected` — a body over the size cap → 413 — `i1-checks`
- `test_unset_secret_fails_closed` — no configured webhook secret → 503 — `i1-checks`
- `test_rate_limit_returns_429` — rate limit trips → 429 — `i1-checks`

### app/features/confluence_sync/tests/test_worker_sync.py
Level: db.
- `test_first_index_creates_active_version_and_chunks` — first index creates one active version with chunks — `i1-handle`
- `test_content_change_swaps_version_atomically` — a content change swaps versions atomically, exactly one active — `i4-swap`
- `test_contextualization_version_bump_rebuilds_at_same_cf_version` — a pipeline-config bump rebuilds at the same cf_version without an IntegrityError — `i4-staging`
- `test_version_guard_drops_stale_update` — a stale (older) version delivery is dropped as `no_change` — `i2-classify`
- `test_first_index_persists_restrictions` — real principal list (users + expanded groups) lands in page_restriction — `d-page_restriction`
- `test_permission_change_is_metadata_only` — a restriction-only change is `metadata_only`, no re-embed, ACL fully replaced — `i2-inplace`
- `test_dropped_restriction_leaves_page_unrestricted` — clearing restrictions removes page_restriction rows entirely — `i2-inplace`
- `test_delete_deactivates_page` — a delete event deactivates the page and its chunks — `i2-gone`

### app/features/evaluation/tests/test_fallback_metrics.py
Level: unit.
- `test_fallback_rate[mixed_outcomes/all_grounded/all_fell_back/empty_is_zero_not_undefined]` (×4) — fallback_rate arithmetic incl. the empty-input edge case — `e-stage4`
- `test_citation_grounding_rate[fully_grounded/partial/no_citations_is_zero/none_grounded]` (×4) — citation_grounding_rate arithmetic — `e-stage4`

### app/features/evaluation/tests/test_fixtures_loader.py
Level: unit (reads the committed fixture corpus, no live DB).
- `test_fixtures_dir_exists` — the fixture corpus directory + manifest exist — `e-gold`
- `test_list_pages_expected_ids` — the manifest lists exactly the expected 6 fixture pages — `e-gold`
- `test_status_coverage` — archived/trashed/current statuses are represented — `e-gold`
- `test_load_page_1001_versions` — page 1001's three versions load with the expected body diffs — `e-gold`
- `test_labels_restrictions_attachments` — labels/restrictions/attachments load per-page, `None` when absent — `e-gold`
- `test_attachment_files_present` — the referenced attachment files exist on disk — `e-gold`

### app/features/evaluation/tests/test_latency_metrics.py
Level: unit.
- `test_percentile_interpolation` — percentile interpolation at 0/50/100 and single-value input — `e-ops`
- `test_percentile_p95_known` — p95 of 1..100 matches a hand-computed value — `e-ops`
- `test_summarize_latencies` — count/min/max/mean/p50 summary — `e-ops`
- `test_summarize_empty` — empty input → zeroed summary, not a crash — `e-ops`
- `test_check_targets_pass_and_fail` — target pass/fail booleans per metric; an absent metric is not checked — `e-ops`
- `test_latency_timer_records_and_appends` — `LatencyTimer` records elapsed time into the samples list — `e-ops`

### app/features/evaluation/tests/test_rerank_lift.py
Level: unit (hand-crafted before/after rankers).
- `test_positive_lift_on_precision_and_ndcg` — a reranker that promotes relevant pages shows positive precision/ndcg lift — `e-stage2`
- `test_zero_lift_when_order_unchanged` — identical before/after order → zero lift (the CI invariant) — `e-stage2`
- `test_empty_dataset_is_safe` — an empty dataset returns zeroed metrics, not a crash — `e-stage2`

### app/features/evaluation/tests/test_retrieval_metrics.py
Level: unit.
- `test_recall_at_k_partial` — recall@k with a partial hit set — `e-stage1`
- `test_recall_at_k_full_and_empty_relevant` — recall@k at 1.0 and with an empty relevant set — `e-stage1`
- `test_precision_at_k_uses_k_denominator` — precision@k denominator behavior incl. k=0 — `e-stage1`
- `test_mrr_first_relevant_rank` — MRR at various first-hit ranks incl. a cutoff exclusion — `e-stage1`
- `test_ndcg_at_k_known_value` — ndcg@k matches a hand-computed value — `e-stage1`
- `test_ndcg_perfect_and_empty` — ndcg@k at 1.0 and with an empty relevant set — `e-stage1`
- `test_hit_rate_at_k` — hit_rate@k incl. a beyond-cutoff miss — `e-stage1`
- `test_duplicates_collapsed` — duplicate ranked ids don't double-count or push others out of the window — `e-stage1`

### app/features/evaluation/tests/test_runner_baseline.py
Level: unit.
- `test_report_structure` — the eval report carries dataset name/timestamp/k/per-case metrics — `cm-eval`
- `test_perfect_ranker_scores_recall_one` — a ranker returning exactly the relevant ids scores 1.0 — `cm-eval`
- `test_empty_ranker_scores_zero` — an empty ranker scores 0.0 — `cm-eval`
- `test_now_iso_is_not_a_clock` — the timestamp is caller-supplied, not wall-clock derived — `cm-eval`

### app/features/ingestion/tests/test_attachment_extraction.py
Level: unit.
- `test_plain_text` — plain text extracts verbatim, no OCR — `i3-attach`
- `test_csv_flattened_to_readable_rows` — CSV flattens to readable rows — `i3-attach`
- `test_html_stripped_to_text` — HTML strips to visible text — `i3-attach`
- `test_markdown_passthrough` — markdown passes through — `i3-attach`
- `test_pdf_with_good_native_text_does_not_need_ocr` — a text-bearing PDF needs no OCR — `i3-attach`
- `test_scanned_pdf_with_empty_native_text_needs_ocr` — an empty-native-text PDF needs OCR — `i3-attach`
- `test_image_always_needs_ocr` — an image attachment always needs OCR — `i3-attach`
- `test_unsupported_binary_is_skipped_not_crashed` — an unsupported binary is skipped, not a crash — `i3-attach`
- `test_missing_optional_lib_degrades_to_skipped` — a missing optional parser lib degrades to skipped — `i3-attach`
- `test_attachment_to_blocks_wraps_text_under_title_keyed_heading_path[...]` (×2) — attachment text wraps under a title-keyed heading path — `i3-attach`
- `test_attachment_to_blocks_empty_text_returns_nothing` — empty extracted text yields no blocks — `i3-attach`
- `test_attachment_to_blocks_distinct_attachments_get_distinct_heading_paths` — distinct attachments get distinct heading paths — `i3-attach`

### app/features/ingestion/tests/test_chunk_diff.py
Level: unit.
- `test_identical_reuses_everything` — identical old/new chunk sets reuse every embedding — `i3-embed`
- `test_edited_in_slot_reembeds_only_that_chunk` — an edited-in-place chunk re-embeds only itself — `i3-embed`
- `test_moved_content_reuses_embedding` — moved-but-unchanged content reuses its embedding at the new position — `i3-embed`
- `test_added_and_removed` — added content re-embeds, removed content is marked deleted — `i3-embed`
- `test_reuse_count_helper` — `reuse_count`/`reembed_count` helpers report correctly — `i3-embed`

### app/features/ingestion/tests/test_chunking.py
Level: unit.
- `test_small_section_yields_one_parent_one_child` — a small section yields one parent/one child under the token max — `i3-parents`
- `test_large_section_splits_into_multiple_children_under_max` — a large section splits into multiple children, all under `child_max` — `i3-children`
- `test_children_cover_parent_content` — every parent word is covered by some child — `i3-children`
- `test_stable_keys_are_deterministic` — stable keys are deterministic across identical re-plans — `i3-children`
- `test_editing_one_section_keeps_other_section_keys_stable` — editing one section leaves an untouched section's keys unchanged — `i3-children`
- `test_empty_blocks_yield_empty_plan` — no blocks → empty plan — `i3-parents`
- `test_heading_path_propagates_to_children` — heading path propagates from parent to children — `i3-children`

### app/features/ingestion/tests/test_contextualizer.py
Level: unit (mocked Anthropic transport).
- `test_fallback_prefixes_heading_path_deterministically` — offline fallback deterministically prefixes the heading path — `i3-context`
- `test_disabled_returns_plain_chunk_text` — contextualization disabled returns plain chunk text — `i3-context`
- `test_llm_path_sends_cached_document_and_prepends_context` — the LLM path sends the doc as a cached system block and prepends real context — `i3-context`
- `test_llm_failure_falls_back_without_raising` — an LLM failure falls back to the deterministic prefix without raising — `i3-context`
- `test_llm_meta_refusal_is_discarded_and_falls_back_to_metadata` (×7 meta-reply phrasings, one function) — a model meta-refusal is discarded, never stored in retrieval_content — `i3-context`
- `test_llm_real_context_first_person_is_not_discarded` — a benign first-person real reply is kept, not false-flagged as a meta-refusal — `i3-context`
- `test_document_text_is_truncated_to_cap` — the cached document text is truncated to the configured char cap — `i3-context`

### app/features/ingestion/tests/test_pipeline_reuse.py
Level: unit (DB-free, spy embedder).
- `test_first_index_embeds_all_children` — first index embeds every child, nothing reused — `i3-embed`
- `test_reindex_identical_reuses_all_embeddings` — an identical reindex reuses every embedding, zero embed calls — `i3-embed`
- `test_edit_one_section_reembeds_only_changed_children` — editing one section re-embeds exactly the changed children — `i3-embed`

### app/features/ingestion/tests/test_tokenization.py
Level: unit.
- `test_empty_and_whitespace_count_zero` — empty/whitespace text counts zero tokens — no panel (protects the token-counting primitive, not itself a design panel)
- `test_count_is_positive_and_monotonic` — token count is positive and grows with text length — no panel
- `test_split_windows_never_exceed_max` — split windows never exceed the max-tokens cap — no panel
- `test_split_short_text_returns_single_window` — short text returns as a single window — no panel
- `test_split_empty_returns_empty_list` — empty text splits to an empty list — no panel
- `test_split_covers_all_words_when_no_overlap` — zero-overlap split covers every word exactly once — no panel
- `test_split_rejects_overlap_ge_max` — overlap ≥ max_tokens raises ValueError — no panel

### app/features/rag_agent/tests/test_answer_cache.py
Level: unit (fake `AnswerProvider`, no network/DB).
- `test_identical_history_and_scope_is_served_from_cache` — identical (history, principal) is a cache hit — `r1-idem`
- `test_different_scope_is_not_served_from_cache` — a different principal is never a cache hit — `r1-idem`
- `test_different_history_is_not_served_from_cache` — a different final question is never a cache hit — `r1-idem`
- `test_earlier_turns_are_part_of_the_cache_key` — different earlier context with the same final turn is not a cache hit — `r1-idem`
- `test_expired_entry_recomputes` — an expired TTL entry recomputes — `r1-idem`
- `test_identical_history_scope_and_knowledge_scope_is_served_from_cache` — identical knowledge-scope allow-list is a cache hit — `r1-idem`
- `test_different_knowledge_scope_is_not_served_from_cache` — a different knowledge-scope allow-list is never a cache hit — `r1-idem`
- `test_omitted_knowledge_scope_is_not_conflated_with_a_named_one` — omitted vs. a named scope never collide — `r1-idem`
- `test_different_token_subject_is_not_served_from_cache` — two verified subjects never share a cache hit — `r1-idem`
- `test_max_entries_bounds_the_cache` — bounded cache evicts the oldest entry — `r1-idem`

### app/features/rag_agent/tests/test_answer_service.py
Level: unit (fake retriever/rewriter/generator/classifier, no network/DB).
- `test_grounded_answer_with_rewrite_and_persisted_trace` — a full grounded run with rewrite persists the trace row — `r5-generate`
- `test_rewrite_disabled_skips_rewriter_and_uses_verbatim_query` — rewrite disabled uses the verbatim query — `r1-rewrite`
- `test_no_candidates_refuses_without_calling_generator` — no candidates refuses without ever calling the generator — `r4-refuse`
- `test_no_candidates_refusal_emits_human_handoff_log` — a no-candidates refusal emits one `human_handoff` log record — `r4-refuse`
- `test_off_topic_refusal_redirects_without_human_handoff` — an off-topic score redirects without a human-handoff log — `r4-refuse`
- `test_weak_score_refusal_still_emits_human_handoff` — a between-thresholds score still hands off to a human — `r4-weak`
- `test_no_citations_refusal_emits_human_handoff_log_with_verbatim_original_query` — the handoff log carries the verbatim original query, not the rewrite — `r4-refuse`
- `test_successful_answer_emits_no_human_handoff_log` — a successful answer never emits a handoff log — `r5-generate`
- `test_weak_result_retries_once_and_succeeds_on_original_query` — a weak rewrite retries once on the original query and succeeds — `r4-weak`
- `test_weak_result_still_weak_after_retry_refuses` — still-weak after one retry refuses — `r4-weak`
- `test_crag_max_retries_zero_never_retries` — `crag_max_retries=0` never retries — `r4-weak`
- `test_no_surviving_citation_degrades_to_refusal` — zero surviving citations degrades to refusal — `r5-nocite`
- `test_rejects_history_not_ending_in_user_turn` — history not ending on a user turn raises ValueError — `cm-agent`
- `test_injected_instruction_in_query_never_changes_the_scope_passed_to_retrieval` — a hostile query text cannot widen the caller-supplied scope — `r1-ctx`
- `test_generator_citing_a_marker_beyond_the_retrieved_hits_is_stripped` — a fabricated out-of-range citation marker is stripped — `r5-enforce`
- `test_generator_that_ignores_citation_instructions_entirely_refuses_rather_than_leaks` — zero valid markers degrades to refusal, never a raw ungrounded answer — `r5-enforce`
- `test_evidence_sent_to_the_generator_never_exceeds_what_retrieval_actually_returned` — the evidence block is built strictly from retrieval's own hits, never the query text — `s-permitted`
- `test_small_talk_short_circuits_before_rewrite_or_retrieval` — small talk never reaches rewrite or retrieval — `r1-small`
- `test_small_talk_writes_no_query_trace_row` — small talk writes no trace row — `r1-small`
- `test_real_question_that_merely_starts_with_a_greeting_still_runs_the_full_pipeline` — a real question glued to a greeting still runs the full pipeline — `r1-small`
- `test_identity_question_short_circuits_before_rewrite_or_retrieval` — an identity question never reaches rewrite/retrieval — no panel (per-user identity path; not yet a named design panel)
- `test_identity_question_writes_no_query_trace_row` — identity answers write no trace row — no panel
- `test_identity_question_on_tokenless_path_still_answers_with_empty_facts` — tokenless identity path answers with empty facts, not a refusal — no panel
- `test_identity_question_checked_after_small_talk` — small-talk's "who are you" takes the small-talk path, not identity — `r1-small`
- `test_real_question_sharing_words_with_identity_still_runs_full_pipeline` — a real question sharing identity-like words still runs the full pipeline — no panel
- `test_rejects_empty_history` — empty history raises ValueError — `cm-agent`
- `test_no_image_never_calls_generate_image_analysis` — no image never calls image analysis — `r5-image`
- `test_image_on_turn_with_no_retrieved_candidates_does_not_refuse` — an image-only turn with no text candidates does not refuse — `r5-image`
- `test_image_analysis_survives_a_citation_enforcement_refusal` — image analysis rides along even when the text answer refuses — `r5-image`
- `test_image_only_turn_with_empty_content_skips_retrieval` — an empty-text image-only turn skips retrieval entirely — `r5-image`
- `test_clarification_branch_disabled_by_default_never_calls_the_classifier` — the classifier is never constructed when the branch is disabled — `r1-clarify`
- `test_clarification_branch_with_non_ambiguous_verdict_runs_the_full_pipeline_unchanged` — a non-ambiguous verdict changes nothing — `r1-clarify`
- `test_clarification_branch_enabled_with_ambiguous_verdict_bypasses_the_pipeline` — an ambiguous verdict bypasses the full pipeline — `r1-clarify`
- `test_clarification_branch_ambiguous_verdict_writes_no_query_trace_row` — a clarifying turn writes no trace row — `r1-clarify`
- `test_clarification_branch_enabled_with_no_classifier_configured_is_a_no_op` — flag on with no classifier degrades safely — `r1-clarify`
- `test_small_talk_short_circuits_before_the_clarification_classifier_too` — small talk wins over the clarification branch — `r1-small`
- `test_image_analysis_is_never_passed_through_citation_enforcement` — image analysis never gains a citation marker — `r5-image`
- `test_auth_allowed_scopes_reach_the_retriever_verbatim` — the verified AuthContext's scopes reach the retriever unchanged — `r1-ctx`
- `test_subject_hash_persisted_is_the_hash_not_the_raw_subject` — the trace stores sha256(subject), never the raw subject — `r1-ctx`
- `test_omitted_knowledge_scope_with_no_default_is_general_alone` — no scope + no default → general-only — `r1-ctx`
- `test_crag_retry_reuses_the_same_resolved_allowed_scopes` — the CRAG retry reuses the exact same resolved scope list — `r1-ctx`
- `test_no_reader_sessionmaker_configured_composes_zero_curated_entries` — no reader sessionmaker → zero curated entries composed, no crash — `r2-curated`
- `test_curated_entries_are_prepended_as_markers_1_through_k` — curated entries get markers 1..k, retrieved hits k+1..n — `r2-curated`
- `test_curated_entry_citation_survives_enforce_citations_exactly_like_a_retrieved_one` — a curated-only citation survives enforcement like any retrieved one — `r2-curated`
- `test_curated_entries_fetched_with_the_same_resolved_allowed_scopes` — curated fetch uses the exact same resolved scope list — `r2-curated`
- `test_curated_entries_still_compose_on_the_text_empty_image_only_path` — curated entries still compose on the image-only path — `r2-curated`

### app/features/rag_agent/tests/test_auth_context.py
Level: unit.
- `test_builds_scoped_context` — a full claims set builds the expected scoped AuthContext — `r1-ctx`
- `test_company_id_only_difference_yields_identical_scopes` — company_id alone never changes resolved scopes (done-when 3a) — `r1-ctx`
- `test_no_business_values_is_general_only` — no business claims → general-only — `r1-ctx`
- `test_unknown_integration_raises` — an unmapped integration raises `UnknownIntegrationError` — `r1-ctx`
- `test_general_only_context_helper` — the `general_only_context()` helper matches the tokenless shape — `r1-ctx`

### app/features/rag_agent/tests/test_citations.py
Level: unit.
- `test_keeps_cited_sentence_and_reports_used_markers` — a validly-cited sentence is kept, marker reported as used — `r5-enforce`
- `test_strips_uncited_claim` — an uncited claim is stripped — `r5-enforce`
- `test_strips_claim_that_only_cites_a_hallucinated_source` — a claim citing only a hallucinated marker is fully stripped — `r5-enforce`
- `test_drops_invalid_marker_but_keeps_a_validly_cited_sentence` — an invalid marker is dropped, the valid one kept — `r5-enforce`
- `test_used_markers_are_sorted_and_deduped` — used markers are sorted and deduped — `r5-enforce`
- `test_empty_answer_returns_empty` — empty input returns empty — `r5-enforce`

### app/features/rag_agent/tests/test_clarification.py
Level: unit.
- `test_long_query_is_never_ambiguous_and_skips_the_classifier` — a long query is never ambiguous, classifier untouched — `r1-clarify`
- `test_empty_query_is_never_ambiguous_and_skips_the_classifier` — an empty query is never ambiguous, classifier untouched — `r1-clarify`
- `test_short_query_falls_through_to_the_classifier_and_returns_its_verdict` — a short query falls through to the classifier's verdict — `r1-clarify`
- `test_short_but_specific_query_can_still_be_judged_not_ambiguous` — a short specific query can still be judged not ambiguous — `r1-clarify`
- `test_history_is_accepted_but_not_required_to_be_non_empty` — history is accepted without affecting the outcome — `r1-clarify`
- `test_parse_clarification_reply[...]` (×7 parametrized cases in one function) — parses/rejects the fixed `Question:`/`Options:` reply shape — `r1-clarify`

### app/features/rag_agent/tests/test_curated_knowledge.py
Level: unit (pure adapter + spy-session SQL shape, no DB).
- `test_curated_entry_to_hit_uses_a_namespaced_page_id_and_negative_chunk_id` — a curated entry maps to a `curated:{id}` page id and negative chunk id — `r2-curated`
- `test_curated_entry_to_hit_ids_never_collide_between_distinct_entries` — distinct entries never collide on hit id — `r2-curated`
- `test_fetch_curated_entries_sets_the_scope_rls_guc_before_reading` — the scope RLS GUC is set before the SELECT — `r2-curated`
- `test_fetch_curated_entries_binds_scopes_as_a_parameter_never_interpolated` — scopes are bound, never interpolated — `r2-curated`
- `test_fetch_curated_entries_binds_a_malicious_scope_value_never_reaches_raw_sql` — a SQL-injection-shaped scope value never reaches raw SQL text — `r2-curated`
- `test_fetch_curated_entries_includes_the_empty_tags_always_included_clause` — the empty-tags-always-included clause is present — `r2-curated`

### app/features/rag_agent/tests/test_identity.py
Level: unit.
- `test_recognizes_identity_questions_case_and_whitespace_insensitively[...]` (×18 cases in one function) — recognizes integration/company/"who am I" phrasings — no panel (per-user identity classifier; not yet a named design panel)
- `test_does_not_match_capability_or_real_questions[...]` (×9 cases in one function) — never matches small-talk look-alikes or real questions, incl. an injection-glued probe — no panel
- `test_identity_facts_reports_business_identity_when_integration_present` — `has_business_identity` true when integration set — no panel
- `test_identity_facts_reports_no_business_identity_when_integration_absent` — false when integration absent — no panel

### app/features/rag_agent/tests/test_llm_client.py
Level: unit (mocked Anthropic transport).
- `test_rewrite_redacts_pii_before_sending` — PII is redacted from the rewrite prompt before sending — `r1-rewrite`
- `test_rewrite_single_turn_skips_the_call_entirely` — a single-turn history skips the LLM call, returns verbatim — `r1-rewrite`
- `test_rewrite_fails_open_to_verbatim_last_turn_on_error` — a transport error fails open to the verbatim last turn — `r1-rewrite`
- `test_generate_redacts_pii_and_sends_cached_system_block` — the answer generator redacts PII and caches its system block — `r5-generate`
- `test_generate_sends_natural_writing_style_guidance_alongside_citation_rules` — writing-style guidance ships alongside the citation-marker rule — `r5-generate`
- `test_generate_small_talk_sends_the_small_talk_system_prompt_and_redacts_pii` — small-talk generation redacts PII, uses the small-talk prompt — `r1-small`
- `test_generate_small_talk_fails_open_to_a_static_greeting_on_error` — a transport error fails open to a static greeting — `r1-small`
- `test_generate_identity_sends_cached_static_block_plus_uncached_per_user_block` — identity generation sends a cached static block + uncached per-user block — no panel (per-user identity)
- `test_generate_identity_redacts_pii_in_the_query` — identity generation redacts PII — no panel
- `test_generate_identity_fails_open_to_a_static_reply_on_error` — a transport error fails open to a static identity reply — no panel
- `test_generate_image_analysis_redacts_query_and_sends_image_blocks` — image analysis redacts the query and sends image blocks — `r5-image`
- `test_generate_image_analysis_never_reaches_enforce_citations_shape` — image analysis never sends an evidence/citation-instruction prompt — `r5-image`
- `test_generate_image_analysis_fails_open_to_a_short_notice_on_error` — a transport error fails open to a short notice — `r5-image`
- `test_classify_redacts_pii_and_sends_the_ambiguity_system_prompt` — the ambiguity classifier redacts PII — `r1-clarify`
- `test_classify_returns_true_for_an_ambiguous_verdict` — an AMBIGUOUS reply classifies true — `r1-clarify`
- `test_classify_returns_false_for_a_specific_verdict` — a SPECIFIC reply classifies false — `r1-clarify`
- `test_classify_fails_open_to_not_ambiguous_on_error` — a transport error fails open to not-ambiguous — `r1-clarify`
- `test_generate_clarification_redacts_pii_and_sends_the_clarification_system_prompt` — clarification generation redacts PII — `r1-clarify`
- `test_generate_clarification_never_sends_an_evidence_block_or_citation_instruction` — clarification never sends an evidence block — `r1-clarify`
- `test_generate_clarification_fails_open_to_a_static_fallback_on_error` — a transport error fails open to a static fallback — `r1-clarify`
- `test_generate_clarification_fails_open_to_a_static_fallback_on_an_unparseable_reply` — an unparseable reply falls back to the static default — `r1-clarify`
- `test_classify_requires_a_leading_ambiguous_token_not_a_buried_one` — only a leading AMBIGUOUS token flips the verdict, not a buried one — `r1-clarify`
- `test_generate_clarification_parser_discards_any_text_outside_the_fixed_shape` — the parser discards any leaked text outside the fixed Question/Options shape — `r1-clarify`

### app/features/rag_agent/tests/test_pii.py
Level: unit.
- `test_redacts_pii_by_type[email/ssn/card/phone]` (×4) — redacts each PII type with its marker — `r5-generate`
- `test_leaves_plain_text_untouched` — plain text is untouched — `r5-generate`
- `test_redacts_multiple_occurrences` — multiple emails in one string are each redacted — `r5-generate`
- `test_obfuscated_email_evades_redaction_documented_known_gap` — an obfuscated email ("[at]"/"[dot]") is NOT caught — documented known gap — `r5-generate`

### app/features/rag_agent/tests/test_prompt.py
Level: unit.
- `test_build_rewrite_prompt_includes_every_turn_in_order` — every history turn appears, in order — `r1-rewrite`
- `test_build_evidence_block_numbers_markers_from_one_in_hit_order` — evidence markers number from 1 in hit order — `r5-evidence`
- `test_build_evidence_block_missing_parent_text_degrades_to_empty_body` — missing parent text degrades to an empty body, not a crash — `r5-evidence`
- `test_build_evidence_block_empty_hits_is_empty_string` — no hits → empty evidence block — `r5-evidence`
- `test_build_answer_prompt_includes_question_and_evidence` — the answer prompt includes both question and evidence — `r5-generate`
- `test_identity_system_prompt_carries_no_citation_and_anti_injection_rules` — the identity prompt forbids citation markers and treats facts as non-instructions — no panel (per-user identity)
- `test_build_identity_system_prompt_appends_operator_static_block` — the operator's static identity block appends to the base prompt — no panel
- `test_build_identity_system_prompt_with_no_static_block_is_just_the_base_prompt` — no static block → just the base prompt — no panel
- `test_build_identity_context_block_renders_business_identity` — renders integration/company/id when present — no panel
- `test_build_identity_context_block_without_identity_says_so_honestly` — states "no verified" identity honestly when absent — no panel

### app/features/rag_agent/tests/test_refusal.py
Level: unit.
- `test_shipped_thresholds_map_supported_answer_offtopic_redirect_weak_handoff` — the shipped thresholds correctly split supported/off-topic/weak-score on real measured scores — `r4-refuse`
- `test_offtopic_when_candidate_at_or_below_offtopic_threshold` — `<=` offtopic threshold → off_topic — `r4-refuse`
- `test_weak_score_when_between_offtopic_and_refusal_threshold` — between thresholds → weak_score — `r4-weak`
- `test_no_candidates_is_a_handoff_not_an_offtopic_redirect` — `None` top score stays no_candidates, not off_topic — `r4-refuse`
- `test_allows_when_top_score_at_or_above_threshold` — at/above threshold → no refusal — `r4-refuse`
- `test_allowed_decision_has_no_reason` — an allowed decision carries no reason — `r4-refuse`
- `test_has_image_never_refuses_on_no_candidates` — an image-bearing turn never refuses on no_candidates — `r5-image`
- `test_has_image_never_refuses_on_offtopic_or_weak_score` — an image-bearing turn never refuses on off_topic/weak_score — `r5-image`
- `test_has_image_true_does_not_change_a_strong_score_outcome` — has_image doesn't change a strong-score outcome — `r5-image`

### app/features/rag_agent/tests/test_small_talk.py
Level: unit.
- `test_recognizes_small_talk_phrases_case_and_whitespace_insensitively[...]` (×27 cases in one function) — recognizes greeting/capability/starter-chip phrasings — `r1-small` / `r1-short`
- `test_does_not_match_real_questions_even_when_they_start_with_a_greeting[...]` (×10 cases in one function) — never matches real questions, incl. one starting with a greeting — `r1-small` / `r1-short`

### app/features/rag_agent/tests/test_token_claims_contract.py
Level: unit (drift guard against `packages/contracts`).
- `test_required_claims_match_the_verifier` — the published JSON Schema's `required` set matches the verifier — `cm-contracts`
- `test_audience_constant_matches_the_verifier` — the schema's `aud` const matches the verifier — `cm-contracts`
- `test_business_claims_are_all_three_or_none` — the schema's dependentRequired mirrors the all-three-or-none rule — `cm-contracts`

### app/features/rag_agent/tests/test_token_verifier.py
Level: unit (throwaway RS256 keypair, stubbed JWKS client).
- `test_valid_token` — a valid token verifies with the right claims — `r1-auth`
- `test_unknown_issuer_rejected` — an unmapped issuer is rejected — `r1-auth`
- `test_hs256_rejected` — an HS256-downgraded token is rejected before any key work — `r1-auth`
- `test_wrong_audience_rejected` — a wrong `aud` is rejected — `r1-auth`
- `test_expired_rejected` — an expired token is rejected — `r1-auth`
- `test_lifetime_over_platform_max_rejected` — a lifetime over the platform's max is rejected — `r1-auth`
- `test_missing_iat_rejected` — a missing `iat` is rejected — `r1-auth`
- `test_partial_business_claims_rejected` — a partial business-claims set is rejected — `r1-auth`
- `test_no_business_claims_is_valid` — no business claims at all is valid — `r1-auth`

### app/features/retrieval/tests/test_fusion_and_permission.py
Level: unit.
- `test_rrf_rewards_top_ranks_and_agreement` — RRF rewards items ranked high in both lists — `r2-rrf`
- `test_rrf_weights_apply` — RRF weights bias the fused score — `r2-rrf`
- `test_classify_scope_splits_digit_strings_from_principal_ids` — `classify_scope` splits numeric space ids from principal ids — `r3-acl`
- `test_space_scope_grants_space_and_blocks_others` — space-level trust grants its space, blocks others — `r3-acl`
- `test_principal_scope_blocks_unauthorized` — principal ACL blocks an unauthorized principal — `r3-acl`
- `test_numeric_principal_argument_is_never_reinterpreted_as_space_trust` — an all-digit `principal=` argument is never promoted to space trust — `r3-acl`

### app/features/retrieval/tests/test_knowledge_scope.py
Level: unit.
- `test_no_request_or_default_returns_general_only` — no request/default → general-only — `r1-ctx`
- `test_recognized_requested_scope_is_added_to_general` — a recognized requested scope adds to general — `r1-ctx`
- `test_requested_scope_matching_is_case_insensitive` — scope matching is case-insensitive — `r1-ctx`
- `test_unrecognized_requested_scope_degrades_to_default` — an unrecognized request degrades to the deployment default — `r1-ctx`
- `test_unrecognized_requested_scope_with_no_default_degrades_to_general_only` — no default either → general-only — `r1-ctx`
- `test_no_requested_scope_falls_back_to_default` — no request falls back to the default — `r1-ctx`
- `test_unrecognized_default_is_ignored` — an unrecognized default is ignored — `r1-ctx`
- `test_result_is_sorted` — the result list is sorted — `r1-ctx`

### app/features/retrieval/tests/test_search_repo_gucs.py
Level: unit (spy session, no DB).
- `test_emits_both_gucs_with_valid_values` — both HNSW GUCs emit with valid values — `r2-gucs`
- `test_ef_search_is_coerced_to_int` — `ef_search` coerces to int — `r2-gucs`
- `test_unknown_scan_mode_falls_back_to_relaxed_order` — an unknown scan mode falls back to `relaxed_order` — `r2-gucs`
- `test_injection_attempt_never_reaches_sql` — an injection-shaped `iterative_scan` value never reaches SQL — `r2-gucs`

### app/features/retrieval/tests/test_search_repo_knowledge_scope.py
Level: unit (spy session, no DB).
- `test_keyword_search_omits_predicate_when_knowledge_scopes_is_none` — flag-off keyword search emits no `tags &&` predicate — `tg-filter`
- `test_keyword_search_adds_predicate_when_knowledge_scopes_given` — flag-on adds the bound predicate — `tg-filter`
- `test_dense_search_omits_predicate_when_knowledge_scopes_is_none` — flag-off dense search emits no predicate — `tg-filter`
- `test_dense_search_adds_predicate_when_knowledge_scopes_given` — flag-on dense search adds the bound predicate — `tg-filter`
- `test_fetch_rerank_texts_adds_predicate_when_knowledge_scopes_given` — flag-on rerank-text fetch adds the predicate — `tg-filter`
- `test_fetch_rerank_texts_omits_predicate_when_knowledge_scopes_is_none` — flag-off omits it — `tg-filter`
- `test_malicious_knowledge_scope_value_never_reaches_sql_text` — an injection-shaped scope value never reaches SQL text — `tg-filter`

### app/platform/clients/tests/test_anthropic_client.py
Level: unit (mocked httpx transport).
- `test_create_message_happy_path` — a normal call returns the text content — `cm-platform`
- `test_missing_key_raises_without_tripping_breaker` — a missing key raises without tripping the breaker — `cm-platform`
- `test_input_abuse_cap_rejects_oversized_prompt` — an oversized prompt is rejected by the abuse cap — `cm-platform`
- `test_circuit_breaker_opens_after_consecutive_failures` — the breaker opens after consecutive failures, then fails fast — `cm-platform`
- `test_create_message_content_shape[...]` (×3 cases in one function) — image+text / image-only / text-only content shapes are built correctly — `cm-platform`
- `test_success_resets_the_breaker` — a success resets the consecutive-failure counter — `cm-platform`

### app/platform/clients/tests/test_confluence_client.py
Level: unit (mocked httpx transport; pure resolver tests are DB-free).
- `test_group_only_restriction_resolves_to_fail_closed_sentinel` — a group-only restriction resolves to the fail-closed sentinel — `r3-groups`
- `test_user_and_group_restriction_without_resolver_keeps_only_resolved_users` — no resolver keeps only the resolved user — `r3-groups`
- `test_user_only_restriction_is_unaffected` — a user-only restriction is unaffected — `r3-groups`
- `test_no_restriction_entries_resolves_to_unrestricted` — no restriction entries → unrestricted — `r3-groups`
- `test_group_restriction_expands_via_resolver` — a resolver expands group membership into principals — `r3-groups`
- `test_group_and_user_restriction_expands_and_unions_via_resolver` — user + group union, deduped — `r3-groups`
- `test_group_restriction_resolver_finding_no_members_still_fails_closed` — a resolver finding no members still fails closed — `r3-groups`
- `test_http_client_group_only_restriction_fails_closed` — the live REST v1 shape's group-only case fails closed — `r3-groups`
- `test_http_client_user_restriction_unaffected` — the live shape's user-only case is unaffected — `r3-groups`
- `test_http_client_no_restrictions_returns_empty` — no restrictions in the live shape returns empty — `r3-groups`
- `test_http_client_restriction_fetch_failure_fails_closed` — a restriction-fetch request failure fails closed, not open — `r3-groups`
- `test_http_client_restrictions_use_v1_content_endpoint` — restrictions use the working v1 content endpoint, not the broken v2 one — `ov-confluence`
- `test_http_client_group_restriction_expands_via_group_member_lookup` — the group-member v1 lookup expands a group restriction — `r3-groups`
- `test_http_client_group_member_lookup_is_cached_across_pages` — group-member lookups are cached across pages — `r3-groups`
- `test_http_client_group_member_lookup_failure_stays_fail_closed` — a member-lookup failure (403) stays fail closed — `r3-groups`
- `test_http_client_list_space_pages_paginates_without_doubling_wiki_prefix` — pagination joins `_links.next` without doubling the `/wiki` prefix — `ov-confluence`
- `test_http_client_group_member_lookup_paginates_without_doubling_wiki_prefix` — group-member pagination has the same fix — `ov-confluence`
- `test_http_client_retries_on_5xx_then_succeeds` — a 5xx is retried, then succeeds — `ov-confluence`
- `test_http_client_4xx_is_not_retried` — a 4xx is never retried — `ov-confluence`
- `test_http_client_breaker_trips_after_consecutive_failures` — the breaker trips after consecutive whole-request failures — `ov-confluence`
- `test_http_client_success_resets_the_breaker` — a success resets the consecutive-failure counter — `ov-confluence`
- `test_http_client_logs_retry_and_status_lines` — retry/5xx events are logged — `ov-confluence`
- `test_fixture_gateway_group_only_restriction_fails_closed` — the fixture gateway mirrors the group-only fail-closed case — `r3-groups`
- `test_fixture_gateway_no_restriction_fixture_is_unrestricted` — no fixture restriction → unrestricted — `r3-groups`
- `test_fixture_gateway_group_restriction_expands_via_group_members_fixture` — the fixture gateway expands via its group-members fixture — `r3-groups`
- `test_fixture_gateway_set_group_members_override` — the test-only member override works — `r3-groups`
- `test_get_attachments_includes_download_link` — attachment listing includes the download link — `i3-attach`
- `test_download_attachment_returns_bytes_on_success` — a successful download returns bytes — `i3-attach`
- `test_download_attachment_follows_cross_host_redirect_without_forwarding_auth` — a cross-host redirect is followed without forwarding the auth header — `i3-attach`
- `test_download_attachment_aborts_past_cap_even_if_content_length_lied` — the byte cap binds even when Content-Length lies — `i3-attach`
- `test_download_attachment_returns_none_on_4xx` — a 4xx download returns None — `i3-attach`
- `test_download_attachment_retries_5xx_then_succeeds` — a 5xx download is retried then succeeds — `i3-attach`
- `test_download_attachment_empty_link_returns_none` — an empty link returns None — `i3-attach`
- `test_fixture_gateway_download_attachment_resolves_real_fixture_file` — the fixture gateway resolves a real fixture attachment file — `i3-attach`
- `test_fixture_gateway_download_attachment_unknown_link_returns_none` — an unknown fixture link returns None — `i3-attach`
- `test_fixture_gateway_download_attachment_oversized_returns_none` — an oversized fixture download returns None — `i3-attach`
- `test_fixture_gateway_set_attachment_content_overrides_bytes` — the test-only content override works — `i3-attach`
- `test_fixture_gateway_set_attachment_content_none_simulates_failure` — the test-only None override simulates a failed download — `i3-attach`
- `test_fixture_gateway_set_restrictions_override_bypasses_resolution` — the test-only restrictions override bypasses resolution — `r3-groups`

### app/platform/clients/tests/test_embeddings_client.py
Level: unit (mocked httpx transport).
- `test_fake_provider_is_deterministic_and_right_dim` — the fake provider is deterministic, L2-normalized, right dim — `vd-model`
- `test_fake_provider_empty_input` — empty input → empty output — `vd-model`
- `test_openai_provider_batches_and_sends_dimensions` — batching splits requests, sends the right model/dimensions — `i3-embed`
- `test_openai_breaker_opens_after_threshold` — the breaker opens after consecutive failed batches — `i3-embed`
- `test_abuse_cap_rejects_oversized_call` — an oversized call is rejected by the abuse cap — `i3-embed`
- `test_factory_falls_back_to_fake_offline_without_key` — no key + local env falls back to the fake provider — `vd-model`
- `test_factory_raises_in_production_without_key` — no key + production env raises — `vd-model`

### app/platform/clients/tests/test_reranker_client.py
Level: unit (mocked httpx transport).
- `test_fake_is_deterministic_order_preserving_and_truncates` — the fake reranker is deterministic, order-preserving, truncates by top_k — `r4-rerank`
- `test_fake_empty_input` — empty input → empty output — `r4-rerank`
- `test_fake_satisfies_the_reranker_protocol` — the fake satisfies the `Reranker` protocol — `r4-rerank`
- `test_cohere_sends_v2_shape_and_maps_indices_back_to_page_ids` — Cohere v2 shape sent, result indices map back to page ids — `r4-rerank`
- `test_cohere_breaker_opens_after_threshold` — the breaker opens after consecutive failures — `r4-rerank`
- `test_cohere_abuse_cap_rejects_oversized_call` — an oversized doc set is rejected by the abuse cap — `r4-rerank`
- `test_factory_returns_fake_for_empty_or_fake_provider` — an empty/"fake" provider setting returns the fake — `r4-rerank`
- `test_factory_falls_back_to_fake_offline_without_key` — no key + local env falls back to fake — `r4-rerank`
- `test_factory_raises_in_production_without_key` — no key + production raises — `r4-rerank`
- `test_factory_builds_cohere_with_key` — a real key + production builds the Cohere client — `r4-rerank`

### app/platform/config/tests/test_knowledge_scopes.py
Level: unit.
- `test_parses_lowercases_and_trims` — scope names parse lowercased and trimmed — `ks-edit`
- `test_missing_general_raises` — a config missing `obi-general-test` raises — `ks-edit`
- `test_empty_scopes_raises` — an empty scope list raises — `ks-edit`
- `test_blank_names_are_ignored` — blank scope names are ignored — `ks-edit`
- `test_committed_repo_config_file_is_well_formed` — the real committed `config/knowledge_scopes.json` parses to the expected 4 scopes — `ks-edit`

### app/platform/config/tests/test_platforms.py
Level: unit.
- `test_maps_platform_key_to_live_slugs` — a platform key maps to its live domain/scope slugs — `em-backend`
- `test_unknown_slug_in_integrations_stops_startup` — an unrecognized scope slug in `integrations` stops startup — `em-backend`
- `test_empty_platforms_stops_startup_when_not_allowed` — empty platforms stops startup unless explicitly allowed — `em-backend`
- `test_empty_platforms_allowed_locally` — empty platforms is allowed when `allow_empty=True` — `em-backend`
- `test_general_always_appended_even_if_omitted` — `obi-general-test` is always appended even if omitted — `em-backend`
- `test_classified_scope_is_never_mappable` — the `classified` scope can never be mapped to a platform — `em-backend`
- `test_hs256_alg_is_forbidden` — an `HS256` algorithm entry is forbidden at load time — `r1-auth`

### app/platform/config/tests/test_settings.py
Level: unit.
- `test_knowledge_scope_set_reads_the_committed_config_file` — `Settings().knowledge_scope_set` reads the committed config — `cm-config`
- `test_construction_fails_fast_when_config_file_is_invalid` — an invalid config file fails `Settings()` construction fast — `cm-config`
- `test_default_knowledge_scope_defaults_to_empty` — `default_knowledge_scope` field defaults to `""` — `cm-config`
- `test_enable_knowledge_scope_filtering_defaults_to_false` — the filtering flag defaults to `False` — `cm-config`
- `test_obi_identity_path_defaults_to_empty` — `obi_identity_path` defaults to `""` — no panel (operator-editable identity static block; not yet a named design panel)
- `test_obi_identity_text_reads_the_file_when_present` — the identity text file is read when present — no panel
- `test_obi_identity_text_is_empty_when_file_missing_does_not_raise` — a missing identity file degrades to `""`, no raise — no panel

### app/platform/db/tests/test_engine_reader_role.py
Level: db-adjacent unit (no live connection; `create_engine` doesn't connect eagerly).
- `test_offline_env_with_unset_reader_url_falls_back_to_writer_engine[local/test/dev/ci]` (×4) — offline envs fall back to the writer engine when the reader URL is unset — `r3-reader`
- `test_non_offline_env_with_unset_reader_url_fails_closed[production/staging/prod]` (×3) — non-offline envs fail closed (raise) when the reader URL is unset — `r3-reader`
- `test_reader_url_set_never_fails_regardless_of_env[local/test/production]` (×3) — a set reader URL never fails regardless of env — `r3-reader`

### app/platform/db/tests/test_migration_0007_knowledge_scope.py — FAILS TODAY (see §4)
Level: db (real Alembic chain against a dedicated migration-test database).
- `test_0007_upgrade_creates_the_new_shape` — upgrade creates `curated_knowledge_entry`, `query_trace.allowed_knowledge_scopes`, the tags GIN index — `cm-alembic`
- `test_0007_downgrade_then_upgrade_round_trips_cleanly` — downgrade removes the new shape byte-for-byte, re-upgrade restores it — `cm-alembic`

### app/platform/db/tests/test_migration_0009_reader_rls_reconcile.py — FAILS TODAY (see §4)
Level: db.
- `test_0009_adds_reader_policy_and_keeps_rls_on` — 0009 adds the reader-scoped SELECT policy on non-chunk tables, `chunk`'s own RLS untouched — `cm-alembic`
- `test_0009_downgrade_then_upgrade_round_trips` — downgrade removes the policy and disables non-chunk RLS, re-upgrade restores it — `cm-alembic`

### app/platform/db/tests/test_migration_0010_scope_rls.py — FAILS TODAY (see §4)
Level: db.
- `test_0010_adds_restrictive_scope_policies` — 0010 adds RESTRICTIVE scope policies on `chunk`/`curated_knowledge_entry`, source policy untouched — `cm-alembic`
- `test_0010_downgrade_then_upgrade_round_trips` — downgrade removes only the scope layer, re-upgrade restores it — `cm-alembic`

### app/platform/db/tests/test_migration_0011_subject_hash.py — FAILS TODAY (see §4)
Level: db.
- `test_0011_adds_subject_hash_and_round_trips` — 0011 adds `query_trace.subject_hash` and round-trips upgrade→downgrade→upgrade — `cm-alembic`

### app/platform/db/tests/test_models_constraints.py
Level: unit (pure SQLAlchemy metadata inspection, no DB).
- `test_chunk_has_exactly_one_canonically_named_source_type_check` — `chunk`'s explicit CHECK name survives the naming convention unmangled — `cm-alembic`
- `test_page_source_has_exactly_one_canonically_named_source_type_check` — same for `page_source` — `cm-alembic`
- `test_source_scope_has_canonically_named_checks` — same for `source_scope`'s two checks — `cm-alembic`

### app/shared/tests/test_rate_limiter.py
Level: unit.
- `test_allows_up_to_max_requests_within_the_window` — allows up to max requests, denies the next within the window — `cm-shared`
- `test_request_is_allowed_again_once_the_window_elapses` — allowed again once the window elapses — `cm-shared`
- `test_distinct_keys_are_independent` — distinct keys are independent — `cm-shared`
- `test_expired_bucket_is_pruned_from_the_dict_on_next_access` — an expired bucket is pruned on next access, not left growing — `cm-shared`
- `test_bucket_count_stays_bounded_across_many_distinct_keys` — many one-shot keys stay bounded by `max_tracked_keys` — `cm-shared`
- `test_max_tracked_keys_evicts_the_oldest_key_first` — the oldest key is evicted first once the cap is hit — `cm-shared`
- `test_unbounded_when_max_tracked_keys_is_none` — no cap → unbounded growth — `cm-shared`

### app/shared/tests/test_ttl_cache.py
Level: unit.
- `test_hit_returns_the_stored_value` — a hit returns the stored value — `cm-shared`
- `test_miss_on_unknown_key_returns_none` — a miss returns None — `cm-shared`
- `test_entry_expires_after_ttl` — an entry expires after its TTL — `cm-shared`
- `test_entry_survives_up_to_the_ttl_boundary` — an entry survives up to (not past) the TTL boundary — `cm-shared`
- `test_expired_entry_is_evicted_on_read` — an expired entry is evicted on read — `cm-shared`
- `test_max_entries_evicts_the_oldest_insertion` — the oldest insertion is evicted once `max_entries` is exceeded — `cm-shared`
- `test_unbounded_when_max_entries_is_none` — no cap → unbounded growth — `cm-shared`

### tests/tools/test_agent_guard.py
Level: unit (subprocess, hermetic; this audit's own subagent tooling).
- `test_guard_rejects_unknown_profile` — an unknown profile is blocked — no panel (protects this audit's own PreToolUse guard, not a design panel)
- `test_auditor_read_only_shell_allowed` — read-only shell commands are allowed under the auditor profile — no panel
- `test_auditor_allows_read_only_pytest` — `pytest --collect-only`/plain `pytest -q` are allowed under the auditor profile — no panel
- `test_auditor_blocks_mutating_shell` — mutating shell commands are blocked under the auditor profile — no panel
- `test_auditor_write_scoped_to_final_docs` — Write is scoped to `docs/Final_docs/`, Edit is always blocked, under the auditor profile — no panel
- `test_auditor_write_check_is_cwd_independent` — the write-scope check is cwd-independent given `CLAUDE_PROJECT_DIR` — no panel
- `test_auditor_blocks_redirect_even_to_allowed_dir` — a shell redirect/tee into the allowed dir is still blocked — no panel
- `test_auditor_checks_every_chained_part` — every part of a chained shell command is checked — no panel
- `test_tester_allows_test_runners_blocks_writes` — the tester profile allows test/diff commands, blocks writes — no panel
- `test_implementer_gated_on_marker` — the implementer profile gates Write/Edit on an active-substep marker file — no panel
- `test_none_profile_is_passthrough` — the `none` profile is a pass-through — no panel

### tests/tools/test_panel.py
Level: unit (subprocess against a synthetic HTML fixture, hermetic).
- `test_panel_print_returns_only_that_panel` — printing one id renders only that panel — no panel (protects this audit's own `panel.py` CLI, not a design panel)
- `test_panel_list_one_line_per_panel` — `--list` prints exactly one line per panel — no panel
- `test_panel_grep_prints_matching_ids_only` — `--grep` prints only matching ids — no panel
- `test_panel_update_changes_two_fields_and_leaves_the_rest_identical` — `--status`/`--today` change exactly those two fields, byte-identical elsewhere — no panel
- `test_panel_status_only_leaves_today_untouched` — `--status` alone leaves `today` untouched — no panel
- `test_panel_unknown_id_fails` — an unknown id fails loudly for both print and update — no panel
- `test_panel_rejects_unknown_status_word` — an unrecognized status word is rejected — no panel

---

## 2. Web test files

### apps/web/src/app/test-hosts/multi-user-content.test.tsx
Level: browser. Internal multi-user QA harness page (PLAN §0 NEXT STEP), not a described design panel.
- `offers exactly the three business users and never the tokenless 'none' host` — no panel
- `always shows the currently active user's company and integration` — no panel
- `switching to a random user changes the active user to a different one` — no panel
- `an explicit per-user button switches the active user to that user` — no panel

### apps/web/src/app/test-hosts/test-host-content.test.tsx
Level: browser. Same internal QA harness family.
- `TestHostsLayout > marks <html> with suppressHydrationWarning to match the sibling root layouts` — no panel
- `tokenUrlFor > builds the per-name token endpoint for %s` (×4, parametrized) — no panel
- `TestHostContent > renders the heading and paste template with the correct tokenUrl for %s` (×4, parametrized) — no panel

### apps/web/src/features/embed/tests/frame-csp.test.ts
Level: browser.
- `computeEmbedCsp > includes every active domain and never emits a wildcard` — the frame-ancestors header lists every active domain, no `*` — `em-button`
- `computeEmbedCsp > renders frame-ancestors 'none' when tolerated locally with no active domains` — `em-button`
- `computeEmbedCsp > fails closed (ok: false) when no active domains exist outside local/dev` — `em-button`
- `activeDomains > returns the sorted, de-duplicated domains of active entries only` — `em-button`
- `activeDomains > returns an empty list for a missing/malformed file` — `em-button`
- `middleware > sets frame-ancestors with the active domains and no wildcard on a normal request` — `em-button`
- `middleware > responds 403 when there are no active domains outside local/dev` — `em-button`
- `middleware > fails toward 403 (never allow-all) when the internal active-domains fetch itself fails` — `em-button`
- `GET /api/internal/active-domains > returns the active domains computed from the current platforms file` — `em-button`

### apps/web/src/features/embed/tests/iframe-bridge.test.ts
Level: browser.
- `sets the token from obi:token when the origin is allowed and the source is the parent` — `w-token`
- `ignores obi:token from a disallowed origin, warns once, and leaves the token null` — `w-token`
- `ignores a message whose source is not window.parent, even from an allowed origin` — `w-token`
- `drops the token on obi:clear` — `w-token`
- `invokes onToken/onClear callbacks` — `w-token`
- `invokes onOpen on obi:open without setting a token` — `w-token`
- `does not invoke onOpen for an obi:open from a disallowed origin` — `w-token`
- `resets to null token on re-init` — `w-token`
- `getToken > never reads any web storage API` — `w-token`

### apps/web/src/features/embed/tests/loader.test.ts
Level: browser.
- `Obi.init injects exactly one iframe pointed at the embed origin's /embed route` — `em-loader`
- `injects the two-tone sparkle 'star' launcher (not a plain text button), matching ChatLauncher` — `em-loader`
- `toggles: a second launcher click hides the iframe without clearing the token or re-fetching` — `em-loader`
- `posts obi:token to the exact OBI_ORIGIN (never '*') after a launcher click fetches the token` — `em-loader`
- `Obi.clear() posts obi:clear to the exact OBI_ORIGIN` — `em-loader`
- `schedules a silent renewal before the token's exp` — `em-loader`
- `retries the token-endpoint fetch once on a 401 from the platform's own server` — `em-loader`
- `Obi.destroy() removes the launcher and iframe so no widget is left in the DOM` — `em-loader`
- `re-init points at a new tokenUrl without leaking a second launcher/iframe (user switch)` — `em-loader`

### apps/web/src/features/chat/tests/assistant-mark.test.tsx
Level: browser. Decorative brand mark, not a named design panel.
- `renders as a decorative SVG hidden from assistive tech` — no panel
- `sizes the SVG from the size prop` — no panel

### apps/web/src/features/chat/tests/panel-header.test.tsx
Level: browser.
- `shows the assistant name, defaulting to Obi` — `w-panel`
- `omits the close button when no onClose is given (page variant)` — `w-panel`
- `shows and wires the close button when onClose is given (widget variant)` — `w-panel`
- `opening one menu closes the other (mutually exclusive)` — `w-panel`
- `renders docs/support as disabled stubs and wires restart to the real handler` — `w-panel`
- `closes the open menu on outside click` — `w-panel`
- `knowledge-scope switcher > is hidden unless NEXT_PUBLIC_SHOW_SCOPE_SWITCHER is set` — `w-scope`
- `knowledge-scope switcher > shows the switcher and applies a picked scope back into the session` — `w-scope`
- `knowledge-scope switcher > opening the scope menu closes the other menus` — `w-scope`

### apps/web/src/features/chat/tests/chat-widget.test.tsx
Level: browser.
- `renders only the closed launcher initially, no panel` — `w-launcher`
- `opens the panel when the launcher is clicked` — `w-launcher`
- `closing the panel (via the header's Close icon) returns to the launcher` — `w-launcher`
- `teaser timing > shows the teaser 3000ms after mount if still closed, and it opens the panel` — `w-launcher`
- `teaser timing > dismissing the teaser hides it without opening the panel` — `w-launcher`

### apps/web/src/features/chat/tests/route-handlers.test.ts
Level: browser (Next.js route handlers under vitest, no live server).
- `handlePostChat > rejects malformed JSON before calling the backend` — `w-proxy`
- `handlePostChat > rejects a request missing history before calling the backend` — `w-proxy`
- `handlePostChat > fails closed with 503 when the automation API is unconfigured` — `w-proxy`
- `handlePostChat > translates the request, forwards the idempotency header, and streams the backend body through` — `w-proxy`
- `handlePostChat > forwards knowledgeScope unmodified as knowledge_scope` — `w-scope`
- `handlePostChat > forwards the backend's error status and body verbatim` — `w-proxy`
- `handlePostChat > returns 502 when the upstream call itself fails` — `w-proxy`
- `handlePostChat > does not 413 a legitimate image-bearing turn within the backend's own image caps` — `w-proxy`
- `handlePostChat > still rejects a pathologically oversized body with 413 before calling the backend` — `w-proxy`
- `handlePostChat > threads a Bearer Authorization header through to callAutomationApi as userToken` — `w-token`
- `handlePostChat > passes no userToken when the request carries no Authorization header` — `w-token`
- `handlePatchFeedback > rejects an invalid feedback value before calling the backend` — `r5-feedback`
- `handlePatchFeedback > fails closed with 503 when the automation API is unconfigured` — `r5-feedback`
- `handlePatchFeedback > forwards to the backend with an encoded traceId and a shortened timeout` — `r5-feedback`

### apps/web/src/features/chat/tests/chat-session-provider.test.tsx
Level: browser.
- `surfaces the backend's error message on a rejected (401) request` — `w-render`
- `clears messages and pending state` — `w-render`
- `aborts an in-flight stream instead of letting it resurrect the cleared thread` — `w-render`
- `sends the configured knowledgeScope on the outgoing request` — `w-scope`
- `applies a runtime scope change (the PLAN 10.8 switcher) to the next outgoing request` — `w-scope`
- `omits knowledgeScope from the outgoing request when not configured` — `w-scope`
- `attaches images to the newest history turn only, and reads imageAnalysis back off done` — `r5-image`
- `marks a turn as clarifying (not refused) and keeps its options, per ADR-0008 decision 3` — `r1-clarify`
- `resends a clarifying turn's question as history on the next message` — `r1-clarify`

### apps/web/src/features/chat/tests/menu.test.tsx
Level: browser. Generic menu primitive underlying PanelHeader's dropdowns, no design panel of its own.
- `renders nothing when closed` — no panel
- `renders its children under the given accessible name when open` — no panel
- `closes when the outside overlay is clicked` — no panel

### apps/web/src/features/chat/tests/teaser-popup.test.tsx
Level: browser.
- `opens the panel when the card itself is clicked` — `w-launcher`
- `dismissing never also opens the panel` — `w-launcher`

### apps/web/src/features/chat/tests/icon-button.test.tsx
Level: browser. Generic UI primitive, no design panel of its own.
- `renders its children and fires onClick` — no panel
- `reflects the active prop as aria-pressed` — no panel
- `does not fire onClick while disabled` — no panel

### apps/web/src/features/chat/tests/typing-indicator.test.tsx
Level: browser.
- `renders an initial word from the thinking-word bank with an ellipsis` — `w-render`
- `cycles to a different word every 3800ms` — `w-render`
- `stops cycling once unmounted (no interval leak)` — `w-render`

### apps/web/src/features/chat/tests/chat-client.test.ts
Level: browser.
- `streamChat > attaches the Authorization bearer header when a token is present` — `w-token`
- `streamChat > omits the Authorization header when no token is present` — `w-token`
- `streamChat > dispatches start/token/citations/done in order from a single chunk` — `w-render`
- `streamChat > reassembles an event whose \n\n separator is split across chunks` — `w-render`
- `streamChat > reports a mid-stream error event through onError without throwing` — `w-render`
- `streamChat > throws ChatRequestError when the response is not ok` — `w-proxy`
- `streamChat > throws ChatRequestError when fetch itself rejects` — `w-proxy`
- `streamChat > notifies onUnauthorized listeners exactly once on a 401, and not on other error statuses` — `w-proxy`
- `streamChat > stops notifying an unsubscribed onUnauthorized listener` — `w-proxy`
- `sendFeedback > resolves with the backend body on success` — `r5-feedback`
- `sendFeedback > attaches the Authorization bearer header when a token is present` — `w-token`
- `sendFeedback > omits the Authorization header when no token is present` — `w-token`
- `sendFeedback > throws ChatRequestError on a non-ok response` — `r5-feedback`

### apps/web/src/features/chat/tests/message-list.test.tsx
Level: browser.
- `shows the resolved greeting with the product name bold, and no suggestion chip` — `w-render`
- `renders all three empty-state example-query chips and sends the clicked one` — `w-render`
- `renders each message via MessageBubble` — `w-render`
- `forwards feedback clicks to onFeedback with the message id and trace id` — `r5-feedback`

### apps/web/src/features/chat/tests/knowledge-scopes.test.ts
Level: browser (drift guard, reads the canonical config file directly).
- `mirrors config/knowledge_scopes.json's scope names in order (no drift)` — `w-scope`
- `always includes obi-general-test — the always-present base scope (ADR-0011)` — `w-scope`

### apps/web/src/features/chat/tests/menu-item.test.tsx
Level: browser. Generic UI primitive, no design panel of its own.
- `fires onSelect when clicked` — no panel
- `is aria-disabled and never fires onSelect when disabled, while staying focusable` — no panel
- `applies danger styling` — no panel
- `applies bold weight when active` — no panel

### apps/web/src/features/chat/tests/scope-menu.test.tsx
Level: browser.
- `renders all four recognized scopes with the active one checked` — `w-scope`
- `calls onSelect with the picked scope name and closes` — `w-scope`
- `checks nothing when no scope is active (embed default)` — `w-scope`

### apps/web/src/features/chat/tests/attachment-strip.test.tsx
Level: browser. Composer image-attachment UI (not the auto page-screenshot tool).
- `renders nothing when there are no attachments` — `w-composer`
- `renders a thumbnail per attachment and calls onRemove with its id` — `w-composer`
- `opens a full-size lightbox on thumbnail click and closes it on Escape` — `w-composer`
- `closes the lightbox via its close button without removing the attachment` — `w-composer`

### apps/web/src/features/chat/tests/language-menu.test.tsx
Level: browser.
- `renders all six locales with English checked` — `w-i18n`
- `calls onSelect with the picked locale and closes, without touching the active one` — `w-i18n`

### apps/web/src/features/chat/tests/use-widget-visibility.test.tsx
Level: browser.
- `starts closed with no teaser` — `w-launcher`
- `shows the teaser 3000ms after mount if still closed` — `w-launcher`
- `never shows the initial teaser if the widget is opened first` — `w-launcher`
- `openWidget opens the panel and hides any visible teaser` — `w-launcher`
- `closeWidget reschedules the teaser after 20000ms` — `w-launcher`
- `dismissTeaser hides it and reschedules after 20000ms, without opening the panel` — `w-launcher`

### apps/web/src/features/chat/tests/validation.test.ts
Level: browser.
- `parseChatRequestBody > accepts a well-formed request and passes fields through unchanged` — `r1-limits`
- `parseChatRequestBody > accepts a minimal request with only history` — `r1-limits`
- `parseChatRequestBody > rejects a non-object body: %s` (×4, parametrized) — `r1-limits`
- `parseChatRequestBody > rejects a missing history field` — `r1-limits`
- `parseChatRequestBody > rejects an empty history array` — `r1-limits`
- `parseChatRequestBody > rejects history longer than the resource-exhaustion ceiling` — `r1-limits`
- `parseChatRequestBody > rejects a turn with an invalid role` — `r1-limits`
- `parseChatRequestBody > accepts a turn with empty content and no images` — `r5-image`
- `parseChatRequestBody > accepts an image-only turn with empty content (ADR-0009 decision 4)` — `r5-image`
- `parseChatRequestBody > accepts a resent history where an older image-only turn has aged out to empty content and no images` — `r5-image`
- `parseChatRequestBody > rejects history that does not end on a user turn` — `r1-limits`
- `parseChatRequestBody > rejects a non-string conversationId` — `r1-limits`
- `parseChatRequestBody > rejects a non-string principal` — `r1-limits`
- `parseFeedbackBody > accepts feedback value %d` (×2, parametrized) — `r5-feedback`
- `parseFeedbackBody > rejects invalid feedback value: %s` (×6, parametrized) — `r5-feedback`
- `parseFeedbackBody > rejects a non-object body` — `r5-feedback`

### apps/web/src/features/chat/tests/panel-body.test.tsx
Level: browser (characterization test replacing the removed `chat-panel.test.tsx`).
- `streams an answer and renders the final text` — `w-render`
- `renders citation links returned with the done event` — `w-render`
- `shows a refusal indicator when the pipeline refuses` — `r4-refuse`
- `surfaces a request error without crashing` — `w-render`
- `sends feedback for the correct trace id and value` — `r5-feedback`
- `restart (via the header's More menu) genuinely clears the thread` — `w-panel`
- `aborts the in-flight stream when unmounted` — `w-render`

### apps/web/src/features/chat/tests/composer.test.tsx
Level: browser.
- `sends the trimmed message and clears the box on Enter` — `w-composer`
- `inserts a newline on Shift+Enter instead of sending` — `w-composer`
- `does not send whitespace-only input` — `w-composer`
- `sends via the Send button and disables it while empty` — `w-composer`
- `renders the footer disclaimer` — `w-composer`
- `disables the box, Send, and Attach buttons while a request is pending` — `w-composer`
- `image attachments > previews an image selected via the file picker and enables Send with no text` — `w-composer`
- `image attachments > previews a pasted image` — `w-composer`
- `image attachments > removes an attachment via its remove button` — `w-composer`
- `image attachments > caps attachments at 4 and ignores extras` — `w-composer`
- `image attachments > shows the PII disclosure while an image is staged, and clears it once removed` — `w-composer`
- `image attachments > sends a base64-encoded image attachment with empty text when there is no text` — `w-composer`
- `image attachments > sends both the text and the image attachment when both are present` — `w-composer`

---

## 3. Implemented panels with no test

35 `built` panels have no test in §1/§2 naming them. Each line below is the panel's own named check
(from its "Steps"/"Settings"/"Tests" section on the design page), or a five-word summary when the
panel names no explicit check.

- **ov-corpus** — The Postgres corpus: row security on every table; writer exempt by ownership. No test asserts the corpus box as a whole (its individual pieces are tested under `s-*`/`vd-*`/`cm-alembic`).
- **ov-widget** — The Obi widget: embedded with a scope, calls its own proxy, proxy adds the key and streams back. Overview box; its parts are tested individually under `w-*`.
- **cm-agent** — features/rag_agent: owns POST /chat, the answer workflow, refusal, citations, prompts, the answer cache. Folder-boundary claim, not a pytest-checked behavior.
- **cm-docs** — docs/adr: the decisions of record. Not code; not pytest-testable.
- **cm-infra** — infra/foundation: local Postgres via docker-compose, pinned pgvector image. Not pytest-testable.
- **cm-ingest** — features/ingestion: owns chunking, contextualization, embedding reuse, attachment extraction, versioning. Folder-boundary claim.
- **cm-platform** — platform/: shared plumbing; imports no feature. Folder-boundary claim (enforced by `make boundaries`, not pytest).
- **cm-retrieval** — features/retrieval: owns search, fusion, the page ACL, rerank wiring. Folder-boundary claim.
- **cm-sync** — features/confluence_sync: owns receive, decide, sweeps, the label-to-tag rule. Folder-boundary claim.
- **cm-tokens** — packages/design-tokens: colors and fonts for the widget. Not pytest-testable.
- **cm-web** — apps/web: the widget's code. Folder-boundary claim; individual pieces tested under `w-*`.
- **d-document** — document table: one row per page, `page_id` unique deferrable FK. No test asserts this constraint directly.
- **i2-fetch** — Fetch the page facts: meta/labels/restrictions/attachments always fetched; body only when the version or attachment list moved; restriction groups expanded via the v1 member endpoint. No dedicated test.
- **i2-tobuild** — On to ingestion stage 3: body blocks + attachment blocks passed to the chunker. Hand-off step; no dedicated test.
- **i4-chunks** — Insert the chunks inactive: parents flushed first, then children; `is_active=false` until swap. No dedicated test.
- **i4-document** — Ensure the document row: one row per page, stable id across every rebuild. No dedicated test.
- **i4-failed** — A failed version never activates: stays as a record of what went wrong. No test simulates a failed build.
- **i4-gate** — Validation gate: zero small pieces marks the build failed and keeps the old page live. No test exercises the zero-chunk failure path.
- **i4-gc** — Garbage collect old versions: keeps the last two, deletes older. No test creates a fourth version to prove deletion of the oldest.
- **ks-index** — Pages go in: the queued job runs stages 2-4, tags become the recognized labels, the page is searchable in that scope. No dedicated end-to-end test (covered piecewise by `i2-labels`/`tg-retag`).
- **r2-embed** — Embed the question: same model as pages; an image-only turn builds an empty result. No dedicated test (exercised only incidentally inside e2e retrieval tests).
- **r2-indexes** — The two search indexes: HNSW over halfvec + GIN over tsv, both `WHERE is_active AND kind = 1`. No test asserts either index definition directly.
- **r3-torerank** — Only permitted candidates move on: up to `rerank_depth` (75), same transaction, same scope. No test asserts the 75-depth or same-transaction constraint specifically.
- **s-audit** — The audit trail: per-query/per-refusal/per-sync log fields, secrets never logged. No test asserts the audit-log field set as its own contract (individual fields are incidentally covered by `d-query_trace`/refusal tests).
- **sc-backend** — One backend: never trusts a body scope, never serves a hidden row, never renders UI. Architecture claim, not pytest-checked as a unit.
- **sc-frontend** — One frontend: never decides access, never holds a signing key, never opens a DB connection. Architecture claim, not pytest-checked as a unit.
- **tg-add** — Add a label: `active_doc_version_id` unchanged after a label-only add; the page appears in the new scope's results on the next question. No test asserts either named check directly (the closest test, `test_label_driven_knowledge_scope_tag_unions_with_source_scope`, checks the tag union but not version-id stability or a live query against the new scope).
- **tg-change** — Change a label: no stale double tag after e.g. mews→toast. No test exercises a sequential label swap (only the two-labels-at-once conflict case is tested).
- **vd-column** — chunk.embedding: `vector(3072)`, nullable, child chunks only, same row as text/tags/tsv. No dedicated test asserts the column definition.
- **vd-hnsw** — The HNSW index: `ix_chunk_embedding_hnsw`, m=16, ef_construction=200, `WHERE is_active AND embedding IS NOT NULL`. No test asserts the index definition (GUC tuning is tested; the index itself is not).
- **vd-nearest** — The nearest 75: `ORDER BY embedding <=> :query_vector LIMIT 75`, row security filters first. No test asserts the 75-row limit or the filter-before-order sequencing.
- **vd-question** — The question vector: rewritten question through the same model, one 3072-number vector, compared by cosine distance. No dedicated test (same gap as `r2-embed`).
- **w-screenshot** — Screenshot of the page behind the widget, attached to the question. No test exists for this feature; `attachment-strip.test.tsx` tests manual image upload (mapped to `w-composer`), not the auto-screenshot capture tool.
- **tests/tools/*** are excluded from this count — they protect this audit's own subagent tooling (`agent_guard.py`, `panel.py`), not a design panel.

---

## 4. Tests that fail today

Executed: `uv run pytest -q` (all levels attempted; local Postgres on :5434 was reported up before
this run) and, to isolate root causes fast, `uv run pytest --lf -q --tb=line` (reruns only the 52
last-failed tests). Both runs agree: **52 failed, 560 passed, 2 warnings, 4 errors** (the 4 errors
are the same 4 migration tests failing again during fixture teardown, not 4 additional distinct
tests). Web (vitest) was not executed — no `pnpm test`/`vitest` command was run, per the read-only
constraint and because it was not in the allowed-commands list; nothing is claimed about web
pass/fail.

**Failures cluster into exactly two root causes, both environment/config, not application-logic
bugs:**

**Cluster A — Alembic + ConfigParser `%`-interpolation crash (5 tests, all `platform/db/tests/test_migration_*`).**
`migration_engine`'s fixture builds a per-test database URL from `get_settings().database_url` and
hands it to `alembic.config.Config.set_main_option("sqlalchemy.url", ...)`. That call routes through
Python's `configparser.BasicInterpolation`, which treats `%` as an interpolation escape. The
configured database password contains a literal `%21` (URL-encoded `!`), so `set_main_option` raises
before any migration runs:
```
ValueError: invalid interpolation syntax in 'postgresql+psycopg://postgres.vtpbwkbbkfukfmytlqns:OMNIBOOST123%21@aws-1-eu-west-1.pooler.supabase.com:5432/postgres_test_migration_test?sslmode=require' at position 63
```
- `test_migration_0007_knowledge_scope.py::test_0007_upgrade_creates_the_new_shape` — same ValueError before any DDL runs
- `test_migration_0007_knowledge_scope.py::test_0007_downgrade_then_upgrade_round_trips_cleanly` — same
- `test_migration_0009_reader_rls_reconcile.py::test_0009_adds_reader_policy_and_keeps_rls_on` — same (also errors again in fixture teardown)
- `test_migration_0009_reader_rls_reconcile.py::test_0009_downgrade_then_upgrade_round_trips` — same (also errors in teardown)
- `test_migration_0010_scope_rls.py::test_0010_adds_restrictive_scope_policies` — same (also errors in teardown)
- `test_migration_0010_scope_rls.py::test_0010_downgrade_then_upgrade_round_trips` — same (also errors in teardown)
- `test_migration_0011_subject_hash.py::test_0011_adds_subject_hash_and_round_trips` — same

**Cluster B — every other DB-touching test connects to a live Supabase pooler host, not local
Postgres, and that connection fails (47 tests).** The captured tracebacks show repeated attempts
against `aws-1-eu-west-1.pooler.supabase.com:5432` failing with:
```
psycopg.OperationalError: connection failed: ... FATAL:  (ENOIDENTIFIER) no tenant identifier provided (external_id or sni_hostname required)
```
This means the effective `DATABASE_URL`/`DATABASE_READER_URL` this run resolved to a remote Supabase
pooler DSN that requires SNI/tenant routing the plain `psycopg` connection here doesn't supply — not
the local `:5434` instance the substep's setup step reported as up. This is the same root cause named
in the task brief ("RLS/reader-role/migration/eval" clustering) — every failing non-migration test is
a `db`- or `eval`-level test that opens a real reader/writer connection:
- `app/features/confluence_sync/tests/test_answer_workflow.py` — all 3 tests (real-retrieval AnswerService)
- `app/features/confluence_sync/tests/test_chat_endpoint.py` — 8 of its tests (the ones indexing the corpus or hitting query_trace)
- `app/features/confluence_sync/tests/test_customer_isolation_backstop.py` — all 5 tests
- `app/features/confluence_sync/tests/test_fallback_eval.py` — 2 of its 3 tests
- `app/features/confluence_sync/tests/test_force_rls_managed_postgres.py` — both tests
- `app/features/confluence_sync/tests/test_reader_rls_reconcile.py` — 2 of its 3 tests
- `app/features/confluence_sync/tests/test_reader_vector_access.py` — 1 of its 3 tests
- `app/features/confluence_sync/tests/test_retrieval_eval.py` — all 10 tests
- `app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py` — 7 of its 8 tests
- `app/features/confluence_sync/tests/test_verify_isolation_script.py` — both tests

Full list of the 52 failing test ids (from `uv run pytest -q`, unchanged on rerun):
```
app/features/confluence_sync/tests/test_answer_workflow.py::test_answer_service_grounds_a_cited_answer_end_to_end
app/features/confluence_sync/tests/test_answer_workflow.py::test_answer_service_refuses_when_source_scope_excludes_everything
app/features/confluence_sync/tests/test_answer_workflow.py::test_answer_service_refuses_when_generator_cites_nothing
app/features/confluence_sync/tests/test_chat_endpoint.py::test_image_within_caps_is_accepted_and_analysis_reaches_the_done_event
app/features/confluence_sync/tests/test_chat_endpoint.py::test_idempotency_key_replay_with_different_field_is_not_the_first_callers_answer[history]
app/features/confluence_sync/tests/test_chat_endpoint.py::test_idempotency_cache_evicts_the_oldest_key_once_max_entries_exceeded
app/features/confluence_sync/tests/test_chat_endpoint.py::test_grounded_answer_streams_start_token_citations_done
app/features/confluence_sync/tests/test_chat_endpoint.py::test_refusal_streams_done_with_refused_true
app/features/confluence_sync/tests/test_chat_endpoint.py::test_chat_request_log_includes_refusal_reason_when_refused
app/features/confluence_sync/tests/test_chat_endpoint.py::test_chat_request_log_has_no_refusal_reason_when_not_refused
app/features/confluence_sync/tests/test_chat_endpoint.py::test_idempotency_key_replays_cached_answer_without_rerunning
app/features/confluence_sync/tests/test_chat_endpoint.py::test_answer_cache_replays_without_rerunning_retrieval
app/features/confluence_sync/tests/test_chat_endpoint.py::test_answer_cache_does_not_cross_token_subject_boundary
app/features/confluence_sync/tests/test_chat_endpoint.py::test_feedback_updates_trace_row
app/features/confluence_sync/tests/test_customer_isolation_backstop.py::test_scope_rls_blocks_cross_customer_read_via_guc_alone
app/features/confluence_sync/tests/test_customer_isolation_backstop.py::test_scope_rls_fails_closed_when_scope_guc_unset
app/features/confluence_sync/tests/test_customer_isolation_backstop.py::test_scope_rls_wildcard_is_an_explicit_opt_out
app/features/confluence_sync/tests/test_customer_isolation_backstop.py::test_scope_rls_untagged_chunk_is_global_visible_under_any_scope
app/features/confluence_sync/tests/test_customer_isolation_backstop.py::test_curated_scope_rls_isolates_tagged_entries_but_keeps_global
app/features/confluence_sync/tests/test_fallback_eval.py::test_out_of_corpus_case_refuses_not_clarifies_or_hallucinates
app/features/confluence_sync/tests/test_fallback_eval.py::test_citation_grounding_rate_on_a_real_grounded_answer
app/features/confluence_sync/tests/test_force_rls_managed_postgres.py::test_non_superuser_owner_reads_own_rows
app/features/confluence_sync/tests/test_force_rls_managed_postgres.py::test_non_owner_reader_still_isolated
app/features/confluence_sync/tests/test_reader_rls_reconcile.py::test_reader_freed_but_anon_stays_denied
app/features/confluence_sync/tests/test_reader_rls_reconcile.py::test_apply_reader_rls_leaves_chunk_source_isolation_intact
app/features/confluence_sync/tests/test_reader_vector_access.py::test_reader_can_run_dense_halfvec_query
app/features/confluence_sync/tests/test_retrieval_eval.py::test_smoke_maintains_recall_and_beats_ranking
app/features/confluence_sync/tests/test_retrieval_eval.py::test_permission_no_leak_and_authorized_access
app/features/confluence_sync/tests/test_retrieval_eval.py::test_permission_enforcement_is_db_backed_not_fixture_fed
app/features/confluence_sync/tests/test_retrieval_eval.py::test_rls_default_deny_on_reader_role
app/features/confluence_sync/tests/test_retrieval_eval.py::test_retriever_wrong_source_scope_returns_zero
app/features/confluence_sync/tests/test_retrieval_eval.py::test_retrieval_writes_one_query_trace_row
app/features/confluence_sync/tests/test_retrieval_eval.py::test_retrieve_with_context_surfaces_chunk_ids_scores_and_parent_text
app/features/confluence_sync/tests/test_retrieval_eval.py::test_retrieve_with_context_empty_on_no_hits
app/features/confluence_sync/tests/test_retrieval_eval.py::test_update_query_trace_answer_and_feedback
app/features/confluence_sync/tests/test_retrieval_eval.py::test_rerank_lift_before_vs_after
app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py::test_flag_off_still_enforces_scope_via_rls_backstop
app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py::test_no_knowledge_scopes_argument_is_unrestricted
app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py::test_flag_on_excludes_page_tagged_for_a_different_scope
app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py::test_flag_on_includes_page_when_its_scope_is_allowed
app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py::test_flag_on_two_scopes_never_cross_leak
app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py::test_flag_on_chunk_with_no_knowledge_scope_tag_never_participates
app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py::test_query_trace_records_allowed_knowledge_scopes
app/features/confluence_sync/tests/test_verify_isolation_script.py::test_verify_isolation_passes_and_runs_reader_readpath_checks
app/features/confluence_sync/tests/test_verify_isolation_script.py::test_verify_isolation_proves_scope_isolation_on_tagged_corpus
app/platform/db/tests/test_migration_0007_knowledge_scope.py::test_0007_upgrade_creates_the_new_shape
app/platform/db/tests/test_migration_0007_knowledge_scope.py::test_0007_downgrade_then_upgrade_round_trips_cleanly
app/platform/db/tests/test_migration_0009_reader_rls_reconcile.py::test_0009_adds_reader_policy_and_keeps_rls_on
app/platform/db/tests/test_migration_0009_reader_rls_reconcile.py::test_0009_downgrade_then_upgrade_round_trips
app/platform/db/tests/test_migration_0010_scope_rls.py::test_0010_adds_restrictive_scope_policies
app/platform/db/tests/test_migration_0010_scope_rls.py::test_0010_downgrade_then_upgrade_round_trips
app/platform/db/tests/test_migration_0011_subject_hash.py::test_0011_adds_subject_hash_and_round_trips
```

**What ran vs. what could not be confirmed:**
- Ran and passed: 560 tests, spanning `unit` and every `db`-level test whose fixtures don't build a
  fresh migration URL and whose reader/writer connections happened to resolve locally (the large
  majority of `confluence_sync`, `ingestion`, `rag_agent`, `retrieval`, `platform` suites).
  `test_engine_reader_role.py` (offline env fallback logic, no real connection attempted) also passed.
- Ran and failed: the 52 above, for the two config/env reasons documented, not for a code defect
  found by this audit.
- Could not run: `make eval` (the gold-set runner, a separate command from `pytest`) was not
  executed — out of scope for `uv run pytest -q`. Web (`vitest`) was not executed at all — no
  pass/fail is claimed for any of the 27 web files in §2.
