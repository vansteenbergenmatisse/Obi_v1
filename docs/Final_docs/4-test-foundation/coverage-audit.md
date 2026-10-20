# 4.2 · Coverage audit — every contract mapped to a test, and the gaps

> **Note (2026-10-20).** This is a record of what ran at the time; results are unchanged. Since then
> the knowledge-scope `-test` tag axis it mentions (`obi-general-test`, `obi-mews-test`, …,
> `app.allowed_knowledge_scopes`) was retired by ADR-routing-labels-sole-content-axis — routing
> labels are the only content axis — and the `apps/automation`, `apps/web` and `infra/foundation`
> folders were renamed to `backend/`, `frontend/` and `knowledge-base/local/`.

Date: 2026-10-05 · substep 4.2 (roadmap Step 4, sync-rules §15.2 golf 1) · four read-only
obi-auditor passes (sync+events · authorization context · RLS/isolation · cache/limits), each
mapping its contracts to the existing tests with file:line evidence. This file is the distilled,
self-contained record: the verdict per contract, the gap list the second half of 4.2 closes
red-first, and what was deliberately deferred. Baselines this work is measured against:
`docs/plan/baseline.md` (4.1).

**Headline:** no audited contract is entirely untested. The suite's floor is strong — all 8 sync
rules, event dedup, the f8098d0 idempotency keys, the webhook gate, token verification order,
cache-key isolation on every axis, rate-limit bucketing, and the RLS fail-closed scope axis all
have direct tests. The gaps are narrow, specific scenarios — mostly adversarial variants — listed
as G1–G19 below.

## Verdict maps (condensed; verdicts are COVERED unless marked)

### 1 · Sync rules + events (auditor 1)

| Contract | Proof | Note |
|---|---|---|
| Rule 1 delete→purge, 1b restore→rebuild | `test_sync_rules_delete.py::test_in2_delete_page_removes_rows`, `::test_in2_delete_then_restore_full_rebuilds` | gap G1: no-op on never-indexed page untested |
| Rule 2 last label→purge | `test_sync_rules_membership.py::test_tags_remove_last_recognized_label_removes_rows`, `::test_tags_unrelated_labels_alone_do_not_keep_page` | |
| Rule 3 metadata-only survivor | `test_sync_rules_visibility.py::test_tags_remove_one_tag_keeps_page_updates_tags_no_reembed` | |
| Rule 4 union/sharing | `test_sync_rules_visibility.py` (4 tests) | |
| Rule 5 membership gate both halves | `test_sync_rules_membership.py::test_in2_untagged_page_never_indexed`, `::test_in2_first_relevant_tag_full_build` | |
| Rule 6 rebuild, no reuse, retain 0 | `test_sync_rules_rebuild.py` (3 tests + the deliberate strict xfail for attachments, D2/needs 2.4.1) | |
| Rule 7 classified→purge | `test_sync_rules_delete.py::test_in2_classified_label_removes_rows` | gap G2: not exercised via the real `label_added` event path |
| Rule 8 neighbour isolation | `test_sync_rules_isolation.py::test_in2_change_never_touches_other_pages_rows` | concurrent-interleaving variant out of scope (X4) |
| Event dedup (delivery_id, payload_hash, redelivery-with-different-hash, partial-unique NULL) | `test_event_dedup.py` (incl. `::test_same_delivery_id_different_payload_dedupes_gracefully_not_500`), `test_webhook.py::test_duplicate_delivery_is_deduped`, `test_event_ledger_constraints.py` (3 tests) | adversarial variant present |
| Idempotency keys per event (f8098d0) | `test_webhook.py::test_i1_two_distinct_label_deliveries_on_one_page_each_enqueue_a_job`, `::test_i1_true_duplicate_label_delivery_still_enqueues_one_job`, `::test_i1_two_distinct_trash_deliveries_on_one_page_each_enqueue_a_job` | gap G3: key string itself only proven behaviorally |
| Webhook gate (valid 200 / tampered 401 / missing 401 / unset secret 503 / oversize 413 / rate 429) | `test_webhook.py` (6 tests) | limiter window-reset not meaningful here (X6) |
| Sweeps incl. the f143caa CQL fix + pagination + client-side space filter | `test_reconciliation.py` (6 tests incl. the failed-space adversarial), `app/platform/clients/tests/test_confluence_client.py` (3 tests) | |
| Findings A/B stale-tags family | `test_scope_config_lifecycle.py`, `test_source_scope_lifecycle.py` | KNOWN-PINNED, fix is §D.0 (Step 5 part 0), not a 4.2 gap |

