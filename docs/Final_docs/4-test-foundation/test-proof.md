# 4.2 · Test proofs — the gap-closing tests, each proven real

> **Note (2026-10-20).** This is a record of what ran at the time; results are unchanged. Since then
> the knowledge-scope `-test` tag axis it mentions (`obi-general-test`, `obi-mews-test`, …,
> `app.allowed_knowledge_scopes`) was retired by ADR-routing-labels-sole-content-axis — routing
> labels are the only content axis — and the `apps/automation`, `apps/web` and `infra/foundation`
> folders were renamed to `backend/`, `frontend/` and `knowledge-base/local/`.

Date: 2026-10-05 · substep 4.2 (golf 1). One block per gap test, in the 0.2.8 method of the sync-rules test-proof file (removed): green-today guards are inverted in production (red for the stated reason), the production file restored byte-identical (shasum-verified), green again. Red-first entries (G14) show red-today → the fix → green. Gap ids map to docs/Final_docs/4-test-foundation/coverage-audit.md.

# 4.2 unit-gap proof — golf 1 (G3, G8, G10, G17, G19)

The 0.2.8 inversion method for green-today guards: temporarily invert the one production behavior
the test pins, run the test, show it goes RED for the right reason, restore the production file
byte-identical (sha256 before == after), re-run green. Commands run from `backend/`, unit level
only — no DATABASE_URL set, no db-marked test executed. Substep: 4.2. Date: 2026-10-05.

Production checksums (before == after, verified by `diff` of `shasum -a 256` outputs — printed
`CHECKSUMS-IDENTICAL` / `PROD-FILES-INTACT`):

```
397cba5646d0cc7e58bd7d9d79a7bbd817134dce6f98a97b7ad34bee4dbdce66  app/features/confluence_sync/application/event_service.py
2ffe40552bf7c661dc3ea65921d6176c0fb29f106cdf5856ce867ef518e191ca  app/features/rag_agent/server/token_verifier.py
51fe9c4f6b642045058f563b862207498a35e80ec1f0bc36f3a1d1fe27c4f58c  app/features/retrieval/application/retriever.py
70206a5a1861cebc5c5da81a2f41ab582b12211f2016ebd90a8b56c947e9498a  app/features/rag_agent/application/answer_cache.py
```

### G3 — `test_i1_sync_event_idempotency_key_is_jobtype_page_and_event_id`, unit

| Step | What | Result |
|---|---|---|
| Inversion applied | `event_service.py`: `key = f"{JOB_SYNC_PAGE}:{envelope.page_id}:{event_id}"` → `f"{JOB_SYNC_PAGE}:{envelope.page_id}"` (drop the event-ledger id — the exact pre-f8098d0 forever-colliding key) | test RED |
| Red output line | `AssertionError: assert 'sync_page:1001' == 'sync_page:1001:77'` (test_event_idempotency_keys.py:58) | right reason |
| Restored green | `cp` backup back; `shasum` `397cba56…` matches before; `3 passed in 0.04s` | checksum match |

### G3 — `test_i1_delete_event_idempotency_key_is_jobtype_page_and_event_id`, unit

| Step | What | Result |
|---|---|---|
| Inversion applied | `event_service.py`: `key = f"{JOB_DELETE_PAGE}:{envelope.page_id}:{event_id}"` → `f"{JOB_DELETE_PAGE}:{envelope.page_id}"` (same combined inversion run) | test RED |
| Red output line | `AssertionError: assert 'delete_page:1001' == 'delete_page:1001:77'` (test_event_idempotency_keys.py:70) | right reason |
| Restored green | same restore; `shasum` `397cba56…` matches; `3 passed` | checksum match |

### G3 — `test_i1_space_event_idempotency_key_is_jobtype_space_and_event_id`, unit

| Step | What | Result |
|---|---|---|
| Inversion applied | `event_service.py`: `key = f"{JOB_RECONCILE_SPACE}:{envelope.space_id}:{event_id}"` → `f"{JOB_RECONCILE_SPACE}:{envelope.space_id}"` (same combined inversion run) | test RED |
| Red output line | `AssertionError: assert 'reconcile_space:100' == 'reconcile_space:100:77'` (test_event_idempotency_keys.py:82) | right reason |
| Restored green | same restore; `shasum` `397cba56…` matches; `3 passed` | checksum match |

