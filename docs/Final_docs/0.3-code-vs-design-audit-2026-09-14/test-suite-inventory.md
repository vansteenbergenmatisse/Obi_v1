# Synopsis of today's test suite (substep 0.3.2)

Read-only audit. Counts below are verified against actual command output (see "How these counts were produced").

| count | value |
|---|---|
| Backend test files (`uv run pytest --collect-only -q`, from `apps/automation`) | **71** |
| Backend test functions collected (same command; parametrize cases counted individually) | **614** |
| Implemented panels (`python3 tools/panel.py --list` — status word **`built`**, the codebase's word for "Implemented"; see mapping note below) | **101** |
| Implemented panels with no test today | **23** |

Frontend (`apps/web`, vitest, jsdom-based component tests) is reported separately below: **27 files, 181 `it`/`test`/`it.each` declarations** (statically grep-counted; `pnpm`/vitest could not be executed under the auditor's read-only shell allow-list, so this count is unverified by execution — see "Frontend tooling gap").

## How these counts were produced

- `cd apps/automation && uv run pytest --collect-only -q` → `614 tests collected` across 71 files under `testpaths = ["app", "tests"]` (`apps/automation/pyproject.toml:58`).
- `python3 apps/automation/tools/panel.py --list` → 192 total panels. `panel.py --help` (`apps/automation/tools/panel.py`) shows the only status words are `built | change | build | unverified | discuss` — there is no literal status called "Implemented". Cross-referencing CLAUDE.md's "Words with one meaning" (*"Implemented: deployed and tested on the live store"*) against the status semantics, **`built` is the status word that means Implemented**; `change` = "Implemented, needs changing"; `build` = "Planned"; `unverified` = "Unverified"; `discuss` = "Decision needed". `python3 apps/automation/tools/panel.py --list | grep built` → 101 panels. This mapping is inferred, not stated literally on the design page — flagged as **ambiguous, ADR-worthy** rather than guessed silently.
- Panel ids cited per test below come from `python3 apps/automation/tools/panel.py --grep <term>` plus reading the panel's "Tests" section, then confirmed against the code the test imports.

## Level key

- **unit** — fakes only, no network, no DB (per CLAUDE.md's test-level table).
- **db** — real local Postgres, schema built directly (`schema.create_all` / real Alembic migrations), truncated/dropped per test.
- Neither **live** nor **eval** (pytest-marker sense) appears as a distinct pytest marker; there are no pytest marks at all in `apps/automation/pyproject.toml` — level is inferred per file from its fixtures (see each file's line below).

## Environment finding that explains most of "Tests that fail today"

`apps/automation/conftest.py:1-24` (root conftest) only pins embedding/reranker envs; it does **not** override `DATABASE_URL`. `app/features/confluence_sync/tests/conftest.py:58-98` builds its dedicated `*_test` database by taking `get_settings().database_url` (i.e. whatever the root `.env` says) and appending `_test`/`_migration_test` to the database name — it never points at `localhost:5434` (the `make up` local Postgres, see `Makefile`). The root `.env` (gitignored, read via `python-dotenv`/pydantic-settings, `apps/automation/app/platform/config`) currently sets `DATABASE_URL` to a **remote Supabase pooler host** (`aws-1-eu-west-1.pooler.supabase.com`) rather than a local instance. Confirmed live during this run: `psycopg.OperationalError: ... FATAL: (ENOIDENTIFIER) no tenant identifier provided` — the pooler rejects the connection because the username isn't in Supabase's per-tenant `postgres.<ref>` form. This is a **test-environment misconfiguration**, not an application bug: CLAUDE.md's own rule ("Secrets come from the root `.env`... Tests never read it") is itself violated here, since `get_settings()` does load `.env` inside the test process. See "Tests that fail today" for the exact list this produces.

---

# Backend (`apps/automation`, pytest)

## `app/shared/tests/` — level: unit

### `app/shared/tests/test_ttl_cache.py`
Purpose (docstring, line 1): TTLCache expiry/eviction, backing both the idempotency replay cache and the exact-match answer cache. No dedicated panel — `cm-shared` (shared/: small generic helpers, **built**) is the umbrella panel this protects.
- L9 `test_hit_returns_the_stored_value` — a set key is retrieved unchanged before TTL — cm-shared
- L15 `test_miss_on_unknown_key_returns_none` — unknown key returns `None` — cm-shared
- L20 `test_entry_expires_after_ttl` — entry past its TTL returns `None` — cm-shared
- L29 `test_entry_survives_up_to_the_ttl_boundary` — entry just under TTL still returns its value — cm-shared
- L38 `test_expired_entry_is_evicted_on_read` — a zero-TTL entry is both unreadable and removed from `len()` — cm-shared
- L45 `test_max_entries_evicts_the_oldest_insertion` — inserting past `max_entries` evicts the oldest key (LRU-by-insertion) — cm-shared
- L56 `test_unbounded_when_max_entries_is_none` — 1000 inserts with no cap all survive — cm-shared

### `app/shared/tests/test_rate_limiter.py`
Purpose: the fixed-window rate limiter shared by the webhook and chat endpoints. No dedicated panel; protects `i1-checks` / `r1-limits` indirectly via the shared primitive — cited as cm-shared here, i1-checks/r1-limits at the call-site tests below.
- L9 `test_allows_up_to_max_requests_within_the_window` — exactly `max` requests pass in one window — cm-shared
- L16 `test_request_is_allowed_again_once_the_window_elapses` — a new window resets the count — cm-shared
- L23 `test_distinct_keys_are_independent` — one key's usage never affects another's — cm-shared
- L29 `test_expired_bucket_is_pruned_from_the_dict_on_next_access` — a stale bucket is garbage-collected on next touch — cm-shared
- L39 `test_bucket_count_stays_bounded_across_many_distinct_keys` — many keys don't grow the dict unboundedly on their own — cm-shared
- L48 `test_max_tracked_keys_evicts_the_oldest_key_first` — hitting `max_tracked_keys` evicts oldest-first — cm-shared
- L58 `test_unbounded_when_max_tracked_keys_is_none` — no cap means no eviction — cm-shared

## `app/platform/clients/tests/` — level: unit (httpx.MockTransport / fakes; no live network)

### `app/platform/clients/tests/test_anthropic_client.py`
Purpose (L1): retry/backoff, circuit breaker, input abuse cap on the shared Anthropic Messages client used by generate/rewrite/classify/identity/image-analysis calls.
- L23 `test_create_message_happy_path` — a 200 response returns the text block — r5-generate
- L28 `test_missing_key_raises_without_tripping_breaker` — an empty API key always raises, never trips the breaker — r5-generate
- L35 `test_input_abuse_cap_rejects_oversized_prompt` — text over `max_input_chars` is rejected before the call; under-cap still works — r5-generate
- L45 `test_circuit_breaker_opens_after_consecutive_failures` — N consecutive 500s open the breaker; further calls fail fast without a request — r5-generate
- L96 `test_create_message_content_shape` (×3 params: with-images, image-only, text-only) — image blocks precede text; an image-only turn never sends an empty `{"type":"text","text":""}` block (Anthropic 400s on that) — r5-image
- L113 `test_success_resets_the_breaker` — one failure below threshold, then a success resets the failure counter — r5-generate

### `app/platform/clients/tests/test_reranker_client.py`
Purpose: `FakeReranker` determinism plus the real Cohere client's shape, breaker and abuse cap.
- L22 `test_fake_is_deterministic_order_preserving_and_truncates` — r4-rerank
- L34 `test_fake_empty_input` — r4-rerank
- L38 `test_fake_satisfies_the_reranker_protocol` — r4-rerank
- L42 `test_cohere_sends_v2_shape_and_maps_indices_back_to_page_ids` — Cohere v2 request shape is correct and returned indices map back to the original page ids — r4-rerank
- L74 `test_cohere_breaker_opens_after_threshold` — r4-rerank
- L98 `test_cohere_abuse_cap_rejects_oversized_call` — r4-rerank
- L107 `test_factory_returns_fake_for_empty_or_fake_provider` — r4-rerank
- L112 `test_factory_falls_back_to_fake_offline_without_key` — r4-rerank
- L117 `test_factory_raises_in_production_without_key` — production without a key fails closed rather than silently degrading — r4-rerank
- L123 `test_factory_builds_cohere_with_key` — r4-rerank

### `app/platform/clients/tests/test_embeddings_client.py`
- L24 `test_fake_provider_is_deterministic_and_right_dim` — r2-embed
- L34 `test_fake_provider_empty_input` — r2-embed
- L38 `test_openai_provider_batches_and_sends_dimensions` — batches at 128/call, sends the configured dim — i3-embed
- L71 `test_openai_breaker_opens_after_threshold` — i3-embed
- L94 `test_abuse_cap_rejects_oversized_call` — i3-embed
- L107 `test_factory_falls_back_to_fake_offline_without_key` — i3-embed
- L116 `test_factory_raises_in_production_without_key` — i3-embed

### `app/platform/clients/tests/test_confluence_client.py`
Purpose: page-restriction resolution (fail-closed on group-only restrictions), the HTTP gateway's retry/breaker/pagination, and the fixture gateway used everywhere else in the suite.
- L41-L83 (`test_group_only_restriction_resolves_to_fail_closed_sentinel`, `test_user_and_group_restriction_without_resolver_keeps_only_resolved_users`, `test_user_only_restriction_is_unaffected`, `test_no_restriction_entries_resolves_to_unrestricted`, `test_group_restriction_expands_via_resolver`, `test_group_and_user_restriction_expands_and_unions_via_resolver`, `test_group_restriction_resolver_finding_no_members_still_fails_closed`) — pure restriction-merge logic; a group whose members can't be resolved fails closed rather than opening the page — r3-groups
- L94-L246 (`test_http_client_group_only_restriction_fails_closed` through `test_http_client_group_member_lookup_paginates_without_doubling_wiki_prefix`) — the real HTTP gateway's restriction fetch, v1 content endpoint, group-member pagination and caching — r3-groups, ov-confluence
- L309-L381 (`test_http_client_retries_on_5xx_then_succeeds`, `test_http_client_4xx_is_not_retried`, `test_http_client_breaker_trips_after_consecutive_failures`, `test_http_client_success_resets_the_breaker`, `test_http_client_logs_retry_and_status_lines`) — retry/breaker discipline on the Confluence HTTP client — ov-confluence
- L414-L461 (`test_fixture_gateway_*`) — the deterministic fixture gateway used by all db-level tests mirrors the real gateway's restriction/group behavior — ov-confluence
- L462-L622 (`test_get_attachments_includes_download_link` through `test_fixture_gateway_set_restrictions_override_bypasses_resolution`) — attachment listing/download: redirect handling drops auth on cross-host redirects, size cap enforced even against a lying `Content-Length`, 4xx/empty-link degrade to `None` not a crash — i3-attach

## `app/platform/config/tests/` — level: unit

### `app/platform/config/tests/test_platforms.py`
Purpose: `config/platforms.json` → live-slug mapping, the config-is-data rule (CLAUDE.md "Config is data").
- L19 `test_maps_platform_key_to_live_slugs` — cm-config
- L48 `test_unknown_slug_in_integrations_stops_startup` — an unrecognized slug fails closed at startup, not at request time — cm-config
- L69 `test_empty_platforms_stops_startup_when_not_allowed` — cm-config
- L75 `test_empty_platforms_allowed_locally` — cm-config
- L81 `test_general_always_appended_even_if_omitted` — `general` is always a member of the allowed-scopes set — cm-config
- L104 `test_classified_scope_is_never_mappable` — the `classified` tag can never be mapped to a platform — cm-config
- L125 `test_hs256_alg_is_forbidden` — HS256 (symmetric) tokens are rejected by config, only asymmetric algorithms allowed — r1-auth

### `app/platform/config/tests/test_knowledge_scopes.py`
- L24 `test_parses_lowercases_and_trims` — cm-config
- L43 `test_missing_general_raises` — cm-config
- L53 `test_empty_scopes_raises` — cm-config
- L60 `test_blank_names_are_ignored` — cm-config
- L69 `test_committed_repo_config_file_is_well_formed` — the actual `config/knowledge_scopes.json` in the repo parses cleanly — cm-config

### `app/platform/config/tests/test_settings.py`
- L20 `test_knowledge_scope_set_reads_the_committed_config_file` — cm-config
- L30 `test_construction_fails_fast_when_config_file_is_invalid` — cm-config
- L49 `test_default_knowledge_scope_defaults_to_empty` — no panel — Settings default value
- L53 `test_enable_knowledge_scope_filtering_defaults_to_false` — no panel — feature-flag default
- L60 `test_obi_identity_path_defaults_to_empty` — no panel — identity feature is not on the design page (see "Not on the design page")
- L64 `test_obi_identity_text_reads_the_file_when_present` — no panel
- L72 `test_obi_identity_text_is_empty_when_file_missing_does_not_raise` — no panel

## `app/platform/db/tests/` — level: **db** for the four migration files (real Postgres + real Alembic, see fixture at L63-L88 of each); **unit** for the other two (pure metadata / no live connection)

### `app/platform/db/tests/test_migration_0007_knowledge_scope.py` — db
- L106 `test_0007_upgrade_creates_the_new_shape` — `curated_knowledge_entry` table, `query_trace.allowed_knowledge_scopes` column and the tags GIN index all exist after `upgrade(head)` — cm-alembic
- L128 `test_0007_downgrade_then_upgrade_round_trips_cleanly` — downgrade removes them byte-for-byte, re-upgrade restores them — cm-alembic

### `app/platform/db/tests/test_migration_0009_reader_rls_reconcile.py` — db
- L120 `test_0009_adds_reader_policy_and_keeps_rls_on` — cm-alembic, s-reader
- L134 `test_0009_downgrade_then_upgrade_round_trips` — cm-alembic

### `app/platform/db/tests/test_migration_0010_scope_rls.py` — db
- L118 `test_0010_adds_restrictive_scope_policies` — cm-alembic, s-source
- L132 `test_0010_downgrade_then_upgrade_round_trips` — cm-alembic

### `app/platform/db/tests/test_migration_0011_subject_hash.py` — db
- L94 `test_0011_adds_subject_hash_and_round_trips` — cm-alembic

### `app/platform/db/tests/test_models_constraints.py` — unit (docstring L8: "pure metadata inspection, no DB needed")
- L26 `test_chunk_has_exactly_one_canonically_named_source_type_check` — a hand-named CHECK constraint isn't silently re-prefixed by SQLAlchemy's naming convention — cm-platform
- L30 `test_page_source_has_exactly_one_canonically_named_source_type_check` — cm-platform
- L34 `test_source_scope_has_canonically_named_checks` — cm-platform

### `app/platform/db/tests/test_engine_reader_role.py` — unit (docstring L6: "without a live DB connection")
- L32 `test_offline_env_with_unset_reader_url_falls_back_to_writer_engine` (×4 envs: local/test/dev/ci) — s-reader
- L42 `test_non_offline_env_with_unset_reader_url_fails_closed` (×3 envs: production/staging/prod) — an unset reader URL outside offline envs raises `ReaderRoleMisconfiguredError` rather than silently using the RLS-bypassing writer — s-reader
- L51 `test_reader_url_set_never_fails_regardless_of_env` (×3 envs) — s-reader

## `app/features/ingestion/tests/` — level: unit (all use fakes/spies; several docstrings say "no database needed")

### `app/features/ingestion/tests/test_attachment_extraction.py`
- L13-L37 (`test_plain_text`, `test_csv_flattened_to_readable_rows`, `test_html_stripped_to_text`, `test_markdown_passthrough`) — per-mimetype text extraction — i3-attach
- L43 `test_pdf_with_good_native_text_does_not_need_ocr` — i3-attach
- L55 `test_scanned_pdf_with_empty_native_text_needs_ocr` — i3-attach
- L66 `test_image_always_needs_ocr` — i3-attach
- L72 `test_unsupported_binary_is_skipped_not_crashed` — i3-attach
- L80 `test_missing_optional_lib_degrades_to_skipped` — an unavailable optional parser degrades gracefully rather than crashing ingestion — i3-attach
- L95 `test_attachment_to_blocks_wraps_text_under_title_keyed_heading_path` (×2 params) — i3-attach
- L105 `test_attachment_to_blocks_empty_text_returns_nothing` — i3-attach
- L110 `test_attachment_to_blocks_distinct_attachments_get_distinct_heading_paths` — i3-attach

### `app/features/ingestion/tests/test_chunking.py`
- L30 `test_small_section_yields_one_parent_one_child` — i3-parents / i3-children
- L41 `test_large_section_splits_into_multiple_children_under_max` — i3-children
- L52 `test_children_cover_parent_content` — the union of a parent's children reconstructs its content with no gaps — i3-children
- L61 `test_stable_keys_are_deterministic` — i3-parents
- L70 `test_editing_one_section_keeps_other_section_keys_stable` — an edit to one section never reassigns the stable key of an untouched sibling section (this is what makes embedding reuse possible) — i3-embed
- L89 `test_empty_blocks_yield_empty_plan` — i3-parents
- L93 `test_heading_path_propagates_to_children` — i3-children

### `app/features/ingestion/tests/test_attachment_wiring.py` — see confluence_sync section (same filename exists there; this one is the DB-free chunk-shape half); *(note: this file actually lives only under confluence_sync/tests — see below; no duplicate here)*

### `app/features/ingestion/tests/test_chunk_diff.py`
Purpose (L1, implied): the reuse-guard diff between old and new chunk plans, keyed by stable key — directly backs i3-embed's documented "today" deviation ("only changed children are embedded... target: all children, every rebuild").
- L21 `test_identical_reuses_everything` — i3-embed
- L31 `test_edited_in_slot_reembeds_only_that_chunk` — i3-embed
- L41 `test_moved_content_reuses_embedding` — content that moved slot but is textually identical still reuses its embedding — i3-embed
- L53 `test_added_and_removed` — i3-embed
- L62 `test_reuse_count_helper` — i3-embed

### `app/features/ingestion/tests/test_tokenization.py`
No panel — token-counting/window-splitting helper used internally by chunking (`i3-parents`/`i3-children`); the design page has no dedicated tokenization panel.
- L15 `test_empty_and_whitespace_count_zero` — no panel
- L20 `test_count_is_positive_and_monotonic` — no panel
- L27 `test_split_windows_never_exceed_max` — no panel
- L35 `test_split_short_text_returns_single_window` — no panel
- L40 `test_split_empty_returns_empty_list` — no panel
- L44 `test_split_covers_all_words_when_no_overlap` — no panel
- L50 `test_split_rejects_overlap_ge_max` — overlap >= max window is rejected (would infinite-loop) — no panel

### `app/features/ingestion/tests/test_contextualizer.py`
- L30 `test_fallback_prefixes_heading_path_deterministically` — i3-context
- L42 `test_disabled_returns_plain_chunk_text` — i3-context
- L49 `test_llm_path_sends_cached_document_and_prepends_context` — i3-context, vd-text
- L78 `test_llm_failure_falls_back_without_raising` — i3-context
- L89 `test_llm_meta_refusal_is_discarded_and_falls_back_to_metadata` — a meta-refusal from the LLM ("I can't help with that") is detected and discarded, not embedded as context — i3-context
- L125 `test_llm_real_context_first_person_is_not_discarded` — the meta-refusal detector doesn't false-positive on legitimate first-person context — i3-context
- L143 `test_document_text_is_truncated_to_cap` — i3-context

### `app/features/ingestion/tests/test_pipeline_reuse.py`
Purpose (L1): "only new/edited children are re-embedded (DB-free, spy embedder)" — same i3-embed drift as test_chunk_diff.py.
- L73 `test_first_index_embeds_all_children` — i3-embed
- L83 `test_reindex_identical_reuses_all_embeddings` — i3-embed
- L98 `test_edit_one_section_reembeds_only_changed_children` — i3-embed

## `app/features/retrieval/tests/` — level: unit (spy-session pattern; docstrings explicitly say "no database needed")

### `app/features/retrieval/tests/test_search_repo_gucs.py`
Purpose (L1-L7): the per-transaction pgvector HNSW GUC helper; `SET LOCAL` can't bind params so inputs are whitelist-validated instead.
- L32 `test_emits_both_gucs_with_valid_values` — r2-gucs
- L41 `test_ef_search_is_coerced_to_int` — r2-gucs
- L48 `test_unknown_scan_mode_falls_back_to_relaxed_order` — r2-gucs
- L54 `test_injection_attempt_never_reaches_sql` — an `iterative_scan` value crafted as a SQL-injection attempt degrades to `relaxed_order` instead of reaching the SQL string — r2-gucs

### `app/features/retrieval/tests/test_search_repo_knowledge_scope.py`
- L37 `test_keyword_search_omits_predicate_when_knowledge_scopes_is_none` — r2-keyword
- L45 `test_keyword_search_adds_predicate_when_knowledge_scopes_given` — r2-keyword
- L55 `test_dense_search_omits_predicate_when_knowledge_scopes_is_none` — r2-dense
- L63 `test_dense_search_adds_predicate_when_knowledge_scopes_given` — r2-dense
- L71 `test_fetch_rerank_texts_adds_predicate_when_knowledge_scopes_given` — r4-rerank
- L79 `test_fetch_rerank_texts_omits_predicate_when_knowledge_scopes_is_none` — r4-rerank
- L87 `test_malicious_knowledge_scope_value_never_reaches_sql_text` — no panel — SQL-injection guard on the scope filter

### `app/features/retrieval/tests/test_knowledge_scope.py`
Purpose: `resolve_allowed_scopes` default/requested-scope resolution logic.
- L15 `test_no_request_or_default_returns_general_only` — no panel — resolve_allowed_scopes defaulting
- L19 `test_recognized_requested_scope_is_added_to_general` — no panel
- L26 `test_requested_scope_matching_is_case_insensitive` — no panel
- L33 `test_unrecognized_requested_scope_degrades_to_default` — no panel
- L40 `test_unrecognized_requested_scope_with_no_default_degrades_to_general_only` — no panel
- L44 `test_no_requested_scope_falls_back_to_default` — no panel
- L51 `test_unrecognized_default_is_ignored` — no panel
- L55 `test_result_is_sorted` — no panel

### `app/features/retrieval/tests/test_fusion_and_permission.py`
- L9 `test_rrf_rewards_top_ranks_and_agreement` — no panel (rrf status is `change`, not `built`) — protects reciprocal-rank-fusion scoring
- L19 `test_rrf_weights_apply` — no panel
- L24 `test_classify_scope_splits_digit_strings_from_principal_ids` — r3-acl
- L30 `test_space_scope_grants_space_and_blocks_others` — r3-acl
- L38 `test_principal_scope_blocks_unauthorized` — r3-acl
- L48 `test_numeric_principal_argument_is_never_reinterpreted_as_space_trust` — a numeric principal string is never mistaken for a space id, which would grant space-wide trust — r3-acl

## `app/features/evaluation/tests/` — level: unit (pure functions over in-memory data; these are unit tests *of* the metrics the `make eval` gold-set runner uses, not the runner itself — see the "eval" level note below)

### `app/features/evaluation/tests/test_fixtures_loader.py`
- L12 `test_fixtures_dir_exists` — e-gold
- L18 `test_list_pages_expected_ids` — e-gold
- L24 `test_status_coverage` — e-gold
- L32 `test_load_page_1001_versions` — e-gold
- L60 `test_labels_restrictions_attachments` — e-gold
- L84 `test_attachment_files_present` — e-gold

### `app/features/evaluation/tests/test_retrieval_metrics.py`
- L16 `test_recall_at_k_partial` — e-stage1
- L24 `test_recall_at_k_full_and_empty_relevant` — e-stage1
- L29 `test_precision_at_k_uses_k_denominator` — e-stage1
- L39 `test_mrr_first_relevant_rank` — e-stage1
- L50 `test_ndcg_at_k_known_value` — e-stage1
- L59 `test_ndcg_perfect_and_empty` — e-stage1
- L64 `test_hit_rate_at_k` — e-stage1
- L71 `test_duplicates_collapsed` — e-stage1

### `app/features/evaluation/tests/test_rerank_lift.py`
- L28 `test_positive_lift_on_precision_and_ndcg` — e-stage2
- L51 `test_zero_lift_when_order_unchanged` — e-stage2
- L65 `test_empty_dataset_is_safe` — e-stage2

### `app/features/evaluation/tests/test_latency_metrics.py`
- L15 `test_percentile_interpolation` — e-ops
- L25 `test_percentile_p95_known` — e-ops
- L31 `test_summarize_latencies` — e-ops
- L41 `test_summarize_empty` — e-ops
- L47 `test_check_targets_pass_and_fail` — e-ops
- L61 `test_latency_timer_records_and_appends` — e-ops

### `app/features/evaluation/tests/test_fallback_metrics.py`
- L23 `test_fallback_rate` (×4 param sets) — e-stage4
- L37 `test_citation_grounding_rate` (×4 param sets) — e-stage4

### `app/features/evaluation/tests/test_runner_baseline.py`
- L18 `test_report_structure` — e-gold
- L37 `test_perfect_ranker_scores_recall_one` — e-gold
- L52 `test_empty_ranker_scores_zero` — e-gold
- L67 `test_now_iso_is_not_a_clock` — no panel — timestamp helper is injectable, not `datetime.now()` directly

## `app/features/rag_agent/tests/` — level: unit (no dedicated conftest in this dir; each file uses fakes/spies/monkeypatch)

### `app/features/rag_agent/tests/test_pii.py`
- L19 `test_redacts_pii_by_type` (×4: email/SSN/card/phone) — no panel — PII redaction before any LLM call
- L25 `test_leaves_plain_text_untouched` — no panel
- L30 `test_redacts_multiple_occurrences` — no panel
- L35 `test_obfuscated_email_evades_redaction_documented_known_gap` — a deliberately obfuscated email is **not** caught; the test name records this as a known, accepted gap — no panel

### `app/features/rag_agent/tests/test_citations.py`
- L8 `test_keeps_cited_sentence_and_reports_used_markers` — r5-enforce
- L14 `test_strips_uncited_claim` — r5-enforce
- L23 `test_strips_claim_that_only_cites_a_hallucinated_source` — a citation number pointing at no real evidence block is stripped, not trusted — r5-enforce
- L30 `test_drops_invalid_marker_but_keeps_a_validly_cited_sentence` — r5-enforce
- L36 `test_used_markers_are_sorted_and_deduped` — r5-enforce
- L44 `test_empty_answer_returns_empty` — r5-enforce

### `app/features/rag_agent/tests/test_refusal.py`
- L35 `test_shipped_thresholds_map_supported_answer_offtopic_redirect_weak_handoff` — r4-refuse
- L54 `test_offtopic_when_candidate_at_or_below_offtopic_threshold` — r4-refuse
- L61 `test_weak_score_when_between_offtopic_and_refusal_threshold` — r4-weak
- L67 `test_no_candidates_is_a_handoff_not_an_offtopic_redirect` — r4-refuse
- L74 `test_allows_when_top_score_at_or_above_threshold` — r4-refuse
- L79 `test_allowed_decision_has_no_reason` — r4-refuse
- L83 `test_has_image_never_refuses_on_no_candidates` — a turn carrying an image never refuses purely for lack of text candidates — r5-image
- L91 `test_has_image_never_refuses_on_offtopic_or_weak_score` — r5-image
- L96 `test_has_image_true_does_not_change_a_strong_score_outcome` — r5-image

### `app/features/rag_agent/tests/test_small_talk.py`
- L45 `test_recognizes_small_talk_phrases_case_and_whitespace_insensitively` (×25 phrases) — r1-small
- L65 `test_does_not_match_real_questions_even_when_they_start_with_a_greeting` (×9 phrases, incl. a prompt-injection attempt) — a greeting-prefixed real question, and an injection attempt disguised as small talk, both still run the full pipeline — r1-small

### `app/features/rag_agent/tests/test_identity.py`
No panel — self-identity Q&A ("who am I", "what company am I") has no panel on the design page at all; see "Not on the design page".
- L42 `test_recognizes_identity_questions_case_and_whitespace_insensitively` (×20 phrases) — no panel
- L65 `test_does_not_match_capability_or_real_questions` (×11 phrases) — no panel
- L69 `test_identity_facts_reports_business_identity_when_integration_present` — no panel
- L74 `test_identity_facts_reports_no_business_identity_when_integration_absent` — no panel

### `app/features/rag_agent/tests/test_clarification.py`
- L31 `test_long_query_is_never_ambiguous_and_skips_the_classifier` — r1-clarify
- L41 `test_empty_query_is_never_ambiguous_and_skips_the_classifier` — r1-clarify
- L48 `test_short_query_falls_through_to_the_classifier_and_returns_its_verdict` — r1-clarify
- L58 `test_short_but_specific_query_can_still_be_judged_not_ambiguous` — r1-clarify
- L69 `test_history_is_accepted_but_not_required_to_be_non_empty` — r1-clarify
- L118 `test_parse_clarification_reply` (×6 params) — parses the fixed clarification-question/options shape out of the model's reply — r1-clarify

### `app/features/rag_agent/tests/test_auth_context.py`
- L58 `test_builds_scoped_context` — r1-ctx
- L68 `test_company_id_only_difference_yields_identical_scopes` — company_id is display-only and never affects allowed_scopes — r1-ctx
- L75 `test_no_business_values_is_general_only` — r1-ctx
- L84 `test_unknown_integration_raises` — r1-ctx
- L89 `test_general_only_context_helper` — r1-ctx

### `app/features/rag_agent/tests/test_curated_knowledge.py`
Purpose (L1-L7): "no database needed — mirrors retrieval/tests/test_search_repo_knowledge_scope.py's spy-session style"; scope-filtering against real Postgres is proven separately in confluence_sync/tests/test_curated_knowledge_repo.py.
- L19 `test_curated_entry_to_hit_uses_a_namespaced_page_id_and_negative_chunk_id` — no panel (r2-curated status is `change`) — curated-entry-to-Hit adapter
- L28 `test_curated_entry_to_hit_ids_never_collide_between_distinct_entries` — no panel
- L64 `test_fetch_curated_entries_sets_the_scope_rls_guc_before_reading` — the scope RLS GUC is set (bound, not interpolated) before the SELECT — no panel
- L75 `test_fetch_curated_entries_binds_scopes_as_a_parameter_never_interpolated` — no panel
- L84 `test_fetch_curated_entries_binds_a_malicious_scope_value_never_reaches_raw_sql` — a SQL-injection-shaped scope value never reaches the SQL text — no panel
- L97 `test_fetch_curated_entries_includes_the_empty_tags_always_included_clause` — no panel

### `app/features/rag_agent/tests/test_token_verifier.py`
- L72 `test_valid_token` — r1-auth
- L82 `test_unknown_issuer_rejected` — r1-auth
- L88 `test_hs256_rejected` — algorithm allow-list rejects HS256 — r1-auth
- L104 `test_wrong_audience_rejected` — r1-auth
- L109 `test_expired_rejected` — r1-auth
- L121 `test_lifetime_over_platform_max_rejected` — r1-auth
- L133 `test_missing_iat_rejected` — r1-auth
- L145 `test_partial_business_claims_rejected` — the three business claims (company_id/company_name/integration) are all-or-none — r1-auth
- L152 `test_no_business_claims_is_valid` — r1-auth

### `app/features/rag_agent/tests/test_token_claims_contract.py`
Purpose: the shared claims contract (`packages/contracts`) matches the verifier's own expectations.
- L24 `test_required_claims_match_the_verifier` — cm-contracts
- L29 `test_audience_constant_matches_the_verifier` — cm-contracts
- L34 `test_business_claims_are_all_three_or_none` — cm-contracts

### `app/features/rag_agent/tests/test_prompt.py`
- L25 `test_build_rewrite_prompt_includes_every_turn_in_order` — no panel (r1-rewrite status is `change`, not `built`)
- L39 `test_build_evidence_block_numbers_markers_from_one_in_hit_order` — r5-evidence
- L48 `test_build_evidence_block_missing_parent_text_degrades_to_empty_body` — r5-evidence
- L54 `test_build_evidence_block_empty_hits_is_empty_string` — r5-evidence
- L58 `test_build_answer_prompt_includes_question_and_evidence` — r5-evidence
- L68 `test_identity_system_prompt_carries_no_citation_and_anti_injection_rules` — no panel (identity feature, undocumented)
- L75 `test_build_identity_system_prompt_appends_operator_static_block` — no panel
- L81 `test_build_identity_system_prompt_with_no_static_block_is_just_the_base_prompt` — no panel
- L86 `test_build_identity_context_block_renders_business_identity` — no panel
- L95 `test_build_identity_context_block_without_identity_says_so_honestly` — no panel

### `app/features/rag_agent/tests/test_llm_client.py`
- L31 `test_rewrite_redacts_pii_before_sending` — no panel (rewrite)
- L46 `test_rewrite_single_turn_skips_the_call_entirely` — no panel
- L54 `test_rewrite_fails_open_to_verbatim_last_turn_on_error` — a rewrite failure fails open to the verbatim last turn rather than blocking the answer — no panel
- L68 `test_generate_redacts_pii_and_sends_cached_system_block` — r5-generate
- L81 `test_generate_sends_natural_writing_style_guidance_alongside_citation_rules` — r5-generate
- L96 `test_generate_small_talk_sends_the_small_talk_system_prompt_and_redacts_pii` — r1-small
- L109 `test_generate_small_talk_fails_open_to_a_static_greeting_on_error` — r1-small
- L122 `test_generate_identity_sends_cached_static_block_plus_uncached_per_user_block` — no panel (identity)
- L145 `test_generate_identity_redacts_pii_in_the_query` — no panel
- L157 `test_generate_identity_fails_open_to_a_static_reply_on_error` — no panel
- L172 `test_generate_image_analysis_redacts_query_and_sends_image_blocks` — r5-image
- L192 `test_generate_image_analysis_never_reaches_enforce_citations_shape` — r5-image
- L207 `test_generate_image_analysis_fails_open_to_a_short_notice_on_error` — r5-image
- L232 `test_classify_redacts_pii_and_sends_the_ambiguity_system_prompt` — r1-clarify
- L245 `test_classify_returns_true_for_an_ambiguous_verdict` — r1-clarify
- L250 `test_classify_returns_false_for_a_specific_verdict` — r1-clarify
- L255 `test_classify_fails_open_to_not_ambiguous_on_error` — r1-clarify
- L266 `test_generate_clarification_redacts_pii_and_sends_the_clarification_system_prompt` — r1-clarify
- L283 `test_generate_clarification_never_sends_an_evidence_block_or_citation_instruction` — a clarifying reply is never given evidence text or told to cite — r1-clarify
- L295 `test_generate_clarification_fails_open_to_a_static_fallback_on_error` — r1-clarify
- L309 `test_generate_clarification_fails_open_to_a_static_fallback_on_an_unparseable_reply` — r1-clarify
- L321 `test_classify_requires_a_leading_ambiguous_token_not_a_buried_one` — r1-clarify
- L333 `test_generate_clarification_parser_discards_any_text_outside_the_fixed_shape` — r1-clarify

### `app/features/rag_agent/tests/test_answer_cache.py`
No panel found (grep for "answer cache" / "exact-match" against the design page returns nothing) — this is the PLAN-5 exact-match answer cache; see "Not on the design page".
- L39 `test_identical_history_and_scope_is_served_from_cache` — no panel
- L50 `test_different_scope_is_not_served_from_cache` — no panel
- L61 `test_different_history_is_not_served_from_cache` — no panel
- L71 `test_earlier_turns_are_part_of_the_cache_key` — no panel
- L92 `test_expired_entry_recomputes` — no panel
- L105 `test_identical_history_scope_and_knowledge_scope_is_served_from_cache` — no panel
- L121 `test_different_knowledge_scope_is_not_served_from_cache` — no panel
- L139 `test_omitted_knowledge_scope_is_not_conflated_with_a_named_one` — no panel
- L152 `test_different_token_subject_is_not_served_from_cache` — one user's cached answer never leaks to a different token subject — no panel
- L164 `test_max_entries_bounds_the_cache` — no panel

### `app/features/rag_agent/tests/test_answer_service.py`
Purpose: the full answer pipeline orchestration (rewrite → retrieve → rerank/CRAG-retry → generate → cite → refuse), 46 tests, largest backend file at 1125 lines.
- L229 `test_grounded_answer_with_rewrite_and_persisted_trace` — r5-stream
- L263 `test_rewrite_disabled_skips_rewriter_and_uses_verbatim_query` — no panel
- L280 `test_no_candidates_refuses_without_calling_generator` — r4-refuse
- L294 `test_no_candidates_refusal_emits_human_handoff_log` — r4-refuse
- L313 `test_off_topic_refusal_redirects_without_human_handoff` — r4-refuse
- L342 `test_weak_score_refusal_still_emits_human_handoff` — r4-weak
- L367 `test_no_citations_refusal_emits_human_handoff_log_with_verbatim_original_query` — r5-nocite
- L392 `test_successful_answer_emits_no_human_handoff_log` — r5-stream
- L411 `test_weak_result_retries_once_and_succeeds_on_original_query` — the CRAG-style one-shot retry — r4-weak
- L430 `test_weak_result_still_weak_after_retry_refuses` — r4-weak
- L447 `test_crag_max_retries_zero_never_retries` — a config of zero retries genuinely never retries — r4-weak
- L462 `test_no_surviving_citation_degrades_to_refusal` — r5-nocite
- L477 `test_rejects_history_not_ending_in_user_turn` — r1-limits
- L488 `test_injected_instruction_in_query_never_changes_the_scope_passed_to_retrieval` — a prompt-injection attempt in the query text never changes which scopes are passed to the retriever — r1-ctx
- L510 `test_generator_citing_a_marker_beyond_the_retrieved_hits_is_stripped` — r5-enforce
- L530 `test_generator_that_ignores_citation_instructions_entirely_refuses_rather_than_leaks` — r5-nocite
- L548 `test_evidence_sent_to_the_generator_never_exceeds_what_retrieval_actually_returned` — r5-evidence
- L568 `test_small_talk_short_circuits_before_rewrite_or_retrieval` — r1-small
- L586 `test_small_talk_writes_no_query_trace_row` — r1-small
- L598 `test_real_question_that_merely_starts_with_a_greeting_still_runs_the_full_pipeline` — r1-small
- L616 `test_identity_question_short_circuits_before_rewrite_or_retrieval` — no panel (identity)
- L642 `test_identity_question_writes_no_query_trace_row` — no panel
- L657 `test_identity_question_on_tokenless_path_still_answers_with_empty_facts` — no panel
- L671 `test_identity_question_checked_after_small_talk` — no panel
- L684 `test_real_question_sharing_words_with_identity_still_runs_full_pipeline` — no panel
- L704 `test_rejects_empty_history` — r1-limits
- L715 `test_no_image_never_calls_generate_image_analysis` — r5-image
- L728 `test_image_on_turn_with_no_retrieved_candidates_does_not_refuse` — r5-image
- L743 `test_image_analysis_survives_a_citation_enforcement_refusal` — r5-image
- L762 `test_image_only_turn_with_empty_content_skips_retrieval` — r5-image
- L785 `test_clarification_branch_disabled_by_default_never_calls_the_classifier` — r1-clarify
- L801 `test_clarification_branch_with_non_ambiguous_verdict_runs_the_full_pipeline_unchanged` — r1-clarify
- L830 `test_clarification_branch_enabled_with_ambiguous_verdict_bypasses_the_pipeline` — r1-clarify
- L862 `test_clarification_branch_ambiguous_verdict_writes_no_query_trace_row` — r1-clarify
- L884 `test_clarification_branch_enabled_with_no_classifier_configured_is_a_no_op` — r1-clarify
- L899 `test_small_talk_short_circuits_before_the_clarification_classifier_too` — r1-small
- L918 `test_image_analysis_is_never_passed_through_citation_enforcement` — r5-image
- L939 `test_auth_allowed_scopes_reach_the_retriever_verbatim` — r1-ctx
- L956 `test_subject_hash_persisted_is_the_hash_not_the_raw_subject` — the raw token subject is never persisted to `query_trace`, only its hash — s-audit
- L973 `test_omitted_knowledge_scope_with_no_default_is_general_alone` — no panel
- L983 `test_crag_retry_reuses_the_same_resolved_allowed_scopes` — r4-weak
- L1011 `test_no_reader_sessionmaker_configured_composes_zero_curated_entries` — no panel (curated, `change` status)
- L1025 `test_curated_entries_are_prepended_as_markers_1_through_k` — no panel
- L1055 `test_curated_entry_citation_survives_enforce_citations_exactly_like_a_retrieved_one` — r5-enforce
- L1082 `test_curated_entries_fetched_with_the_same_resolved_allowed_scopes` — no panel
- L1108 `test_curated_entries_still_compose_on_the_text_empty_image_only_path` — no panel

## `app/features/confluence_sync/tests/` — level: **db** (shared `conftest.py:58-98`: session-scoped real Postgres, `schema.create_all` + RLS + reader role, truncated between tests via `_truncate` L101-106)

### `app/features/confluence_sync/tests/test_webhook.py`
- L47 `test_valid_signed_event_is_accepted_and_enqueued` — i1-webhook
- L58 `test_missing_signature_is_rejected` — i1-checks
- L66 `test_bad_signature_is_rejected` — i1-checks
- L74 `test_duplicate_delivery_is_deduped` — i1-ledger
- L84 `test_self_generated_event_enqueues_no_job` — i1-self
- L96 `test_oversized_body_is_rejected` — i1-checks
- L103 `test_unset_secret_fails_closed` — i1-checks
- L111 `test_rate_limit_returns_429` — i1-checks

### `app/features/confluence_sync/tests/test_event_dedup.py`
- L28 `test_duplicate_delivery_is_idempotent` — i1-ledger
- L41 `test_in1_duplicate_result_stops_before_enqueue` — i1-ledger
- L60 `test_same_delivery_id_different_payload_dedupes_gracefully_not_500` — i1-ledger

### `app/features/confluence_sync/tests/test_job_queue.py`
- L24 `test_claim_uses_skip_locked` — a worker claim uses `SELECT ... FOR UPDATE SKIP LOCKED`, never blocking on a peer — i1-claim
- L42 `test_fail_backs_off_then_dead_letters` — i1-fail
- L62 `test_reap_reclaims_expired_lease` — i1-reaper

### `app/features/confluence_sync/tests/test_scheduler.py`
No panel — the dev-only periodic reconcile scheduler wiring has no panel on the design page.
- L20 `test_dev_reconcile_job_absent_by_default` — no panel
- L32 `test_dev_reconcile_job_registered_when_interval_set` — no panel

### `app/features/confluence_sync/tests/test_reader_rls_reconcile.py`
- L49 `test_reader_freed_but_anon_stays_denied` — s-anon
- L94 `test_apply_reader_rls_leaves_chunk_source_isolation_intact` — s-source
- L120 `test_apply_reader_rls_skips_policy_when_role_absent` — s-reader

### `app/features/confluence_sync/tests/test_knowledge_scope_backfill.py`
Purpose: the readiness gate operator tool (`scripts/`) that confirms every active chunk has a knowledge-scope tag before the filter flag can be turned on.
- L60 `test_all_active_chunks_scope_tagged_is_ready` — cm-scripts, ks-index
- L72 `test_untagged_active_chunk_is_not_ready` — cm-scripts
- L84 `test_source_scope_tag_alone_does_not_count` — cm-scripts
- L101 `test_each_recognized_scope_tag_counts` (×4: general/mews/opera-cloud/toast) — cm-scripts
- L111 `test_partial_coverage_lists_only_untagged_pages` — cm-scripts
- L126 `test_inactive_untagged_chunks_are_ignored` — cm-scripts
- L148 `test_empty_corpus_is_vacuously_ready` — cm-scripts

### `app/features/confluence_sync/tests/test_curated_knowledge_repo.py`
Purpose (per test_curated_knowledge.py's docstring): "scope-filtering behavior against real Postgres."
- L25 `test_empty_tags_entry_is_always_included_regardless_of_allowed_scopes` — no panel (`change` status)
- L37 `test_scoped_entry_only_returned_when_its_scope_is_allowed` — no panel
- L49 `test_inactive_entry_is_never_returned` — no panel
- L57 `test_cap_enforcement_limits_the_result_count` — no panel
- L66 `test_ordering_is_stable_by_id_for_deterministic_citation_numbering` — no panel
- L75 `test_two_differently_scoped_entries_never_cross_leak` — s-scope

### `app/features/confluence_sync/tests/test_versioning_rollback.py`
- L30 `test_rollback_restores_prior_version` — i4-rollback
- L53 `test_rollback_restores_page_source_hashes_and_pipeline_stamps` — i4-rollback
- L86 `test_rollback_then_unchanged_sync_reports_no_change` — i4-rollback
- L107 `test_rollback_then_real_newer_revision_is_detected_not_masked` — a rollback doesn't hide a genuinely newer Confluence revision from future syncs — i4-rollback

### `app/features/confluence_sync/tests/test_answer_workflow.py`
- L109 `test_answer_service_grounds_a_cited_answer_end_to_end` — r5-generate
- L139 `test_answer_service_refuses_when_source_scope_excludes_everything` — r4-refuse
- L160 `test_answer_service_refuses_when_generator_cites_nothing` — r5-nocite
- L180 `test_answer_service_small_talk_skips_retrieval_even_with_a_real_indexed_corpus` — r1-small

### `app/features/confluence_sync/tests/test_verify_isolation_script.py`
- L35 `test_verify_isolation_passes_and_runs_reader_readpath_checks` — cm-scripts
- L55 `test_verify_isolation_proves_scope_isolation_on_tagged_corpus` — cm-scripts, s-scope

### `app/features/confluence_sync/tests/test_knowledge_scope.py`
- L12 `test_recognized_label_becomes_a_tag` — i2-labels
- L19 `test_unrecognized_label_is_ignored` — i2-labels
- L26 `test_general_plus_one_provider_label_yields_both_tags_no_conflict` — i2-labels
- L33 `test_two_provider_labels_conflict_mews_and_opera_cloud` — tg-conflict
- L40 `test_two_provider_labels_conflict_mews_and_toast` — tg-conflict
- L49 `test_empty_labels_yield_empty_result` — i2-labels
- L56 `test_labels_are_trimmed_and_lowercased_before_matching` — i2-labels

### `app/features/confluence_sync/tests/test_ingestion_pipeline.py`
- L16 `test_children_have_embeddings_and_tsv` — i3-tsv
- L28 `test_keyword_tsv_is_queryable` — i3-tsv, vd-keyword
- L41 `test_version_upgrade_is_atomic_and_updates_content` — i4-swap
- L55 `test_only_one_document_version_active_after_reindex` — i4-swap
- L73 `test_reuse_guard_disables_on_config_change` — i3-embed
- L89 `test_schema_bump_triggers_full_reembed_release` — i3-embed
- L115 `test_label_driven_knowledge_scope_tag_unions_with_source_scope` — i2-labels
- L144 `test_conflicting_provider_labels_contribute_no_tag_and_log_conflict` — tg-conflict

### `app/features/confluence_sync/tests/test_event_dedup.py` — see above.

### `app/features/confluence_sync/tests/test_chat_endpoint.py`
- L102 `test_missing_api_key_is_rejected` — r1-auth
- L109 `test_unconfigured_api_key_fails_closed` — r1-auth
- L118 `test_previous_api_key_is_accepted_during_rotation_overlap` — r1-auth
- L134 `test_key_outside_current_and_previous_is_rejected` — r1-auth
- L145 `test_previous_key_stops_working_once_rotation_completes` — r1-auth
- L158 `test_history_must_end_on_user_turn` — r1-limits
- L169 `test_history_too_long_is_rejected` — r1-limits
- L177 `test_message_too_long_is_rejected` — r1-limits
- L188 `test_too_many_images_on_a_turn_is_rejected` — r1-limits
- L211 `test_oversized_image_is_rejected` — r1-limits
- L231 `test_image_within_caps_is_accepted_and_analysis_reaches_the_done_event` — r5-image
- L279 `test_tokenless_request_forwards_general_only_and_ignores_body_scope` — r1-ctx
- L301 `test_malformed_knowledge_scope_is_rejected` — an unknown body scope is a 400 before any search, per CLAUDE.md rule 2 — r1-limits
- L338 `test_idempotency_key_replay_with_different_field_is_not_the_first_callers_answer` (param `[history]`) — r1-idem
- L359 `test_numeric_principal_is_rejected_not_treated_as_space_wide_trust` — r1-ctx
- L376 `test_rate_limit_returns_429` — r1-limits
- L386 `test_rate_limit_is_keyed_by_ip_not_by_rotating_principal` — r1-limits
- L406 `test_idempotency_cache_evicts_the_oldest_key_once_max_entries_exceeded` — r1-idem
- L430 `test_grounded_answer_streams_start_token_citations_done` — r5-stream
- L461 `test_refusal_streams_done_with_refused_true` — r5-stream
- L507 `test_clarification_done_payload_never_leaks_internal_refusal_categories` — r1-clarify
- L574 `test_chat_request_log_includes_refusal_reason_when_refused` — s-audit
- L604 `test_chat_request_log_has_no_refusal_reason_when_not_refused` — s-audit
- L625 `test_idempotency_key_replays_cached_answer_without_rerunning` — r1-idem
- L644 `test_answer_cache_replays_without_rerunning_retrieval` — no panel (answer cache)
- L661 `test_answer_cache_does_not_cross_token_subject_boundary` — no panel
- L686 `test_create_app_wires_the_answer_cache_by_default` — cm-root
- L694 `test_feedback_updates_trace_row` — r5-feedback
- L716 `test_feedback_requires_auth` — r5-feedback
- L723 `test_feedback_rejects_invalid_value` — r5-feedback

### `app/features/confluence_sync/tests/test_reconciliation.py`
- L37 `test_complete_reconcile_deactivates_orphan_and_enqueues_new` — i1-sweep, d-reconciliation_run
- L55 `test_lightweight_reconcile_repairs_version_drift` — i1-sweep
- L72 `test_page_root_scopes_reconciliation_to_its_subtree_and_tags_it` — i1-sweep
- L100 `test_deactivating_root_purges_previously_synced_now_uncovered_pages` — i1-sweep

### `app/features/confluence_sync/tests/test_scope_resolver.py`
- L53 `test_page_root_resolves_to_self_and_descendants_only` — d-source_scope
- L59 `test_page_root_never_includes_siblings_or_ancestors` — d-source_scope
- L67 `test_space_root_resolves_to_every_live_page` — d-source_scope
- L73 `test_page_root_missing_from_live_listing_resolves_to_empty` — d-source_scope
- L79 `test_overlapping_page_roots_resolve_independently` — d-source_scope
- L87 `test_no_roots_is_unrestricted_and_untagged` — d-source_scope
- L93 `test_only_page_roots_restricts_to_their_union` — d-source_scope
- L102 `test_overlapping_roots_union_tags_on_shared_pages` — d-source_scope
- L112 `test_space_root_present_covers_everything_even_with_page_roots_on_top` — d-source_scope
- L124 `test_page_outside_every_root_resolves_to_nothing` — d-source_scope
- L132 `test_deactivating_the_last_root_purges_rather_than_reverting_to_unrestricted` — d-source_scope
- L139 `test_inactive_roots_do_not_contribute_coverage_or_tags_alongside_active_ones` — d-source_scope

### `app/features/confluence_sync/tests/test_reader_vector_access.py`
- L26 `test_reader_can_run_dense_halfvec_query` — vd-rls, vd-hnsw
- L38 `test_ensure_reader_role_grants_extensions_usage_when_schema_exists` — s-reader
- L64 `test_ensure_reader_role_no_extensions_schema_is_a_noop_for_extensions` — s-reader

### `app/features/confluence_sync/tests/test_customer_isolation_backstop.py`
- L56 `test_scope_rls_blocks_cross_customer_read_via_guc_alone` — s-scope
- L76 `test_scope_rls_fails_closed_when_scope_guc_unset` — an unset scope GUC fails closed, denies everything — s-scope
- L90 `test_scope_rls_wildcard_is_an_explicit_opt_out` — s-scope
- L104 `test_scope_rls_untagged_chunk_is_global_visible_under_any_scope` — s-scope
- L151 `test_curated_scope_rls_isolates_tagged_entries_but_keeps_global` — s-scope

### `app/features/confluence_sync/tests/test_fallback_eval.py`
- L57 `test_ambiguity_dataset_cases_trigger_clarification_end_to_end` — r1-clarify
- L93 `test_out_of_corpus_case_refuses_not_clarifies_or_hallucinates` — r4-refuse
- L131 `test_citation_grounding_rate_on_a_real_grounded_answer` — e-stage4

### `app/features/confluence_sync/tests/test_worker_sync.py`
- L23 `test_first_index_creates_active_version_and_chunks` — i4-swap
- L36 `test_content_change_swaps_version_atomically` — i4-swap, vd-swap
- L55 `test_contextualization_version_bump_rebuilds_at_same_cf_version` — i2-rebuild
- L81 `test_version_guard_drops_stale_update` — i1-handle
- L94 `test_first_index_persists_restrictions` — d-page_restriction
- L109 `test_permission_change_is_metadata_only` — i2-meta
- L128 `test_dropped_restriction_leaves_page_unrestricted` — i2-inplace
- L141 `test_delete_deactivates_page` — i2-gone
- L154 `test_delete_marks_the_active_version_superseded` — i2-gone

### `app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py`
- L49 `test_flag_off_still_enforces_scope_via_rls_backstop` — r3-scope
- L65 `test_no_knowledge_scopes_argument_is_unrestricted` — r3-scope
- L79 `test_flag_on_excludes_page_tagged_for_a_different_scope` — r3-scope
- L95 `test_flag_on_includes_page_when_its_scope_is_allowed` — r3-scope
- L107 `test_flag_on_two_scopes_never_cross_leak` — r3-deny
- L125 `test_flag_on_chunk_with_no_knowledge_scope_tag_never_participates` — r3-scope
- L139 `test_query_trace_records_allowed_knowledge_scopes` — r3-scope
- L155 `test_gin_index_is_plan_usable_for_tags_overlap` — r2-indexes

### `app/features/confluence_sync/tests/test_attachment_wiring.py`
- L24 `test_text_attachment_content_is_indexed_and_searchable` — i3-attach
- L36 `test_markdown_attachment_content_is_indexed` — i3-attach
- L44 `test_placeholder_pdf_and_xlsx_degrade_to_no_chunk_not_a_crash` — i3-attach
- L58 `test_attachment_chunks_inherit_page_acl_and_source` — i3-attach, r3-acl
- L70 `test_resyncing_unchanged_page_is_a_true_no_change_not_a_spurious_rebuild` — i2-nochange
- L86 `test_unchanged_attachment_reuses_embedding_across_a_body_driven_rebuild` — i3-embed
- L103 `test_oversized_attachment_metadata_is_skipped_before_download` — i3-attach
- L113 `test_unfetchable_attachment_is_skipped_not_a_sync_failure` — i3-attach
- L129 `test_attachment_only_change_is_metadata_only_disclosed_limitation` — i2-meta

### `app/features/confluence_sync/tests/test_force_rls_managed_postgres.py`
- L41 `test_non_superuser_owner_reads_own_rows` — s-writer
- L67 `test_non_owner_reader_still_isolated` — s-reader

### `app/features/confluence_sync/tests/test_retrieval_eval.py`
Purpose (L1-L11): end-to-end retrieval quality over the fixture corpus vs. a manifest-order baseline. Uses `app.features.evaluation.evaluate`/`load_dataset` inside the real-Postgres harness — closest thing in pytest to the `make eval` gold-set runner, though it runs via pytest not the standalone `run_baseline` script (see level note at file top).
- L87 `test_smoke_maintains_recall_and_beats_ranking` — e-stage1
- L100 `test_permission_no_leak_and_authorized_access` — s-permitted
- L131 `test_permission_enforcement_is_db_backed_not_fixture_fed` — r3-torerank
- L160 `test_rls_default_deny_on_reader_role` — s-reader
- L178 `test_retriever_wrong_source_scope_returns_zero` — r3-source
- L197 `test_retrieval_writes_one_query_trace_row` — d-query_trace
- L232 `test_retrieve_with_context_surfaces_chunk_ids_scores_and_parent_text` — r5-parents (`change` status, no `built` panel)
- L272 `test_retrieve_with_context_empty_on_no_hits` — r2-dense
- L289 `test_update_query_trace_answer_and_feedback` — d-query_trace
- L331 `test_rerank_lift_before_vs_after` — e-stage2

### `app/features/confluence_sync/tests/test_router_auth_context.py`
- L64 `test_token_integration_drives_scopes` — r1-ctx
- L72 `test_body_scope_disagreeing_with_token_is_ignored` — a body scope that disagrees with the token is ignored and logged, per CLAUDE.md rule 2 — r1-ctx
- L81 `test_unknown_body_scope_is_400_before_search` — r1-limits
- L89 `test_unknown_integration_is_401` — r1-ctx
- L96 `test_tokenless_request_is_general_only` — r1-ctx
- L105 `test_bad_token_is_401_before_search` — r1-auth

## `tests/tools/` — level: unit (meta/tooling tests for the auditor's own tools — the PreToolUse guard hook and the design-panel CLI — not a stage of the Obi RAG design; confirmed via `python3 apps/automation/tools/panel.py --grep guard`, `--grep "design panel"`, `--grep subagent`, none of which return a panel describing this tooling)

### `tests/tools/test_agent_guard.py`
Purpose (docstring L1-L6): drives `tools/agent_guard.py` (the PreToolUse guard for Obi subagents) as a subprocess with a JSON payload on stdin, exactly as the hook runs; hermetic, no network, no sleep. The implementer marker is created/removed inside a tmp cwd so nothing leaks.
- L54 `test_guard_rejects_unknown_profile` — an unrecognized profile name blocks (exit 2) rather than defaulting open — no panel
- L58 `test_auditor_read_only_shell_allowed` — auditor may run `ls`, `git log --oneline`, and the panel reader (`panel.py --list`) — no panel
- L64 `test_auditor_allows_read_only_pytest` — auditor may run `pytest --collect-only -q` and a plain `pytest -q` (both read-only, needed by this very substep) — no panel
- L70 `test_auditor_blocks_mutating_shell` — auditor is blocked from `git status` and `rm -rf docs` — no panel
- L75 `test_auditor_write_scoped_to_final_docs` — Write is allowed only under `docs/Final_docs/`; a path outside it blocks, and Edit is blocked everywhere for the auditor profile — no panel
- L81 `test_auditor_write_check_is_cwd_independent` — the `docs/Final_docs/` allow-list check is anchored to `CLAUDE_PROJECT_DIR`, not the process's cwd, so it gives the same answer no matter where the hook is invoked from — no panel
- L93 `test_auditor_blocks_redirect_even_to_allowed_dir` — `echo > file` and `echo | tee file` are blocked even when the target path is under the allowed `docs/Final_docs/` — no panel
- L98 `test_auditor_checks_every_chained_part` — a `&&`-chained command (`git log && git status`) is blocked as a whole because one chained part is disallowed — no panel
- L103 `test_tester_allows_test_runners_blocks_writes` — tester may run `make check`/`uv run pytest -q`/`git diff` but Write and Edit are always blocked, and mutating shell (`rm -rf`) is blocked too — no panel
- L112 `test_implementer_gated_on_marker` — implementer's Write/Edit are blocked until `.obi/active-substep` exists in the cwd, then allowed once the marker file is created; Bash stays unrestricted throughout — no panel
- L125 `test_none_profile_is_passthrough` — the `none` profile allows Write, Bash and Edit unconditionally (the safe default for an ungated session) — no panel

### `tests/tools/test_panel.py`
Purpose (docstring L1-L7): drives `tools/panel.py` (the design-panel reader/updater used throughout this very audit) as a subprocess against a synthetic HTML fixture written to a tmp dir; no network, no sleep, no real design file touched.
- L74 `test_panel_print_returns_only_that_panel` — printing one id renders that panel's title and id, and nothing from a sibling panel leaks into the output — no panel
- L86 `test_panel_list_one_line_per_panel` — `--list` prints exactly one `id | title | status` line per panel, one line per fixture panel, covering every id — no panel
- L98 `test_panel_grep_prints_matching_ids_only` — `--grep` prints only the ids whose panel text mentions the search word, and prints nothing for a word that matches none — no panel
- L112 `test_panel_update_changes_two_fields_and_leaves_the_rest_identical` — `--status` and `--today` together rewrite exactly those two fields on the named panel; every byte of the file outside the JSON block, and every field on every other panel, is byte-identical before and after — no panel
- L148 `test_panel_status_only_leaves_today_untouched` — `--status` given alone changes only the status word; the `today` line is untouched — no panel
- L158 `test_panel_unknown_id_fails` — an unknown panel id is a hard error (non-zero exit, the bad id named in stderr) for both printing and updating, never a silent no-op — no panel
- L169 `test_panel_rejects_unknown_status_word` — `--status` only accepts the five defined status words (`built|change|build|unverified|discuss`); any other value errors with that value named in stderr — no panel

---

# Frontend (`apps/web`, vitest + jsdom) — level: component test, jsdom, not a live browser

**Tooling gap:** `apps/web/package.json:9` defines `"test": "vitest run"`. There is no Playwright config anywhere in the repo (`find . -iname "playwright.config*"` → empty) and no `test:e2e` script. CLAUDE.md's test-level table defines **browser** as "Playwright against a stub host page" — that suite does not exist today; what exists is a vitest+jsdom component-test suite. Counted here under its own heading rather than folded into "browser," since jsdom is not a real browser and this is a drift from the documented test level, not a match to it. The auditor's Bash allow-list has no `pnpm` entry, so these counts are static (grep of `it(`/`test(`/`it.each(`), not verified by running vitest.

## `src/app/test-hosts/`
### `multi-user-content.test.tsx` (4 tests)
- L13 "offers exactly the three business users and never the tokenless 'none' host" — sc-user
- L22 "always shows the currently active user's company and integration" — sc-user
- L30 "switching to a random user changes the active user to a different one" — sc-user
- L39 "an explicit per-user button switches the active user to that user" — sc-user

### `test-host-content.test.tsx` (3 declarations: 1 `it` + 2 `it.each` of 4 params each = 9 runtime cases)
- L16 "marks <html> with suppressHydrationWarning to match the sibling root layouts" — no panel
- L32 `it.each(["none","mews","toast","opera-cloud"])` "builds the per-name token endpoint for %s" — em-token
- L38 `it.each(...)` (second block, same 4 params) — em-token

## `src/features/embed/tests/`
### `frame-csp.test.ts` (8 tests)
- L47 "includes every active domain and never emits a wildcard" — em-button
- L54 "renders frame-ancestors 'none' (not a wildcard) when tolerated locally with no active domains" — em-button
- L60 "fails closed (ok: false) when no active domains exist outside local/dev" — em-button
- L67 "returns the sorted, de-duplicated domains of active entries only" — em-button
- L79 "returns an empty list for a missing/malformed file" — em-button
- L97 "sets frame-ancestors with the active domains and no wildcard on a normal request" — em-button
- L110 "responds 403 when there are no active domains outside local/dev" — em-button
- L120 "fails toward 403 (never allow-all) when the internal active-domains fetch itself fails" — em-button
- L132 "returns the active domains computed from the current platforms file" — em-button, cm-config

### `iframe-bridge.test.ts` (9 tests)
- L32 "sets the token from obi:token when the origin is allowed and the source is the parent" — w-token
- L41 "ignores obi:token from a disallowed origin, warns once, and leaves the token null" — w-token
- L50 "ignores a message whose source is not window.parent, even from an allowed origin" — w-token
- L59 "drops the token on obi:clear" — w-token
- L69 "invokes onToken/onClear callbacks" — w-token
- L81 "invokes onOpen on obi:open without setting a token (the message carries no data)" — w-launcher
- L90 "does not invoke onOpen for an obi:open from a disallowed origin" — w-launcher
- L100 "resets to null token on re-init (a fresh frame load never carries a stale token)" — w-token
- L112 "never reads any web storage API" — the token bridge never touches localStorage/sessionStorage, per CLAUDE.md rule 10 — w-token

### `loader.test.ts` (9 tests)
- L40 "Obi.init injects exactly one iframe pointed at the embed origin's /embed route" — em-loader
- L49 "injects the two-tone sparkle 'star' launcher (not a plain text button), matching ChatLauncher" — w-launcher
- L67 "toggles: a second launcher click hides the iframe without clearing the token or re-fetching" — w-launcher
- L92 "posts obi:token to the exact OBI_ORIGIN (never '*') after a launcher click fetches the token" — w-token
- L123 "Obi.clear() posts obi:clear to the exact OBI_ORIGIN" — w-token
- L136 "schedules a silent renewal before the token's exp" — em-token
- L166 "retries the token-endpoint fetch once on a 401 from the platform's own server" — em-hostbackend
- L180 "Obi.destroy() removes the launcher and iframe so no widget is left in the DOM" — em-loader
- L192 "re-init points at a new tokenUrl without leaking a second launcher/iframe (user switch)" — em-loader

## `src/features/chat/tests/`
### `assistant-mark.test.tsx` (2)
- L6 "renders as a decorative SVG hidden from assistive tech" — w-render
- L13 "sizes the SVG from the size prop" — w-render

### `attachment-strip.test.tsx` (4)
- L9 "renders nothing when there are no attachments" — w-composer
- L14 "renders a thumbnail per attachment and calls onRemove with its id" — w-composer
- L30 "opens a full-size lightbox on thumbnail click and closes it on Escape" — w-composer
- L49 "closes the lightbox via its close button without removing the attachment" — w-composer

### `chat-client.test.ts` (13)
- L54 "attaches the Authorization bearer header when a token is present" — w-token
- L64 "omits the Authorization header when no token is present" — w-token
- L74 "dispatches start/token/citations/done in order from a single chunk" — r5-stream
- L111 "reassembles an event whose \n\n separator is split across chunks" — r5-stream
- L124 "reports a mid-stream error event through onError without throwing" — r5-stream
- L136 "throws ChatRequestError when the response is not ok" — no panel
- L146 "throws ChatRequestError when fetch itself rejects" — no panel
- L154 "notifies onUnauthorized listeners exactly once on a 401, and not on other error statuses" — w-token
- L171 "stops notifying an unsubscribed onUnauthorized listener" — no panel
- L197 "resolves with the backend body on success" (feedback call) — r5-feedback
- L209 "attaches the Authorization bearer header when a token is present" (feedback call) — w-token
- L219 "omits the Authorization header when no token is present" (feedback call) — w-token
- L229 "throws ChatRequestError on a non-ok response" (feedback call) — r5-feedback

### `chat-launcher.test.tsx` (2)
- L18 "calls onOpen when clicked" — w-launcher
- L25 "only animates the pulse while a teaser is visible" — w-launcher

### `chat-session-provider.test.tsx` (9)
- L74 "surfaces the backend's error message on a rejected (401) request" — w-token
- L100 "clears messages and pending state" — w-panel
- L123 "aborts an in-flight stream instead of letting it resurrect the cleared thread" — r5-stream
- L147 "sends the configured knowledgeScope on the outgoing request" — w-scope
- L171 "applies a runtime scope change (the PLAN 10.8 switcher) to the next outgoing request" — w-scope
- L210 "omits knowledgeScope from the outgoing request when not configured" — w-scope
- L234 "attaches images to the newest history turn only, and reads imageAnalysis back off done" — r5-image
- L292 "marks a turn as clarifying (not refused) and keeps its options, per ADR-0008 decision 3" — r1-clarify
- L332 "resends a clarifying turn's question as history on the next message" — r1-clarify

### `chat-widget.test.tsx` (5)
- L18 "renders only the closed launcher initially, no panel" — w-launcher
- L24 "opens the panel when the launcher is clicked" — w-panel
- L32 "closing the panel (via the header's Close icon) returns to the launcher" — w-panel
- L45 "shows the teaser 3000ms after mount if still closed, and it opens the panel" — w-launcher
- L55 "dismissing the teaser hides it without opening the panel" — w-launcher

### `composer.test.tsx` (13)
- L18 "sends the trimmed message and clears the box on Enter" — w-composer
- L29 "inserts a newline on Shift+Enter instead of sending" — w-composer
- L42 "does not send whitespace-only input" — w-composer
- L52 "sends via the Send button and disables it while empty" — w-composer
- L67 "renders the footer disclaimer" — w-composer
- L74 "disables the box, Send, and Attach buttons while a request is pending" — w-composer
- L86 "previews an image selected via the file picker and enables Send with no text" — w-composer
- L99 "previews a pasted image" — w-composer
- L113 "removes an attachment via its remove button" — w-composer
- L124 "caps attachments at 4 and ignores extras" — w-composer
- L136 "shows the PII disclosure while an image is staged, and clears it once removed" — w-composer
- L149 "sends a base64-encoded image attachment with empty text when there is no text" — w-composer
- L176 "sends both the text and the image attachment when both are present" — w-composer

### `icon-button.test.tsx` (3)
- L7 "renders its children and fires onClick" — w-panel
- L19 "reflects the active prop as aria-pressed" — w-panel
- L24 "does not fire onClick while disabled" — w-panel

### `knowledge-scopes.test.ts` (2)
- L25 "mirrors config/knowledge_scopes.json's scope names in order (no drift)" — cm-config, w-scope
- L32 "always includes obi-general-test — the always-present base scope (ADR-0011)" — cm-config

### `language-menu.test.tsx` (2)
- L9 "renders all six locales with English checked" — w-i18n
- L17 "calls onSelect with the picked locale and closes, without touching the active one" — w-i18n

### `menu-item.test.tsx` (4) / `menu.test.tsx` (3) — no panel (generic menu chrome; covered under w-panel)
- `menu-item.test.tsx` L9, L16, L30, L35 — w-panel
- `menu.test.tsx` L9, L18, L28 — w-panel

### `message-bubble.test.tsx` (21)
- L19 "renders a user message in a filled, right-aligned bubble" — w-render
- L25 "renders an assistant message as plain text with no bubble fill" — w-render
- L32 "shows the typing indicator instead of text while streaming with nothing received yet" — w-render
- L38 "shows the refusal banner and a mailto hand-off CTA for a refused turn" — r4-refuse
- L49 "renders no hand-off CTA on a non-refused turn" — r4-refuse
- L54 "keeps the banner + CTA for a hand-off refusal reason (weak_score)" — r4-weak
- L64 "shows NO banner and NO hand-off CTA for an off_topic redirect — just the softer body" — r4-refuse
- L87 "shows a distinct clarifying banner, not the refusal banner" — r1-clarify
- L97 "renders a quick-reply chip per clarification option and sends it on click" — r1-clarify
- L132 "renders no chips when the turn has no clarification options" — r1-clarify
- L141 "never shows feedback controls on a clarifying turn (no trace row is written)" — r1-clarify
- L151 "renders citation links when a url is present" — w-render
- L162 "renders an unavailable-source badge when a citation has no url" — w-render
- L173 "shows thumbs feedback controls for a complete turn with a traceId" — r5-feedback
- L185 "reflects a previously-submitted rating" — r5-feedback
- L190 "hides feedback controls while streaming (no traceId yet)" — r5-feedback
- L195 "never shows feedback controls for the user's own messages" — r5-feedback
- L201 "renders a user turn's attached images and opens a lightbox on click" — w-render
- L218 "does not render an empty bubble for an image-only turn with no text" — w-render
- L232 "renders a labeled vision-analysis block for an assistant turn that has one" — r5-image
- L249 "renders no vision-analysis block when the turn has none" — r5-image

### `message-list.test.tsx` (4)
- L19 "shows the resolved greeting with the product name bold, and no suggestion chip" — w-render
- L31 "renders all three empty-state example-query chips and sends the clicked one" — w-render
- L45 "renders each message via MessageBubble" — w-render
- L56 "forwards feedback clicks to onFeedback with the message id and trace id" — r5-feedback

### `panel-body.test.tsx` (7)
- L72 "streams an answer and renders the final text" — r5-stream
- L89 "renders citation links returned with the done event" — r5-stream
- L110 "shows a refusal indicator when the pipeline refuses" — r4-refuse
- L124 "surfaces a request error without crashing" — no panel
- L133 "sends feedback for the correct trace id and value" — r5-feedback
- L160 "restart (via the header's More menu) genuinely clears the thread" — w-panel
- L180 "aborts the in-flight stream when unmounted" — r5-stream

### `panel-header.test.tsx` (9)
- L18 "shows the assistant name, defaulting to Obi" — w-panel
- L23 "omits the close button when no onClose is given (page variant)" — w-panel
- L28 "shows and wires the close button when onClose is given (widget variant)" — w-panel
- L35 "opening one menu closes the other (mutually exclusive)" — w-panel
- L45 "renders docs/support as disabled stubs and wires restart to the real handler" — w-panel
- L64 "closes the open menu on outside click" — w-panel
- L77 "is hidden unless NEXT_PUBLIC_SHOW_SCOPE_SWITCHER is set" — w-scope
- L82 "shows the switcher and applies a picked scope back into the session" — w-scope
- L97 "opening the scope menu closes the other menus (mutually exclusive)" — w-scope

### `route-handlers.test.ts` (14)
- L48 "rejects malformed JSON before calling the backend" — w-proxy
- L59 "rejects a request missing history before calling the backend" — w-proxy
- L65 "fails closed with 503 when the automation API is unconfigured" — w-proxy
- L76 "translates the request, forwards the idempotency header, and streams the backend body through" — w-proxy, r1-idem
- L107 "forwards knowledgeScope unmodified as knowledge_scope" — w-scope
- L122 "forwards the backend's error status and body verbatim" — w-proxy
- L133 "returns 502 when the upstream call itself fails" — w-proxy
- L141 "does not 413 a legitimate image-bearing turn within the backend's own image caps" — w-proxy
- L156 "still rejects a pathologically oversized body with 413 before calling the backend" — w-proxy
- L172 "threads a Bearer Authorization header through to callAutomationApi as userToken" — w-token
- L187 "passes no userToken when the request carries no Authorization header" — w-token
- L199 "rejects an invalid feedback value before calling the backend" — r5-feedback
- L205 "fails closed with 503 when the automation API is unconfigured" (feedback route) — w-proxy
- L215 "forwards to the backend with an encoded traceId and a shortened timeout" — r5-feedback

### `scope-menu.test.tsx` (3)
- L9 "renders all four recognized scopes with the active one checked" — w-scope
- L17 "calls onSelect with the picked scope name and closes" — w-scope
- L26 "checks nothing when no scope is active (embed default)" — w-scope

### `teaser-popup.test.tsx` (2)
- L18 "opens the panel when the card itself is clicked" — w-launcher
- L25 "dismissing never also opens the panel" — w-launcher

### `typing-indicator.test.tsx` (3)
- L19 "renders an initial word from the thinking-word bank with an ellipsis" — w-render
- L24 "cycles to a different word every 3800ms" — w-render
- L36 "stops cycling once unmounted (no interval leak)" — w-render

### `use-widget-visibility.test.tsx` (6)
- L9 "starts closed with no teaser" — w-launcher
- L15 "shows the teaser 3000ms after mount if still closed" — w-launcher
- L25 "never shows the initial teaser if the widget is opened first" — w-launcher
- L34 "openWidget opens the panel and hides any visible teaser" — w-launcher
- L44 "closeWidget reschedules the teaser after 20000ms" — w-launcher
- L57 "dismissTeaser hides it and reschedules after 20000ms, without opening the panel" — w-launcher

### `validation.test.ts` (13 declarations; 3 are `it.each` expanding to 4+2+6=12 extra runtime cases)
- L5 "accepts a well-formed request and passes fields through unchanged" — r1-limits
- L21 "accepts a minimal request with only history" — r1-limits
- L26 `it.each([null, undefined, "string", 42])` "rejects a non-object body: %s" — r1-limits
- L33 "rejects a missing history field" — r1-limits
- L40 "rejects an empty history array" — r1-limits
- L47 "rejects history longer than the resource-exhaustion ceiling" — r1-limits
- L59 "rejects a turn with an invalid role" — r1-limits
- L64 "accepts a turn with empty content and no images (the backend has no min_length either)" — r1-limits
- L69 "accepts an image-only turn with empty content (ADR-0009 decision 4)" — r5-image
- L78 "accepts a resent history where an older, no-longer-newest image-only turn has aged out to empty content and no images (PLAN 7.8 bug E)" — r5-image
- L97 "rejects history that does not end on a user turn" — r1-limits
- L107 "rejects a non-string conversationId" — r1-limits
- L115 "rejects a non-string principal" — r1-limits
- L125 `it.each([-1, 1])` "accepts feedback value %d" — r5-feedback
- L129 `it.each([0, 2, -2, "1", null, undefined])` "rejects invalid feedback value: %s" — r5-feedback
- L136 "rejects a non-object body" — r1-limits

---

# Tests that fail today

`uv run pytest -q` (from `apps/automation`): **53 failed, 561 passed, 2 warnings, 3 errors in 368.26s**. Every failure is inside a **db-level** file (no unit-level test failed). Root cause, confirmed live during this run (see "Environment finding" above): the root `.env`'s `DATABASE_URL` resolves to a Supabase pooler host, not the local `make up` Postgres on `:5434`; connections fail with `psycopg.OperationalError: ... FATAL: (ENOIDENTIFIER) no tenant identifier provided`. This is an environment/config problem, not a code regression — flagged for the ledger under "need from you" (a local `DATABASE_URL` override for the test run), not fixed here (auditor is read-only).

Failing tests (grouped by file; reason is the same connection failure unless noted):

- `test_answer_workflow.py`: `test_answer_service_grounds_a_cited_answer_end_to_end`, `test_answer_service_refuses_when_source_scope_excludes_everything`, `test_answer_service_refuses_when_generator_cites_nothing` — Supabase pooler connection failure
- `test_chat_endpoint.py`: `test_image_within_caps_is_accepted_and_analysis_reaches_the_done_event`, `test_idempotency_key_replay_with_different_field_is_not_the_first_callers_answer[history]`, `test_idempotency_cache_evicts_the_oldest_key_once_max_entries_exceeded`, `test_grounded_answer_streams_start_token_citations_done`, `test_refusal_streams_done_with_refused_true`, `test_chat_request_log_includes_refusal_reason_when_refused`, `test_chat_request_log_has_no_refusal_reason_when_not_refused`, `test_idempotency_key_replays_cached_answer_without_rerunning`, `test_answer_cache_replays_without_rerunning_retrieval`, `test_answer_cache_does_not_cross_token_subject_boundary`, `test_feedback_updates_trace_row` — same
- `test_customer_isolation_backstop.py`: all 5 tests — same
- `test_fallback_eval.py`: `test_out_of_corpus_case_refuses_not_clarifies_or_hallucinates`, `test_citation_grounding_rate_on_a_real_grounded_answer` — same
- `test_force_rls_managed_postgres.py`: both tests — same
- `test_reader_rls_reconcile.py`: `test_reader_freed_but_anon_stays_denied`, `test_apply_reader_rls_leaves_chunk_source_isolation_intact` — same
- `test_reader_vector_access.py`: `test_reader_can_run_dense_halfvec_query` — same
- `test_retrieval_eval.py`: all 10 tests — same
- `test_retrieval_knowledge_scope.py`: 7 of 8 tests (all but `test_gin_index_is_plan_usable_for_tags_overlap`) — same
- `test_verify_isolation_script.py`: both tests — same
- `test_worker_sync.py`: `test_delete_marks_the_active_version_superseded` — same
- `test_migration_0007_knowledge_scope.py`, `test_migration_0009_reader_rls_reconcile.py`, `test_migration_0010_scope_rls.py`, `test_migration_0011_subject_hash.py`: all 7 tests — same connection failure, plus
- 3 **ERRORs** (teardown/setup of `test_0009_downgrade_then_upgrade_round_trips`, `test_0010_adds_restrictive_scope_policies`, `test_0010_downgrade_then_upgrade_round_trips`) — the migration fixture's `_drop_database` step fails with `psycopg.errors.ObjectInUse: database "..." is being accessed by other users`, a cascading side effect of the same root-cause connection instability against the remote pooler, not a distinct bug.

Frontend (`apps/web`, vitest): **not run** — `pnpm` is not in the auditor's Bash allow-list (`apps/automation/tools/agent_guard.py:44-53`, tester profile only). No pass/fail data available for this audit; say so rather than guess.

`tests/tools/` (test_agent_guard.py, test_panel.py): included in the `uv run pytest -q` run above; all 18 of their tests are in the **561 passed**, none failed.

---

# Implemented panels with no test today

23 of the 101 `built`-status panels have no test citing them anywhere above:

| panel | title | checks the panel names ("## Tests" section) |
|---|---|---|
| `cm-docs` | docs/adr: the decisions of record | (no "Tests" section — documentation, not code) |
| `cm-tokens` | packages/design-tokens | (no "Tests" section found; not imported by any cataloged test) |
| `cm-infra` | infra/foundation: local Postgres | (no "Tests" section; `make up`/docker compose is not exercised by any test) |
| `i2-tobuild` | On to ingestion stage 3 | no dedicated test for the stage-2→3 handoff decision point itself (only exercised implicitly inside full-pipeline `test_worker_sync.py` runs) |
| `i3-blocks` | Normalize HTML into blocks | no `test_normalize*`/`test_blocks*` file exists; only attachment-specific block conversion is tested (`test_attachment_extraction.py`), not general page-HTML normalization |
| `i4-document` | Ensure the document row | no test asserts the `document` row is created/reused independently of a full sync test |
| `i4-chunks` | Insert the chunks inactive | no test isolates the "insert inactive, not yet visible" step from the swap itself |
| `i4-gate` | Validation gate | no test isolates the pre-swap validation gate from the swap tests |
| `i4-failed` | A failed version never activates | no test simulates a failed build and asserts the version never activates |
| `i4-gc` | Garbage collect old versions | no `test_gc*`/garbage-collection test found anywhere in the suite |
| `tg-add` | Add a label | no test simulates adding a label mid-lifecycle distinct from initial classification |
| `tg-change` | Change a label | no test simulates changing an existing label |
| `tg-retag` | Tags updated without a re-embed | no test isolates a tag-only update that explicitly asserts no re-embed happened |
| `r1-short` | A short reply without search | not distinguished from `r1-small` (small talk) in any test name or body |
| `r2-indexes` | The two search indexes | only the GIN tags index is directly tested (`test_gin_index_is_plan_usable_for_tags_overlap`); no test asserts both the tsv and HNSW indexes together as "the two search indexes" |
| `r4-proceed` | Top-k children move on to stage 5 | no test isolates this hand-off point from the surrounding rerank/generate tests |
| `w-screenshot` | Screenshot of the page behind the widget | no test file for screenshot capture exists under `apps/web/src/features/chat/tests/` despite `html-to-image` being a dependency (`apps/web/package.json`) |
| `d-document` | document (table) | no test asserts the `document` table's shape/constraints directly (only via full-pipeline side effects) |
| `vd-column` | chunk.embedding | no test asserts the embedding column's type/dimension directly |
| `vd-nearest` | The nearest 75 | no test asserts the top-N=75 candidate count specifically |
| `vd-question` | The question vector | not distinguished from generic embedding-client tests (`test_embeddings_client.py` tests the provider generically, not "the question" specifically) |
| `sc-frontend` | One frontend | architectural/boundary claim; enforced (if at all) by `make boundaries`, not by a pytest/vitest test |
| `sc-backend` | One backend | same — architectural claim, no test |

---

# Report-back summary (for the launching agent)

- **Counts:** 71 backend test files, 614 backend test functions (verified via `uv run pytest --collect-only -q`), 101 Implemented (`built`) panels (verified via `python3 tools/panel.py --list`), 23 Implemented panels with no test.
- **Uncovered-panels list length:** 23 (table above).
- **Three least-confident panel matches** (kept in the doc but flagged here as genuinely ambiguous rather than a clean fit):
  1. `i1-handle` ("Handle and complete in one transaction") cited for `test_worker_sync.py::test_version_guard_drops_stale_update` — the test is really about the stale-update guard, and only touches "handle and complete in one transaction" as a side effect.
  2. `ks-index` ("Pages go in") cited for `test_knowledge_scope_backfill.py` — that file tests the readiness-gate *counting* logic, not the indexing decision itself; the fit is via `cm-scripts` primarily, `ks-index` secondarily and weakly.
  3. `r2-embed`/`vd-question` ("Embed the question" / "The question vector") considered for `test_embeddings_client.py` — that file tests the embeddings client generically (used for both chunks and questions); nothing in it is question-specific, so `r2-embed` is a loose citation and `vd-question` was ultimately left uncited (listed as no-test).
- **Ambiguity flagged explicitly in the doc, not guessed:** the "Implemented" ↔ `built` status-word mapping (no panel or doc literally equates the two); the frontend test level ("browser" per CLAUDE.md vs. the vitest+jsdom suite that actually exists — no Playwright suite exists in this repo); and the root cause of the 53 pytest failures (DATABASE_URL pointing at a Supabase pooler instead of local Postgres — confirmed live, not guessed, via the actual `ENOIDENTIFIER` exception text and the `.env` file's host value).
- **Follow-up addressed:** added the missing `tests/tools/` section (`test_agent_guard.py`, 11 tests; `test_panel.py`, 7 tests — 18 total, all already inside the 71-file/614-function top-line counts). Confirmed via `panel.py --grep guard`/`"design panel"`/`subagent` that none of the 192 panels describe this meta-tooling, so all 18 are cited "no panel." None of them protects a currently-uncovered panel, so the 23-panel uncovered list, its table, and the top-line counts are unchanged from the previous version of this document.