### 2 · Authorization context (auditor 2)

| Contract | Proof | Note |
|---|---|---|
| Unknown body scope → 400 before search; malformed shape → 422 | `test_router_auth_context.py::test_unknown_body_scope_is_400_before_search`; `test_chat_endpoint.py::test_malformed_knowledge_scope_is_rejected` | |
| Known body scope disagreeing with token → ignored, token wins | `test_router_auth_context.py::test_body_scope_disagreeing_with_token_is_ignored` | PARTIAL — gap G4: the log line itself unasserted |
| Tokenless → general-only; body scope/principal inert | `test_chat_endpoint.py::test_tokenless_request_forwards_general_only_and_ignores_body_scope`, `::test_cip1_forwarded_body_principal_is_inert_scope_and_principal_unchanged`, `test_router_auth_context.py::test_tokenless_request_is_general_only` | gaps G5 (empty-string scope), G6 (literal `*`), G7 (extra field) |
| Unknown integration / cross-issuer / inactive platform → 401 | `test_auth_context.py` + `test_router_auth_context.py` (6 tests, CIP-A1/A2/AUTH-1) | |
| GUCs bound-param, None→`*`, []→fail-closed | `retrieval/tests/test_search_repo_gucs.py` | |
| Search txn sets both GUCs + runs as rag_reader | `retriever.py:134-182` + `test_s_reader_role_usage.py` | PARTIAL — gap G10: only `keyword_search` spied; siblings inferred via shared session |
| RLS backstop flag-on/flag-off, two-scope no-cross-leak, AUTH-7 parent expansion, ADR-db-level-customer-scope-isolation-backstop parent-text `*` opt-out (disclosed) | `test_retrieval_knowledge_scope.py` (4 tests) + 2 AUTH-7 tests | |
| Curated: GUC set before read, runs as rag_reader, same resolved scopes as search, CRAG retry reuses them | `test_curated_knowledge.py`, `test_s_reader_curated_fetch.py`, `test_answer_service.py` (3 tests), `test_curated_knowledge_repo.py` | D2: repo test proves app predicate, not RLS (owner session) — docstring pointer needed |
| Token verification order (issuer→alg→kid→sig→aud/exp/iat/sub→lifetime→business-claims), contract schema | `test_token_verifier.py` (~12 tests) + `test_token_claims_contract.py` | PARTIAL — gaps G8 (true forged signature never exercised), G9 (uniform bare 401 at the wire) |
| classified body scope → 400 (tokened + tokenless) | `test_router_classified_scope.py` | |
| Body caps (history/message/images, per-turn) | `test_chat_endpoint.py` (5 tests) | |
| Missing host key → 401; numeric principal rejected | `test_chat_endpoint.py::test_missing_api_key_is_rejected`, `::test_numeric_principal_is_rejected_not_treated_as_space_wide_trust` | |
| Widget proxy forwards bearer | — | frontend/browser level, out of 4.2's backend scope (X5 → Step 4.4/6) |

### 3 · RLS / isolation (auditor 3)