### G8 — `test_g8_forged_signature_rejected_at_signature_step`, unit

| Step | What | Result |
|---|---|---|
| Inversion applied | `token_verifier.py` step 4: `options={"require": list(REQUIRED_CLAIMS)}` → `options={"require": list(REQUIRED_CLAIMS), "verify_signature": False}` (signature check disabled) | test RED |
| Red output line | `Failed: DID NOT RAISE TokenError` (test_token_verifier.py:201) — with the check off, the token signed by the WRONG private key was accepted, exactly what the guard exists to catch | right reason |
| Restored green | `cp` backup back; `shasum` `2ffe4055…` matches before; `1 passed in 0.34s` | checksum match |

No production bug: on the unmodified verifier, the forged-key token IS rejected, and the cause
chain is `jwt.InvalidSignatureError` — the rejection happens at the signature step (steps 1–3
passed, 5–6 never masked it), collapsing to the uniform bare `TokenError("invalid token")`.
G8 is a guard like the others.

### G10 — `test_s_reader_sibling_read_runs_on_the_guc_bound_reader_session[dense_search]`, unit

| Step | What | Result |
|---|---|---|
| Inversion applied | `retriever.py` `_search`: `dense = dense_search(session, …)` → `dense_search(self._session_factory().__enter__(), …)` (dense read moved onto a second session, off the GUC-configured one) | test RED |
| Red output line | `assert 2 == 1` on `assert len(factory_sessions) == 1  # one reader session for the whole search transaction` (test_s_reader_session_binding.py:106) | right reason |
| Restored green | `cp` backup back; `shasum` `51fe9c4f…` matches; `3 passed` | checksum match |

### G10 — `test_s_reader_sibling_read_runs_on_the_guc_bound_reader_session[fetch_page_scopes]`, unit

| Step | What | Result |
|---|---|---|
| Inversion applied | `retriever.py` `_search`: `fetch_page_scopes(session, ranked)` → `fetch_page_scopes(self._session_factory().__enter__(), ranked)` (separate targeted inversion, after restoring the previous one) | test RED |
| Red output line | `assert 2 == 1` on the one-reader-session assertion (test_s_reader_session_binding.py:106) | right reason |
| Restored green | same restore; `shasum` `51fe9c4f…` matches; `3 passed` | checksum match |

### G10 — `test_s_reader_sibling_read_runs_on_the_guc_bound_reader_session[fetch_rerank_texts]`, unit

| Step | What | Result |
|---|---|---|
| Inversion applied | `retriever.py` `_search`: `fetch_rerank_texts(session, …)` → `fetch_rerank_texts(self._session_factory().__enter__(), …)` (separate targeted inversion) | test RED |
| Red output line | `assert 2 == 1` on the one-reader-session assertion (test_s_reader_session_binding.py:106) | right reason |
| Restored green | same restore; `shasum` `51fe9c4f…` matches; `3 passed in 0.01s` | checksum match |

### G17 — `test_g17_small_talk_answer_is_served_from_cache`, unit

| Step | What | Result |
|---|---|---|
| Inversion applied | `answer_cache.py` `CachingAnswerService.answer`: `self._cache.set(key, result)` → `if not result.refused and result.trace_id is not None: self._cache.set(key, result)` (small-talk/refusal bypass introduced) | test RED |
| Red output line | `AssertionError: assert 2 == 1` on `assert inner.calls == 1` (test_answer_cache.py:211) | right reason |
| Restored green | `cp` backup back; `shasum` `70206a5a…` matches; file's full suite green | checksum match |

### G17 — `test_g17_refused_answer_is_served_from_cache`, unit

| Step | What | Result |
|---|---|---|
| Inversion applied | same bypass inversion (one run, both G17 tests red together) | test RED |
| Red output line | `AssertionError: assert 2 == 1` on `assert inner.calls == 1` (test_answer_cache.py:228) | right reason |
| Restored green | same restore; `shasum` `70206a5a…` matches; green | checksum match |

### G19 — `test_g19_cache_key_and_cached_value_carry_no_raw_token_material`, unit