| Contract | Proof | Note |
|---|---|---|
| chunk source policy + scope policy under rag_reader | `test_force_rls_managed_postgres.py::test_non_owner_reader_still_isolated`, `test_customer_isolation_backstop.py` (4 tests), `test_reader_vector_access.py::test_s_source_separates_whole_source_systems_by_source_id` | |
| ANN adversarial: nearer-but-forbidden row never surfaces | `test_reader_vector_access.py::test_vd_rls_forbidden_rows_nearest_neighbor_hit_is_never_returned` | strongest isolation test in the suite |
| curated scope policy + 0009 reader-read | `test_customer_isolation_backstop.py::test_curated_scope_rls_isolates_tagged_entries_but_keeps_global` | |
| page_source reader-read vs anon denied | `test_reader_rls_reconcile.py` (2 tests) | PARTIAL — gap G11: `page_restriction` never read as rag_reader directly |
| Scope fail-closed: empty tags→nobody (0014), unset GUC denies, `*` opt-out, overlap-not-equality, disjoint scope → 0 | `test_customer_isolation_backstop.py::test_sec_empty_tags_visible_to_no_scope`, `::test_scope_rls_fails_closed_when_scope_guc_unset`, `::test_scope_rls_wildcard_is_an_explicit_opt_out`, `::test_sec_read_paths_use_overlap_not_equality` | |
| rag_reader cannot write/DDL; role has NOBYPASSRLS etc.; writer no SUPERUSER; chunk ENABLE-not-FORCE | `test_reader_vector_access.py::test_s_reader_cannot_insert_update_delete_or_create_table`, `knowledge-base/tests/test_r3_reader_role_protect.py`, `test_force_rls_managed_postgres.py` (2 tests) | gaps G12 (SET ROLE escalation untested), G13 (GUC transaction-locality on pooled connections untested) |
| GUC SQL-injection (bound params, hnsw whitelist) | `test_search_repo_gucs.py` (3 tests incl. the DROP TABLE attempt) | gap G14: value-SEMANTIC injection (embedded comma; `*` collision) untested against the real policy |
| Migrations: 0009 downgrade guard (2 tests), 0010 + 0014 round-trips | `knowledge-base/tests/test_migration_{0009_downgrade_guard,0010_scope_rls,0014_chunk_scope_fail_closed}.py` | X1: 0010/0014 downgrades unguarded on Supabase — KNOWN code gap, stays owner-gated |
| Live isolation script hermetic legs + the untagged-corpus skip branch | `test_verify_isolation_script.py` (2 tests) | post-0014 the skip is harmless (floor independently proven) but X2: it could be a loud readiness failure instead — deferred code change |

### 4 · Answer cache + rate limits (auditor 4)

Cache key (`answer_cache.py:47-62`): `sha256(history | principal | allowed_scopes | token_subject)`,
token_subject issuer-namespaced. `company_id` deliberately not in the key (audit-only in v1 — a
documented design choice, not a gap).

| Contract | Proof | Note |
|---|---|---|
| Miss on different principal / scopes / token_subject (incl. cross-issuer same sub) / history (incl. earlier turns); hit on identical | `test_answer_cache.py` (8 tests), `test_auth_context.py::test_same_subject_different_issuer_yields_distinct_token_subject` | |
| Cross-subject isolation at the real HTTP layer | `test_chat_endpoint.py::test_answer_cache_does_not_cross_token_subject_boundary` | PARTIAL — gap G16: cross-KNOWLEDGE-SCOPE isolation never proven through the cached HTTP path |
| Rate limits: chat 20/min keyed `sub:sha256(token_subject)` else `ip:`, webhook 300/min by IP; 429 over limit; body principal can't split/evade the bucket; XFF can't move it; window mechanics + bounded memory | `test_edge_auth.py` (2 tests), `test_chat_endpoint.py` (4 tests), `test_webhook.py::test_rate_limit_returns_429`, `shared/tests/test_rate_limiter.py` (7 tests) | limiter is pure in-process math — no fail-open/closed mode exists; restart/multi-instance reset is a documented limitation |
| Auth-before-limiter order (host key → token → limiter → body) | `router.py:509-521` docstring only | MISSING — gap G15 (chat + feedback endpoints) |
| TTL expiry | `shared/tests/test_ttl_cache.py` (3 tests), `test_answer_cache.py::test_expired_entry_recomputes` | |
| No token material in key/value; trace rows don't leak cache internals | structurally true by type; `test_answer_cache_replays_without_rerunning_retrieval` implies no second trace row | gaps G19 (negative regression lock), G18 (explicit row-count assertion on a hit) |
| Small-talk / refusal through the cache | code: single `answer()` entrypoint, no bypass | MISSING — gap G17 |