| Step | What | Result |
|---|---|---|
| Inversion applied | `answer_cache.py` `_cache_key`: `return hashlib.sha256(payload.encode("utf-8")).hexdigest()` → `return payload` (key becomes the readable plaintext concatenation of history/principal/scopes/subject) | test RED |
| Red output line | `AssertionError` on `assert len(key) == 64 and set(key) <= set("0123456789abcdef")  # a bare sha256 hex digest` (test_answer_cache.py:249) | right reason |
| Restored green | `cp` backup back; `shasum` `70206a5a…` matches before; final combined run `38 passed` | checksum match |

Final combined green run over every file touched in this batch:
`uv run pytest app/features/confluence_sync/tests/test_event_idempotency_keys.py app/features/rag_agent/tests/test_token_verifier.py app/features/retrieval/tests/test_s_reader_session_binding.py app/features/rag_agent/tests/test_answer_cache.py app/features/confluence_sync/tests/test_list_pages_by_label.py -q` → `38 passed`.

# 4.2 coverage-gap proof — database batch 1 (G1, G2, G11, G12, G13, G14)

The 0.2.8 method: a test is only real if it goes red for a stated reason and green after the
change. G14a/G14b are **red-first** tests (a missing fail-closed validation — the table shows
red-today → the production change → green). G1, G2, G11, G12 and G13 are **green-today guards**
proven by inversion: invert the one production behavior, red for the right reason, restore
byte-identical (shasum before == after), green again. Commands run from `backend/` with
`DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag` exported.

Substep: 4.2 (coverage audit, DB-level golf 1). Date: 2026-10-05.

### G1 — `test_in2_delete_page_never_indexed_is_clean_noop`, database

File: `app/features/confluence_sync/tests/test_sync_rules_delete.py` · panel i2-gone

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest app/features/confluence_sync/tests/test_sync_rules_delete.py::test_in2_delete_page_never_indexed_is_clean_noop` | PASSED — a `delete_page` job on page 4242 (no page_source row, never indexed) returns `status == "succeeded"`, `outcome.action == "skipped"`, all five row counts 0 |
| Guard inverted | `command_handler.py` `apply_sync_command` delete branch: `return SyncOutcome(action="skipped", ...)` → `raise RuntimeError(...)` | FAILED for the right reason — `RunResult(status='failed', error="RuntimeError('INVERSION G1: ...')")`, `assert 'failed' == 'succeeded'` |
| Restored | revert the one line; `shasum app/features/ingestion/application/command_handler.py` | `c16fb7828c11ea086670d09ad88fe7689a11d0b9` before and after (byte-identical); rerun PASSED |

### G2 — `test_tags_classified_label_added_delivery_purges_end_to_end`, database

File: `app/features/confluence_sync/tests/test_webhook.py` · panel tg-classified

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest app/features/confluence_sync/tests/test_webhook.py::test_tags_classified_label_added_delivery_purges_end_to_end` | PASSED — index page 1001, set labels `[obi-general-test, classified]`, POST a real HMAC-signed `label_added` delivery → 200 + job id → `drain` worker → every row count 0 (webhook → ledger → job → worker, rule 7 end-to-end) |
| Guard inverted | `confluence_sync/domain/ingest_decision.py` `resolve_scopes`: `if RESERVED_CLASSIFIED_SCOPE in norm_labels:` → `if False and ...` | FAILED for the right reason — the page survives the delivery: `{'chunk': 18, 'document': 1, ...} != {'chunk': 0, ...}` |
| Restored | revert the one line; `shasum app/features/confluence_sync/domain/ingest_decision.py` | `b12fbc0539dc744c30b8d599a7c6202842839014` before and after; rerun PASSED |

### G11 — `test_sec_every_reader_read_table_readable_by_reader_denied_to_anon[page_source|page_restriction|curated_knowledge_entry]`, database

File: `app/features/confluence_sync/tests/test_reader_rls_reconcile.py` · panel s-anon