## The gap list — closed red-first in this substep

Each lands with the obi-test-writer conventions (docstring names the panel/contract; guards
proven by the 0.2.8 inversion method; genuinely-new behavior red-first).

| id | level | test home | scenario |
|---|---|---|---|
| G1 | db | `test_sync_rules_delete.py` | a `delete_page` job for a never-indexed page is a clean no-op, not an error |
| G2 | db | `test_webhook.py` | `classified` arriving via a real signed `label_added` delivery purges end-to-end |
| G3 | unit | `test_event_dedup.py` | the literal idempotency-key strings `sync_page:{page}:{event}`, `delete_page:{page}:{event}`, `reconcile_space:{space}:{event}` |
| G4 | http | `test_router_auth_context.py` | the `body_knowledge_scope_ignored` log line actually fires on a token/body disagreement |
| G5 | http | `test_chat_endpoint.py` | `knowledge_scope: ""` → 422 via the shape validator |
| G6 | http | `test_chat_endpoint.py` | literal `"*"` body scope → 422 (the internal wildcard sentinel can never be smuggled in) |
| G7 | http | `test_chat_endpoint.py` | an unknown extra top-level body field → 422 (`extra="forbid"` has zero coverage) |
| G8 | unit | `test_token_verifier.py` | a token signed by a DIFFERENT private key than the JWKS-resolved public key → rejected at the signature step (today every negative test fails earlier) |
| G9 | http | `test_router_auth_context.py` | the `/chat` 401 body is byte-identical across all auth failure modes (no detail leaks on the wire) |
| G10 | unit | `retrieval/tests/test_s_reader_role_usage.py` | `dense_search`, `fetch_rerank_texts`, `fetch_page_scopes` each independently proven on the reader-role session (not inferred from `keyword_search`'s spy) |
| G11 | db | `test_reader_rls_reconcile.py` | every `_READER_READ_TABLES` member (esp. `page_restriction`) readable as rag_reader, denied to the anon-like role — parameterized, not `page_source` hardcoded |
| G12 | db | `test_reader_rls_reconcile.py` (or sibling) | rag_reader attempting `SET ROLE <owner>` is denied by Postgres |
| G13 | db | `test_customer_isolation_backstop.py` | a scope GUC set in one transaction does not leak into the next transaction on the same pooled connection (`is_local` honored) |
| G14 | db | `test_customer_isolation_backstop.py` | semantic injection: a scope value with an embedded comma must not split into extra scope tokens; a scope list whose joined value equals `"*"` must not unlock the wildcard opt-out |
| G15 | http | `test_chat_endpoint.py` | 401s (bad host key / bad token) never consume rate-limit budget, pinning the host-key→token→limiter order, on `/chat` and the feedback endpoint |
| G16 | db/http | `test_chat_endpoint.py` | with `CachingAnswerService` wrapping the real service over a scope-tagged corpus, a mews-token cache entry is never served to a toast token with identical history |
| G17 | unit | `test_answer_cache.py` | a small-talk (`trace_id=None`) answer and a `refused=True` answer are both served from cache on an identical repeat (provider called once) |
| G18 | db | `test_chat_endpoint.py` | a cache hit leaves the `query_trace` row count unchanged (explicit count, not inferred from the equal traceId) |
| G19 | unit | `test_answer_cache.py` | neither the computed cache key nor the cached value contains the raw bearer/X-Obi-Token material (regression lock) |

Doc corrections in the same substep:

- **D1** — `test_list_pages_by_label.py:3` docstring still claims the live client issues a
  `space.id = <id>` CQL query; that is exactly what f143caa removed. Correct to the real shape.
- **D2** — `test_curated_knowledge_repo.py` docstring gets a one-line pointer: it proves the
  app-level `tags &&` predicate under the OWNER session (RLS does not bind the owner); the
  RLS-policy-level proof lives in `knowledge-base/tests/test_migration_0010_scope_rls.py`.

## Deliberately deferred (recorded, not silently dropped)

| id | what | why deferred |
|---|---|---|
| X1 | Supabase-host guards on the 0010/0014 `downgrade()` (mirroring 0009's tested guard) | a production-code change already flagged "recommended, not yet added" (2026-09-28 survey); owner-gated, not a test gap |
| X2 | `verify_isolation`'s untagged-corpus skip-as-pass becoming a loud readiness failure (post-membership-gate, untagged active chunks indicate a regression) | changes operator-script behavior/deploy gating — an owner call; the fail-closed floor itself is independently tested (0014 test) |
| X3 | proof the public `/chat` path can never resolve the `'*'` scope sentinel live | unit composition already proves scopes reach the retriever verbatim and auth contexts always carry ≥1 scope; the live leg belongs with 4.3/4.6 |
| X4 | rule-8 concurrent-rebuild interleaving | single-worker single-instance deploy (backend CLAUDE.md); no concurrency to test today |
| X5 | widget-proxy forwarding (host key added, bearer unchanged) | browser level — owner-run in 4.4, Playwright in Step 6 |
| X6 | webhook limiter window-reset/partitioning | single-secret single-sender endpoint; no tenant partitioning exists to test |

Known-pinned, NOT gaps: findings A/B (stale tags survive sweeps) are pinned by sentinel tests and
scheduled as §D.0 (Step 5 part 0); the attachment-rebuild xfail is decision D2 awaiting 2.4.1.

## Closed — 2026-10-05 (same substep)

All 19 gaps closed the same day by three implementer batches (unit · sync/RLS db · HTTP/cache db),
25 new test functions total, every guard inversion-proven and every inverted production file
restored byte-identical (shasums in `test-proof.md`). The closing tests:

| gap | closed by |
|---|---|
| G1 | `test_in2_delete_page_never_indexed_is_clean_noop` (test_sync_rules_delete.py) |
| G2 | `test_tags_classified_label_added_delivery_purges_end_to_end` (test_webhook.py) |
| G3 | 3 × `test_i1_*_idempotency_key_*` (NEW test_event_idempotency_keys.py, unit) |
| G4 | `test_rt1_body_scope_disagreement_fires_the_ignored_log_and_token_scopes_serve` (test_router_auth_context.py) |
| G5 | `test_rt1_empty_string_knowledge_scope_is_422_before_the_service` (test_chat_endpoint.py) |
| G6 | `test_rt1_wildcard_knowledge_scope_sentinel_is_422` (test_chat_endpoint.py) |
| G7 | `test_rt1_unknown_extra_body_field_is_422` (test_chat_endpoint.py) |
| G8 | `test_g8_forged_signature_rejected_at_signature_step` (test_token_verifier.py) — no bug: rejection proven at the signature step (`jwt.InvalidSignatureError` as cause), bare uniform TokenError |
| G9 | `test_sec_chat_401_body_is_byte_identical_across_all_auth_failure_modes` (test_router_auth_context.py, 5 modes) |
| G10 | `test_s_reader_sibling_read_runs_on_the_guc_bound_reader_session[dense_search\|fetch_page_scopes\|fetch_rerank_texts]` (NEW retrieval/tests/test_s_reader_session_binding.py, unit decomposition — the db-level per-sibling `current_user` spy remains an optional strengthening) |
| G11 | `test_sec_every_reader_read_table_readable_by_reader_denied_to_anon[page_source\|page_restriction\|curated_knowledge_entry]` + `test_sec_reader_read_table_list_cannot_silently_shrink` (test_reader_rls_reconcile.py) |
| G12 | `test_sec_reader_set_role_to_owner_is_denied` (test_reader_rls_reconcile.py) |
| G13 | `test_sec_scope_guc_is_local_does_not_leak_into_next_transaction_on_same_connection` (test_customer_isolation_backstop.py) |
| G14 | `test_sec_scope_element_with_embedded_comma_cannot_widen_access`, `test_sec_literal_wildcard_scope_list_cannot_unlock_opt_out` (test_customer_isolation_backstop.py) — **red-first: a REAL defence-in-depth hole.** Probed live as rag_reader: one element `"obi-mews-test,obi-toast-test"` returned BOTH scopes' rows and `["*"]` as data unlocked the wildcard opt-out; nothing at any layer (config loader, resolver, registry, applier, policy) prevented it. Fixed by the smallest change at the one choke point every production scope-GUC write funnels through: `apply_knowledge_scope` (search_repo.py) now raises ValueError on any element containing `,` or `*` before joining; the internal `None`→`'*'` sentinel is untouched. Strictly tightening. Component doc: `docs/Final_docs/retrieval/scope-enforcement-read-path.md`. |
| G15 | `test_sec_auth_failures_never_consume_rate_limit_budget_on_chat` + `..._on_feedback` (test_chat_endpoint.py) — production respects the documented host-key→token→limiter order; feedback's only drivable auth failure is the host key (no token gate there), noted in the docstring |
| G16 | `test_sec_answer_cache_never_crosses_the_knowledge_scope_boundary_end_to_end` (test_chat_endpoint.py; hub-issuer fixture so scope is the only key discriminator) |
| G17 | `test_g17_small_talk_answer_is_served_from_cache`, `test_g17_refused_answer_is_served_from_cache` (test_answer_cache.py) |
| G18 | `test_rt5_cache_hit_leaves_the_query_trace_row_count_unchanged` (test_chat_endpoint.py) |
| G19 | `test_g19_cache_key_and_cached_value_carry_no_raw_token_material` (test_answer_cache.py) |

D1/D2 docstring corrections applied. The only production change in the whole substep is the G14
fail-closed validation. Proofs: `test-proof.md` in this folder.

> **Update 2026-10-05 (later the same day): X1 ACCEPTED and built.** The owner delegated the
> X1/X2 call; X1 was chosen (a prod downgrade silently reopens a cross-tenant leak — a security
> cliff, where X2 only loudens an existing gate's failure message). Both `0010_customer_scope_rls`
> and `0014_chunk_scope_fail_closed` now carry 0009's enforced `_refuse_supabase_downgrade` host
> guard, proven by 4 hermetic fake-bind tests in
> `knowledge-base/tests/test_migration_scope_downgrade_guards.py` (blocks a `*.supabase.co` host,
> allows localhost — the local round-trip tests stay green; kb suite 45 → 49). X2 stays deferred.

> **Update 2026-10-05 (evening): X2 ALSO accepted and built.** The owner ordered X2 after X1:
> `check_deploy_readiness` (setup_supabase.py) now runs an untagged-ACTIVE-chunk census and
> refuses the deploy (rc 11) naming each dark page, instead of `verify_isolation`'s skip-as-pass
> posture (that skip itself is unchanged — the *gate* is where loudness belongs). Red-first proven:
> `test_deploy_readiness_fails_loudly_on_untagged_active_chunks` failed on the old gate (rc 0, no
> census line) and passes after; the guard `test_deploy_readiness_ignores_untagged_inactive_chunks`
> pins that GC remnants don't block. Live read-only run against Supabase: census 0, gate OK.
> X3–X6 remain the open deferred set.