Parameterized over the production `schema._READER_READ_TABLES` tuple itself; each table carries a
seeded committed row (page_source via `index_page`, page_restriction + curated_knowledge_entry via
owner inserts), so visibility is a real count, never vacuous-empty.

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest "app/features/confluence_sync/tests/test_reader_rls_reconcile.py::test_sec_every_reader_read_table_readable_by_reader_denied_to_anon"` | 3 PASSED — per table: RLS-on/no-policy denies both roles; after `apply_reader_rls` rag_reader reads the seeded count, the anon-like role (GRANT SELECT, NOBYPASSRLS) stays at 0 before AND after |
| First inversion attempt | drop `"page_restriction"` from `_READER_READ_TABLES` | test did NOT go red — the parametrize derives its cases from the production list at collection, so the dropped table silently dropped its own proof (2 passed). Fixed by adding the companion pin `test_sec_reader_read_table_list_cannot_silently_shrink` (asserts the list ⊇ the three known tables), which goes red under exactly this inversion |
| Guard inverted | `knowledge-base/schema/schema.py` `apply_reader_rls` loop: skip `CREATE POLICY` for `page_restriction` | FAILED for the right reason — `AssertionError: rag_reader cannot read page_restriction after apply_reader_rls`, `assert 0 == 1` (1 failed, 2 passed) |
| Restored | revert; `shasum knowledge-base/schema/schema.py` | `699d1369d51ac15b9f11c1b3772d2242082e680d` before and after; rerun 3 PASSED (+ the pin test) |

### G12 — `test_sec_reader_set_role_to_owner_is_denied`, database

File: `app/features/confluence_sync/tests/test_reader_rls_reconcile.py` · panel s-reader

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest "app/features/confluence_sync/tests/test_reader_rls_reconcile.py::test_sec_reader_set_role_to_owner_is_denied"` | PASSED — as rag_reader, `SET ROLE rag` (the owner role from the harness engine URL) raises `ProgrammingError` matching "permission denied"; after rollback the same session still answers `current_user == 'rag_reader'` |
| Guard inverted (DB state, no file) | `psql -U rag -d postgres -c "GRANT rag TO rag_reader"`; rerun | FAILED for the right reason — `DID NOT RAISE ProgrammingError`: with membership granted the escalation succeeds, proving the test asserts the real privilege boundary |
| Restored | `REVOKE rag FROM rag_reader`; rerun | PASSED; no file was touched for this inversion |

### G13 — `test_sec_scope_guc_is_local_does_not_leak_into_next_transaction_on_same_connection`, database

File: `app/features/confluence_sync/tests/test_customer_isolation_backstop.py` · panel 3.4.1

Drives the production `apply_knowledge_scope` (`set_config(..., is_local=true)`) on one checked-out
reader connection reused across two transactions; the source GUC is pinned session-level on purpose
so the txn-2 outcome is attributable to the scope GUC alone (and is RESET before the connection
returns to the pool).

| Step | Command | Result |
|---|---|---|
| Passes today | `uv run pytest "app/features/confluence_sync/tests/test_customer_isolation_backstop.py::test_sec_scope_guc_is_local_does_not_leak_into_next_transaction_on_same_connection"` | PASSED — txn 1 (scope mews) sees its rows (>0); txn 2 on the SAME DBAPI connection, setting nothing, reads 0 rows and `current_setting('app.allowed_knowledge_scopes', true)` is unset |
| Guard inverted | `search_repo.py` `apply_knowledge_scope`: `set_config(..., true)` → `set_config(..., false)` (session-level) | FAILED for the right reason — `scope GUC visibility leaked into the next transaction on the same pooled connection -> is_local not honored (fail-open)`, `assert 18 == 0` |
| Restored | revert the one flag; `shasum app/features/retrieval/infrastructure/search_repo.py` | `1a3235123e4f030860a0b9fb89a619f74b337022` before and after (the post-G14-fix baseline); rerun PASSED |

### G14a — `test_sec_scope_element_with_embedded_comma_cannot_widen_access`, database

File: `app/features/confluence_sync/tests/test_customer_isolation_backstop.py` · panel 3.4.1 · **red-first**

Layer survey before any change (what prevents a comma'd scope VALUE today): the config loader
(`knowledge_scopes.py`) validates lowercase/dupes/presence only — a scope *named* `a,b` or `*`
would load; `resolve_allowed_scopes` and the platform registry gate on *membership* in that set,
so they inherit whatever the file allows; `apply_knowledge_scope` joined blindly; the RLS policy
splits with `string_to_array(guc, ',')` and compares the whole GUC against `'*'`. **Nothing at any
layer failed closed** → missing validation, owner layer = `apply_knowledge_scope` (the one choke
point every production scope-GUC write funnels through: search txn, parent expansion `None`,
curated repo).

| Step | Command | Result |
|---|---|---|
| Red today (hole demonstrated) | throwaway probe (same seeding, as rag_reader against the real policy): `apply_knowledge_scope(s, ["obi-mews-test,obi-toast-test"])` | `PROBE comma'd single element: mews=18 toast=8` — ONE element granted BOTH scopes' rows |
| Red today (the test) | `uv run pytest "...test_customer_isolation_backstop.py::test_sec_scope_element_with_embedded_comma_cannot_widen_access"` | FAILED — `DID NOT RAISE ValueError` (no validation exists at any layer) |
| The change | `search_repo.py` `apply_knowledge_scope`: reject any element containing `,` or `*` with `ValueError` before joining (the `None` → `'*'` internal sentinel untouched) | smallest fail-closed fix, one function, retrieval infrastructure (the owner of the join/GUC semantics) |
| After the change | same | PASSED — ValueError raised, GUC never set, RESTRICTIVE policy fails closed: 0 rows from either scope |

### G14b — `test_sec_literal_wildcard_scope_list_cannot_unlock_opt_out`, database

File: `app/features/confluence_sync/tests/test_customer_isolation_backstop.py` · panel 3.4.1 · **red-first**

| Step | Command | Result |
|---|---|---|
| Red today (hole demonstrated) | probe: `apply_knowledge_scope(s, ["*"])` as rag_reader | `PROBE ['*'] as data: mews=18` — a caller-supplied `["*"]` list unlocked the wildcard RLS opt-out |
| Red today (the test) | `uv run pytest "...test_customer_isolation_backstop.py::test_sec_literal_wildcard_scope_list_cannot_unlock_opt_out"` | FAILED — `DID NOT RAISE ValueError` |
| The change | same single fix as G14a (`*` in an element is rejected) | the internal `None` → `'*'` sentinel is asserted to still work in the same session, so data and sentinel can never be conflated |
| After the change | same | PASSED — `["*"]` rejected, 0 rows; `apply_knowledge_scope(s, None)` still opts out (>0 rows) |

---

Final state: the five touched files run `45 passed` together
(`test_sync_rules_delete.py test_webhook.py test_reader_rls_reconcile.py
test_customer_isolation_backstop.py` + `retrieval/tests/test_search_repo_gucs.py`, the unit suite
covering the changed function — all 9 of its existing GUC tests unaffected by the validation).
Every inversion file restored byte-identical (shasums above). Row security was never disabled; the
non-chunk RLS toggling follows the files' existing setup/teardown discipline.

# 4.2 coverage-audit gap closures — batch db2 (HTTP/chat-endpoint + cache): G4 G5 G6 G7 G9 G15 G16 G18

The 0.2.8 method on green-today guards: each test passed on the unmodified code, then the single
sharpest production inversion made it red for the stated reason, then the production file was
restored byte-identical (shasum proof) and the test went green again. Commands run from `backend/`
with:

```
export DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag
```

Substep: 4.2 (roadmap Step 4, sync-rules §15.2 golf 1). Date: 2026-10-05.

Baseline shasums (before any inversion, and after every restore):

```
f17d39a3ecb18189efdaf6908b65848c2332805db882bff74e74f8be9df1e6aa  app/features/rag_agent/server/router.py
70206a5a1861cebc5c5da81a2f41ab582b12211f2016ebd90a8b56c947e9498a  app/features/rag_agent/application/answer_cache.py
```

### G4 — `test_rt1_body_scope_disagreement_fires_the_ignored_log_and_token_scopes_serve`, database (http)

File: `app/features/confluence_sync/tests/test_router_auth_context.py` · panel r1-auth

| Step | Command | Result |
|---|---|---|
| Green today | `uv run pytest app/features/confluence_sync/tests/test_router_auth_context.py::test_rt1_body_scope_disagreement_fires_the_ignored_log_and_token_scopes_serve` | PASSED — one `body_knowledge_scope_ignored` entry with `requested="obi-toast-test"`, `token_scopes=["obi-general-test","obi-mews-test"]`; served scopes stay the token's |
| Inversion | router.py `_validate_body_knowledge_scope`: the `log.info("body_knowledge_scope_ignored", ...)` call replaced with `pass` | FAILED — `assert len(ignored) == 1` → `assert 0 == 1` (the line never fired; request still 200 and token still wins, so only the log guard catches it) |
| Restore | shasum `f17d39a3…` matches baseline | PASSED again (final full-file run) |

Log capture: `_LogRecorder` wrapping `chat_router_module.log` via monkeypatch (structlog's
`capture_logs()` is unusable this late in the run — `cache_logger_on_first_use=True` warmed the
module logger against the real renderer long before; see `_LogRecorder`'s docstring).

### G5 — `test_rt1_empty_string_knowledge_scope_is_422_before_the_service`, database (http)

File: `app/features/confluence_sync/tests/test_chat_endpoint.py` · panel r1-limits

| Step | Command | Result |
|---|---|---|
| Green today | `uv run pytest app/features/confluence_sync/tests/test_chat_endpoint.py::test_rt1_empty_string_knowledge_scope_is_422_before_the_service` | PASSED — `""` is 422 (pattern requires ≥1 char), spy service never invoked |
| Inversion (shared with G6) | router.py `_reject_malformed_knowledge_scope`: condition prefixed `if False and …` (validator accepts everything) | FAILED — `assert 400 == 422`: the empty string travelled past body validation and was only stopped by the deeper `_validate_body_knowledge_scope` 400 whitelist gate — the 422 shape guard was gone |
| Restore | shasum `f17d39a3…` matches baseline | PASSED again |

### G6 — `test_rt1_wildcard_knowledge_scope_sentinel_is_422`, database (http)

File: `app/features/confluence_sync/tests/test_chat_endpoint.py` · panel r1-limits

| Step | Command | Result |
|---|---|---|
| Green today | `uv run pytest app/features/confluence_sync/tests/test_chat_endpoint.py::test_rt1_wildcard_knowledge_scope_sentinel_is_422` | PASSED — the literal `"*"` (the RLS wildcard opt-out sentinel) is 422, spy never invoked |
| Inversion | same single inversion as G5 (validator disabled) | FAILED — `assert 400 == 422`: `"*"` got past the shape guard (today only the second-layer unknown-scope 400 caught it — defense-in-depth held, but the pinned first gate was gone) |
| Restore | shasum `f17d39a3…` matches baseline | PASSED again |

### G7 — `test_rt1_unknown_extra_body_field_is_422`, database (http)

File: `app/features/confluence_sync/tests/test_chat_endpoint.py` · panel r1-limits

| Step | Command | Result |
|---|---|---|
| Green today | `uv run pytest app/features/confluence_sync/tests/test_chat_endpoint.py::test_rt1_unknown_extra_body_field_is_422` | PASSED — unknown top-level field `scope` → 422, spy never invoked |
| Inversion | router.py `ChatRequestBody`: `extra="forbid"` → `extra="ignore"` | FAILED — `assert 200 == 422`: the unknown field was silently dropped and the request served |
| Restore | shasum `f17d39a3…` matches baseline | PASSED again |

### G9 — `test_sec_chat_401_body_is_byte_identical_across_all_auth_failure_modes`, database (http)

File: `app/features/confluence_sync/tests/test_router_auth_context.py` · panel r1-auth

Five drivable failure modes: garbage token (`TokenError`), unknown issuer (new `UNKNOWN_ISS`
fixture entry — issuer absent from the registry), inactive platform, cross-issuer integration,
unknown integration.

| Step | Command | Result |
|---|---|---|
| Green today | `uv run pytest app/features/confluence_sync/tests/test_router_auth_context.py::test_sec_chat_401_body_is_byte_identical_across_all_auth_failure_modes` | PASSED — all five 401 bodies are the identical bare `{"detail":"invalid token"}`; service never reached |
| Inversion | router.py `_resolve_auth_context`: `"invalid token"` → `f"invalid token: {exc}"` | FAILED — `assert 5 == 1`: five distinct bodies leaking the gate (`…: bad`, `…: https://unknown.example.com`, `…: https://pos.toasttab.com`, `…: platform mews may not assert integration 'toast'`, `…: wordpress`) |
| Restore | shasum `f17d39a3…` matches baseline | PASSED again |

### G15 — `test_sec_auth_failures_never_consume_rate_limit_budget_on_chat` + `test_sec_auth_failures_never_consume_rate_limit_budget_on_feedback`, database (http)

File: `app/features/confluence_sync/tests/test_chat_endpoint.py` · panel r1-limits

Production does NOT violate the documented host-key → token → limiter order — both tests were
green on the unmodified code. The feedback endpoint has no X-Obi-Token gate, so its only drivable
auth-failure mode is the wrong host key (said in the docstring); /chat covers both wrong-key and
invalid-token modes. A missing trace row is a documented silent no-op in
`update_query_trace_feedback`, so the feedback test needs no corpus.

| Step | Command | Result |
|---|---|---|
| Green today | `uv run pytest app/features/confluence_sync/tests/test_chat_endpoint.py::test_sec_auth_failures_never_consume_rate_limit_budget_on_chat app/features/confluence_sync/tests/test_chat_endpoint.py::test_sec_auth_failures_never_consume_rate_limit_budget_on_feedback` | PASSED — under a 1/min limit, 3×wrong-key + 3×bad-token (chat) / 3×wrong-key (feedback) all 401; the valid request after them is 200; the control request is the 429 |
| Inversion | router.py: the limiter block moved ABOVE `_verify_api_key` in `post_chat` AND `patch_chat_feedback` | FAILED (both) — `assert 429 == 401` on the second bad-credential request: 401s now consume budget |
| Restore | shasum `f17d39a3…` matches baseline | PASSED again |

### G16 — `test_sec_answer_cache_never_crosses_the_knowledge_scope_boundary_end_to_end`, database (db/http)

File: `app/features/confluence_sync/tests/test_chat_endpoint.py` · panel r3-deny

Built so the cache key differs ONLY in `allowed_scopes`: a purpose-built registry
(`_hub_platforms_file`) with one active hub issuer allowed to assert both mews and toast, and two
tokens sharing issuer + subject (`u-shared`) — identical issuer-namespaced `token_subject`, so a
cross-scope hit cannot be masked by the subject component. Real grounded `AnswerService` wrapped
in `CachingAnswerService` over the AUTH-6 scope-tagged corpus (3002 mews / 3004 toast). Contains
its own cache-is-engaged control: the identical mews replay IS a hit (same traceId).

| Step | Command | Result |
|---|---|---|
| Green today | `uv run pytest app/features/confluence_sync/tests/test_chat_endpoint.py::test_sec_answer_cache_never_crosses_the_knowledge_scope_boundary_end_to_end` | PASSED — mews cached (replay hit), toast gets its own trace id, zero 3002 citations, 3004 cited |
| Inversion | answer_cache.py `_cache_key`: the `",".join(auth.allowed_scopes)` component replaced with `""` | FAILED — `assert '1' != '1'`: the toast token WAS served the mews cached entry (identical traceId) — proving the scope component of the key is the only thing standing between the two scopes here |
| Restore | shasum `70206a5a…` matches baseline | PASSED again |

### G18 — `test_rt5_cache_hit_leaves_the_query_trace_row_count_unchanged`, database

File: `app/features/confluence_sync/tests/test_chat_endpoint.py` · panel s-audit

Explicit `SELECT count(*) FROM query_trace` before/after, mirroring
`test_r1_short_small_talk_writes_no_query_trace_row`; also asserts the miss wrote exactly one row
(`before + 1`) so the no-new-row claim is not trivially true of an idle pipeline.

| Step | Command | Result |
|---|---|---|
| Green today | `uv run pytest app/features/confluence_sync/tests/test_chat_endpoint.py::test_rt5_cache_hit_leaves_the_query_trace_row_count_unchanged` | PASSED — miss writes 1 row; the hit returns the same traceId and the count is unchanged |
| Inversion | answer_cache.py `CachingAnswerService.answer`: `self._cache.set(key, result)` removed | FAILED — `assert '2' == '1'`: the repeat re-ran retrieval and wrote trace row 2 (the explicit row-count guard sits behind this first assertion) |
| Restore | shasum `70206a5a…` matches baseline | PASSED again |

---

Final state: both production files byte-identical to baseline (shasums above re-verified after the
last restore). Full runs of both touched test files:

```
uv run pytest app/features/confluence_sync/tests/test_chat_endpoint.py \
              app/features/confluence_sync/tests/test_router_auth_context.py -q
65 passed, 1 warning in 13.05s
```

Lint/type on touched files: `ruff check` clean, `ruff format --check` clean, pyright 6 errors —
all pre-existing (the documented `_CitingGenerator`-family `AnswerGenerator` protocol gap, every
error line predates this batch's additions). Whole-repo: ruff 18 (= baseline), pyright 41
(< the 43 baseline floor).
