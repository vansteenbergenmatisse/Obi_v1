# Phase-4 embed security loop — wave log

Append-only. One section per wave. Never edit a prior wave; a correction is a new dated note.

## Wave 0 — Research & requirement-traceability matrix (2026-09-22)

Six independent read-only research agents (auth & host-key, browser/iframe, authorization/isolation, Confluence/identity, lifecycle/stale-state, config/migration/CI) inspected code, config, tests, migrations, and docs — reaching conclusions from the code itself, not the plan. One agent (auth & host-key) hit a structured-output failure on the first run and was re-run standalone. A synthesis pass built `traceability-matrix.md`.

**Baseline (green) before any change:** `make boundaries` OK · backend unit 529 passed · knowledge-base unit 17 passed · frontend vitest 240 passed · Playwright e2e 4 passed.

**Headline findings.** The backend auth/authorization core is correctly built and well-tested (JWT chain, RESTRICTIVE RLS migration 0010 fail-closed, host-key constant-time + server-only, body-cannot-override-token, cache keys bound to scope+subject). Genuine gaps cluster in: frontend embed lifecycle (obi:clear is not a real logout; token-fetch race; silent scope switch), production config (no guard against test/localhost platforms or domains in prod), and backend identity (token_subject not issuer-namespaced). Five mandate premises **refuted**: token_subject not namespaced; obi:clear does not drop in-flight answers; a token refresh can silently change scope; there are no `docs/brief` runbooks (three packs in `docs/embedding/`); test/localhost platforms are not rejected in production. "Base" and "OmniBoost Test" do not exist as named platforms (confirmed).

**Gap → slice grouping:** see README. Owner decisions: fix **all actionable gaps**; execute **autonomously, committing each verified slice** (green gate + ledger entry), reporting at each audit-wave boundary.

### Implementation slices

**S1 — embed lifecycle & logout — DONE (committed).** Implemented by an independent implementation agent, test-first; verified independently in the main window. Closed LC-1/LC-4 (obi:clear now routes through the chat session's `restart()` — aborts the in-flight stream, clears messages + conversationId — so it is a real logout, not a panel hide), LC-5 (module-scoped epoch guard drops a stale in-flight token fetch after clear/re-point), LC-2/3/6 (bridge decodes display-only integration+company claims and resets the conversation on a scope-changing renewal; a 401 drives a subscribed onUnauthorized→restart), BIT-7 (runtime non-empty-string guard on the obi:token field). 9 new tests. **Gate:** vitest 240→249 passed · typecheck clean · Playwright embed e2e 4 passed · boundaries green. Client-side claim decode is display/equality-only, never trust-bearing (backend TokenVerifier stays authoritative). Files: app/embed/embed-frame.tsx, features/chat/index.ts, features/embed/{iframe-bridge,loader}.ts + 3 test files.

**S2 — production config trust guard — DONE (committed).** Independent implementer, test-first; verified in the main window. Closed CFG-02/AUTHRT-1 (backend `load_platform_registry` refuses an active platform with a placeholder/non-https/localhost/.local issuer or JWKS outside offline, naming it), CFG-04 (backend refuses localhost CSP domains on active entries; frontend `computeEmbedCsp` strips localhost outside local/dev, fails closed), CFG-05 (aligned backend/frontend offline env sets — `development` consistent both sides — pinned by a contract test each side). Guard gated on the single `offline` signal; only non-test caller is `Settings.platform_registry` (grep-verified). 13 tests. **Gate:** backend unit 529→538 · kb 17 · frontend vitest 249→253 · typecheck clean · ruff/pyright clean · boundaries green. **Owner blocker surfaced:** committed `datahub` is active with a TODO placeholder → the guard now (correctly) fails non-offline startup; owner must supply real datahub issuer/JWKS/domains or set it inactive before a real deploy (recorded as NEED-FROM-YOU in the ledger; data not invented per rule 12). **Open judgment for the audit wave:** CFG-05 aligned `development` toward offline (permissive) — real prod uses ENV=production/unset (guarded); flagged for test-vs-prod-isolation scrutiny. Files: platforms.py, settings.py, csp.ts + 3 test files.

**S3 — backend identity & defense-in-depth — DONE (committed).** Independent implementer, test-first; verified in the main window incl. the full DB suite. Closed CIP-4 (`token_subject` now `issuer\x00subject` via `_identity_key` — two issuers sharing a `sub` no longer collide across rate-limit/idempotency/cache/audit keys), BIT-10 (`server-only` trip-wire on automation-api/client.ts), CIP-5 (no v1 code change — added ADR-0019 recording page-principal ACL as an app-layer-only defense-in-depth gap + a pinning test for the `principal=None → only unrestricted` invariant; RLS backstop gated before per-principal ACL). 5 new + 3 updated tests. **Gate:** backend unit 538→543 · full backend DB suite 271 passed/1 xfailed · kb 17 unit + 18 db · vitest 253 · typecheck/ruff/pyright clean · boundaries green. **Implementer miss caught in verification (disclosed):** the agent ran only the rag_agent tree and missed `confluence_sync/tests/test_chat_endpoint.py:770`, an audit-fingerprint test the token_subject change broke deterministically; main-window full-DB-suite verification surfaced it, assertion updated to the namespaced fingerprint. Files: auth_context.py, client.ts + 3 test files + docs/adr/0019.

### Tracked findings discovered mid-loop (for the audit wave)

- **FLAKE-1 (pre-existing, NOT caused by this pass):** `backend/app/features/confluence_sync/tests/test_versioning_failed.py` intermittently fails in the full DB suite ("staging produced no child chunks for page 3010") but passes in isolation and passed on the final full run; the failing test varied run-to-run — a shared-DB-state / per-test-rollback isolation flake in the ingestion tests, unrelated to any embed-security slice. Contradicts the matrix's CI-04 "deterministic fixtures = covered". Out of embed-security scope; flagged for auditor-6 (config/migration/CI) to confirm independently and for the owner to decide whether ingestion-test isolation is fixed here or tracked separately.

**S4 — migration-0010 deploy-readiness gate — DONE (committed).** Independent implementer; verified in the main window. Closed MIG-02: `check_deploy_readiness()` + `check-deploy-readiness` CLI phase on setup_supabase.py — read-only catalog check that both scope-RLS policies exist AS RESTRICTIVE FOR SELECT with RLS enabled, else fails loud (rc 10, "do not expose the reader path"). Asserts ENABLE not FORCE (per ADR-0013). Recorded 0010's local-inert / prod-mandatory status in docs/runbooks/deploy-readiness-scope-rls.md; no new ADR (0014 already owns the decision). 2 DB tests (ready + fails-closed, rolled back). **Gate:** deploy-readiness db 2 passed · backend unit 543 · boundaries green · ruff/pyright clean. Files: setup_supabase.py, test_deploy_readiness_check.py + docs/runbooks/deploy-readiness-scope-rls.md.

**S5 — regression-test coverage — DONE (committed).** 12 tests, ZERO production code changed. AUTH-6 (end-to-end /chat mews-vs-toast isolation, non-vacuous with a toast-token control), AUTH-7 (scoped search excludes a toast child from parent expansion), CIP-1 (body principal inert), CIP-3 (distinct subjects never share a cache entry), AUTHRT-2 (JWKS cached + finite timeout), AUTHRT-3 (missing sub/exp rejected), AUTHRT-4 (body principal can't split the rate-limit bucket), BIT-2 (token never in URL/history), BIT-9 (JWT never in console). CIP-2 already covered by S3. **Gate:** backend unit 543→548 · full backend db 271→278 · vitest 253→256 · typecheck/ruff clean · boundaries green. Meaningfulness of AUTH-6/AUTH-7 proven via a deleted scratch probe. Files: test_chat_endpoint.py, test_retrieval_knowledge_scope.py, test_answer_cache.py, test_token_verifier.py, loader.test.ts, iframe-bridge.test.ts.

- **FINDING-AUTH7 (design, for auditor-3 to weigh):** `HybridRetriever.fetch_parent_texts` sets the scope GUC to `'*'` (ADR-0014), so a parent chunk with a DIFFERENT scope tag than its authorized child IS surfaced to the generator. Cannot arise via normal ingestion (parent+child share the page's tags); safe because expansion only runs on already-scoped-authorized child ids (locked by the sibling test). Actual behavior pinned; theoretical concern recorded, not fixed (would require changing ADR-0014 design).

---

## Implementation phase (S1–S5) complete — commits

- e927e25 docs baseline + matrix
- 34efc45 SEC-S1 embed lifecycle & logout
- 26ced91 SEC-S2 production config guard
- 6816168 SEC-S3 identity namespacing + defense-in-depth (+ ADR-0019)
- 0a8aa67 SEC-S4 migration-0010 deploy gate (+ runbook)
- (this) SEC-S5 regression coverage

Full-suite state at phase close: backend unit 548 · full backend db 278 passed/1 xfailed · kb 17 unit + 18 db · frontend vitest 256 · typecheck clean · ruff/format clean · boundaries green · Playwright embed e2e 4 (from S1). Two open tracked findings carried into the audit wave: FLAKE-1 (pre-existing ingestion test flake) and FINDING-AUTH7 (parent-fetch scope-GUC opt-out).

## Wave 1 — First independent audit (2026-09-22)

Six independent adversarial auditors (none were implementers), each attacking one domain from code+tests only, told NOT to trust commit/docstring/ledger claims. Every finding then adversarially verified by a separate skeptic (default REFUTED without reproducible code evidence). Result: **15 CONFIRMED, 0 needs-investigation, 1 REFUTED** (22 agents).

**REFUTED:** ISO-AUTH-1 (high) — a claimed scope-derivation tenant-isolation bypass; the verifier disproved it from code.

### Triage (coordinator) → repair slices

- **CFG-A (HIGH) + CFG-B + CFG-C + CFG-H** — the SEC-S2 trust guard is FAIL-OPEN: `Settings.env` defaults to `'local'` → `is_offline_env()` True → `_reject_untrusted_active_platform` + zero-active guard SKIPPED when ENV is unset/forgotten in a real deployment; `allow_empty_platforms` alone also disables both guards regardless of env; the CFG-05 "aligned" comment is false for the unset-default case (backend default `local` vs frontend `NODE_ENV` fallback). → **R1** (settings fail-closed + doc). This is the top-priority fix — a security boundary defaulting open. Caught in my own SEC-S2 work by the audit.
- **AUTH-1 == CIP-A2 (MED)** — inactive platforms are not gated at the `/chat` backend path; `platform_for`/`.active` has zero call sites on the request path, so the documented two-tier model's access-gating half is unimplemented; deactivating a platform does not revoke backend scope. → **R2** (active-gate at the AuthContext boundary).
- **CIP-A1 (MED)** — the `integration` claim is resolved against a GLOBAL map with no issuer binding; any trusted issuer can claim any integration and get that tenant's scopes. Mostly mitigated today by R2's active-gate (only `datahub` active; as the hub it legitimately asserts product integrations; `mews`/`toast` inactive → gated out). Must be bound before `mews`/`toast` activate. → **R2** (per-platform allowed-integrations allow-list; `datahub`'s allowed set = OWNER DECISION, built to the design's mews/toast/opera-cloud default and flagged). 
- **BIT-A1 (MED)** — the SEC-S2 CSP localhost strip was applied only to `computeEmbedCsp`, not to the OTHER consumer of `activeDomains()`: `app/embed/page.tsx toOrigins()` still emits localhost origins (and fabricates plaintext `http://`) into the iframe-bridge allow-list in production. → **R3** (frontend CSP completeness).
- **CFG-D (HIGH)** — four duplicated db-test harnesses (`test_s_reader_role_usage.py`, `test_vector_data_nearest.py`, `test_vector_data_keyword.py`, `test_s_reader_curated_fetch.py`) omit the `_require_local_host` guard that was added after two live-Supabase incidents → they `drop_all`/`create_all` + provision a known-credential reader role on whatever DATABASE_URL resolves to. → **R4** (guard/consolidate harnesses). Live-data-loss risk; out of the embed core but serious.
- **CFG-E (MED)** — ROOT CAUSE of FLAKE-1: the duplicated session-scoped harnesses share one test DB + one lru_cache engine singleton with TRUNCATE-only (no per-test rollback) isolation → intermittent cross-test contamination. → **R4** (consolidate + deterministic per-test isolation).
- **CFG-F (LOW)** — CI coverage floor measures COLLECTED not EXECUTED tests (a `@pytest.mark.skip`'d security test still counts); CI is PR-only. → **R5** (CI skip/execution guard).
- **CFG-G (LOW)** — the SEC-S4 deploy gate is a hand-run CLI with no automated caller (no deploy pipeline exists to wire it into). → **R5** (accept + tighten the doc claim to "manual until a pipeline exists"; already close).
- **LC-F1 (LOW, missing-test)** — no composed embed-frame test for a scope-changing token renewal resetting the conversation (only the unit callback is asserted). → **R3**.
- **LC-F2 (LOW, missing-test)** — `decodeScope`/`decodeExpMs` are only tested against padded standard base64, never a real url-safe unpadded base64url JWT payload. → **R3**.

Repair slices R1–R5 follow (separate agents, failing-test-first). R1 and R4 carry the HIGH findings.

### Wave-1 repairs

**R1 — fail-closed trust boundary — DONE (committed).** Fixes CFG-A (HIGH) + CFG-B + CFG-C + CFG-H. `Settings.env` default `local`→`""` (unset ⇒ production); `_OFFLINE_ENVS` narrowed to `{local,test,ci}`; `offline=is_offline_env()` and `allow_empty=offline and allow_empty_platforms` (escape hatch can't relax the guard outside offline); false alignment comments corrected in settings.py + csp.ts. PROOF: `ENV=production` Settings() vs committed registry now RAISES on the datahub TODO placeholder. Blast-radius handled: conftest sets ENV=test; 4 pre-existing tests that relied on the CFG-C bug (built Settings(env="production")) given valid-prod registries (not weakened). 6 new fail-closed tests (TDD red first). **Gate:** backend unit 555 · full backend db 278/1xf · kb 35 · vitest 256 · typecheck/ruff/pyright clean · boundaries green. Residual for R3: frame-csp.test.ts stale comment re: matching backend _OFFLINE_ENVS.

**R2 — backend platform gating — DONE (committed).** AUTH-1/CIP-A2: `build_auth_context` now uses `platform_for` (active view) → `InactivePlatformError`/401 for an inactive platform (even general-only). CIP-A1: added `PlatformEntry.allowed_integrations` (per-platform allow-list, startup-validated); a token whose integration isn't in the issuer's list → `IntegrationNotAllowedError`/401. datahub→[mews,toast,opera-cloud] (**OWNER DECISION**, flagged in _readme, built to design), self-serving→own; platforms.local matched to test-hosts config.ts (locked by a test). 14 new tests; 7 pre-existing chat-endpoint tests repointed at a test registry (intent preserved, isolation assertion intact). **Gate:** backend unit 555→566 · db 278→281/1xf · vitest 263 · boundaries/typecheck/ruff/pyright clean.

**R3 — frontend CSP completeness + tests — DONE (committed).** BIT-A1: the SEC-S2 localhost strip reached only `computeEmbedCsp`, not `page.tsx toOrigins` (which built the bridge allow-list) — it emitted localhost + plaintext-http origins in prod. Fix: shared `effectiveEmbedderDomains()`/`toEmbedderOrigins()` in csp.ts used by BOTH (https-only for real domains outside local/dev; loopback only local/dev; fail-closed preserved). LC-F1 (composed scope-change reset test), LC-F2 (real base64url decoder tests), CFG-H residual (stale frame-csp comment corrected). 7 new tests. **Gate:** vitest 256→263 · typecheck clean · e2e 4.

**R5 — CI skip-guard + honest deploy-gate doc — DONE (committed).** CFG-F: ci.yml now fails on any unexpected skip/xpass/new-xfail (allowlisting the one known Planned worker xfail) and runs on `push:[main]` + `merge_group`, not only PRs. CFG-G: runbook states the deploy gate is MANUAL today (no pipeline) + where it must be wired; added a clearly-labelled local smoke step (not the gate). Validated locally: skip-guard exits 0 for `not db` (566/17) and `db` (281/1xf, known xfail allowed); ci.yml parses; smoke exits 0. Files: .github/workflows/ci.yml, docs/runbooks/deploy-readiness-scope-rls.md.

**R4 — test-harness live-host guard (CFG-D) + flake isolation (CFG-E) — RESET, re-running.** First attempt aborted mid-refactor when the subagent hit an account spend limit (external billing block), leaving a partial harness consolidation (an untracked `backend/db_test_harness.py` + a few half-converted files). The partial edits were DISCARDED to a clean base (R1's committed conftest restored); nothing broken was committed. Re-dispatched fresh from the clean base.

**R4 (retry) — DONE (committed).** CFG-D (HIGH): the `_require_local_host` guard was in 1 of 5 db harnesses; consolidated ALL five duplicated bootstraps into one shared `backend/app/tests/db_harness.py` (guard runs first, once, before any drop_all) + 4 guard tests (incl. patch-to-remote-host raises). CFG-E (FIXED): root cause was the DB-name CASCADE — each duplicated fixture re-derived the test-DB name from an already-mutated DATABASE_URL → 5 databases + 5 schema builds racing. Shared harness derives the name idempotently, builds once. **Validated:** full db suite 281 passed ×2 (main window) + subagent's 3 runs incl. reversed order; exactly ONE `omniboost_rag_test` DB remains. Isolation stays TRUNCATE (rollback not viable — reader is a separate role/engine needing committed data). **Gate:** backend unit 566→570 · db 281/1xf · guard 4 · boundaries/pyright/ruff clean. **FLAKE-1 RESOLVED** (root cause found + fixed).

---

## Wave-1 repairs COMPLETE (R1–R5) — commits

- c5112b2 R1 fail-closed trust boundary (CFG-A/B/C/H)
- 6f3c63c R2+R3 platform gating + integration binding + CSP completeness (AUTH-1/CIP-A2, CIP-A1, BIT-A1, LC-F1/F2, CFG-H residual)
- 17446a5 R5 CI skip-guard + honest deploy-gate (CFG-F/G)
- (this) R4 db-harness consolidation + flake fix (CFG-D/CFG-E)

**All 15 Wave-1 confirmed findings resolved** (1 was refuted at audit). Two open items remaining, both surfaced-and-dispositioned: FLAKE-1 → fixed by R4; FINDING-AUTH7 → pinned as documented ADR-0014 behavior (parent-fetch scope opt-out, bounded — the Wave-2 auditor will re-weigh). One OWNER DECISION outstanding: datahub `allowed_integrations` (built to design default, reversible config).

Full-suite state after Wave-1 repairs: backend unit 570 · full backend db 281 passed/1xf (deterministic, cascade gone) · kb 17+18 · frontend vitest 263 · typecheck clean · Playwright embed e2e 4 · boundaries green.

## Wave 2 — Fresh independent re-audit (2026-09-22)

Six FRESH auditors (none audited or implemented before), each: (1) confirm each Wave-1 fix holds by re-attacking the current code, (2) hunt regressions the repairs introduced, (3) re-sweep for new findings. Plus a cross-cutting completeness critic. Every new finding adversarially verified. Result: **42 fix-confirmations (39 fixed-confirmed, 1 n/a, 1 partially-fixed, 1 still-broken), 4 CONFIRMED new findings, 2 refuted, 0 needs-investigation** (12 agents). NOT a clean wave → repaired, clean-wave counter reset.

All Wave-1 core fixes independently CONFIRMED holding (fail-closed env, offline trust guard, token-verifier attack matrix, host-key, body-inertness, issuer-namespaced subject, active-gate, integration binding, CSP shared-helper, obi:clear lifecycle, flake fix, CI skip-guard). New findings (all repaired below):

- **CFG-D-KB-1 (HIGH, confirmed-defect):** SEC-R4 guarded the BACKEND db harnesses but the KNOWLEDGE-BASE db-test harnesses (7 suites) still `CREATE DATABASE` + reset the rag_reader password on any resolved host with NO live-host guard — same live-data risk R4 closed, in the tree R4 didn't touch.
- **CROSS-1 (HIGH, regression-from-repair):** the CI deploy-readiness smoke step SEC-R5 added crashes in CI — ENV is unset there (no .env), so R1's fail-closed default makes get_settings() raise on the datahub placeholder before the check runs. R5×R1 interaction.
- **BIT-A-R1 (LOW→real, potential-risk):** `isLocalhostDomain` matched only exact `localhost`/`127.0.0.1`; `::1`, the `127.0.0.0/8` block, and `0.0.0.0` slipped through into the prod trusted-embedder set.
- **AUTH-DOC-1 (LOW, doc):** two settings.py doc strings still listed `dev` as offline, contradicting the CFG-B fix.

REFUTED (2): held under adversarial verification. FINDING-AUTH7 was independently RE-WEIGHED by W2A3 and judged acceptably bounded (parent expansion only runs on already-scope-authorized child ids; a page's parent+child share tags).

### Wave-2 repairs (RW2) — DONE (committed)

- **CFG-D-KB-1 (HIGH):** added `knowledge-base/tests/_db_guard.py` (`require_local_host`, ADR-0018-clean COPY of the backend guard — KB imports nothing from backend) + `knowledge-base/tests/conftest.py` (autouse, db-gated fixture running BEFORE any harness bootstrap) + `test_db_host_guard.py` (6 tests). Negative proof: forcing a remote DATABASE_URL raises at setup before any CREATE DATABASE, verified against two harnesses. KB db 18 passed, KB unit 23, boundaries OK.
- **CROSS-1 (HIGH):** `.github/workflows/ci.yml` — added `export ENV=test` to the deploy-readiness smoke step so backend Settings resolves offline like every pytest step (no fail-closed crash on the placeholder registry). Verified the check exits 0 with ENV=test.
- **BIT-A-R1 (LOW):** `csp.ts isLocalhostDomain` broadened to the full loopback set (`localhost`/`*.localhost`, `127.0.0.0/8` strict numeric, `0.0.0.0`, `::1` bare+bracketed) while excluding hostnames like `127.example.com`; 10 new tests. vitest 264→274.
- **AUTH-DOC-1 (LOW, doc):** corrected the two stale `dev`-is-offline strings in settings.py to `local/test/ci` + noted dev/development are guarded.

**Combined gate:** backend unit 570 · kb unit 23 · backend db 281/1xf · kb db 18 · frontend vitest 274 · typecheck clean · boundaries OK.

## Targeted mutation testing (2026-09-22)

Deliberately broke each security boundary, one mutation at a time, confirmed the guarding test goes RED, reverted. **First attempt was INVALID and discarded:** the `isolation: worktree` agent created its worktree from the WRONG branch (`feat/rag-phase-3.5`, the pre-hardening base — a worktree can't reuse the branch checked out in the main tree), so it saw none of the SEC-* controls and reported 8 as "N/A — doesn't exist". Redone correctly IN THE MAIN TREE (correct branch, deps present) with per-mutation `git checkout` reverts + a final clean assertion.

Results (all on the correct branch):

| Boundary | Mutation | Detected? |
|---|---|---|
| Fail-closed env (CFG-A) | env default → "local" | RED ✓ (3 failed) |
| Active-gate (AUTH-1) | platform_for → by_issuer | RED ✓ (2) |
| Integration binding (CIP-A1) | skip allowed_integrations check | RED ✓ (1) |
| Issuer-namespaced subject (CIP-4) | return raw subject | RED ✓ |
| Deploy gate (MIG-02) | check_deploy_readiness return 10→0 | RED ✓ (1) |
| KB live-host guard (CFG-D-KB-1) | require_local_host no-op | RED ✓ (2) |
| principal-None invariant (CIP-5) | principal=None → non-None | RED ✓ (1) |
| BIT-7 token-string guard | drop the guard | RED ✓ (2) |
| Loopback strip (BIT-A-R1) | drop ::1 branch | RED ✓ (5) |
| obi:clear → restart (LC-1/4) | onClear no restart | RED ✓ (2) |
| scope-change → restart (LC-F1) | onScopeChange no-op | RED ✓ (1) |
| **Token web-storage WRITE (BIT-3/9)** | **sessionStorage.setItem** | **was GREEN → GAP FOUND** |
| host-key / origin / source / postMessage-'*' / scope-filter / scopes_for isolation / permission.allowed / body-scope / HS256 | (validated on identical code) | RED ✓ |

**GAP FOUND + FIXED:** the web-storage guard test spied only `Storage.prototype.getItem` (a READ); a `sessionStorage.setItem` WRITE went undetected. Added a content-based write-guard test (asserts `sessionStorage.length===0` + cookie unchanged + token genuinely handled). NOTE: the first fix attempt used `localStorage.clear()`, which is undefined in this jsdom env (a false red); corrected to a defensively-guarded sessionStorage/cookie content check. Re-verified: unmutated → full frontend suite 275 passed; mutated (setItem) → RED. HS256 note: the step-2 alg check is redundantly backstopped by `jwt.decode(algorithms=...)` at step 4, so the property (HS256 rejected) stays guarded either way.

**Outcome:** every targeted mutation is now caught. One real weak test found and sharpened — exactly what mutation testing is for.

## Wave 3 — Second fresh independent re-audit (2026-09-22)

Five fresh auditors + adversarial verify (14 agents). **35 fixed-confirmed, 2 partially-fixed, 8 confirmed new findings (1 MED + 7 LOW), 1 refuted.** NOT clean → repaired (SEC-RW3), counter still 0.

- **XCUT-1 (MED, confirmed-defect):** BIT-A-R1 broadened the FRONTEND loopback strip but the BACKEND trust guard (`_LOCALHOST_HOSTS`) still matched only exact localhost/127.0.0.1 → ::1/0.0.0.0/127.0.0.0-8/*.localhost passed the production issuer/JWKS+CSP guard. (The recurring fixed-in-one-place pattern.)
- **AUTHRT-REGISTRY-RELOAD (LOW):** platform registry re-read+re-validated per request.
- **TESTINFRA-1 (LOW):** 3 migration tests share a db name (safe only sequentially).
- **BIT-B1 (LOW, missing-test):** no loader-side storage-write guard.
- **AUTH-DOC-2 / XCUT-2 / CFG-DOC-1 (LOW docs):** stale doc strings (CFG-DOC-1 pre-existing, not from this pass).
- **AUTH7-REWEIGH (false-positive):** FINDING-AUTH7 independently confirmed bounded-safe again.
- REFUTED: 1.

### Wave-3 repairs (SEC-RW3) — DONE (committed)

- **XCUT-1:** broadened backend `_reject_untrusted_active_platform` to the frontend's full loopback set (`_is_loopback_host`/`_is_ipv4_loopback_host`; issuer/jwks + CSP domain; `_domain_host` port-strip fixed for `[::1]:3000`); rejection tests added. This also makes the csp.ts XCUT-2 docstrings accurate (backend now backs the frontend), so XCUT-2 needed no separate edit.
- **AUTHRT-REGISTRY-RELOAD:** process-level keyed registry cache (survives model_copy; fail-closed first-load preserved); cache tests added.
- **TESTINFRA-1:** unique migration db names (_migration_0007/0009/0010_test).
- **BIT-B1:** loader storage-write guard test (mutation-verified).
- **AUTH-DOC-2 / CFG-DOC-1:** doc strings corrected. Fixed an E501 my RW2 AUTH-DOC-1 edit introduced (rewrapped, keeps lint baseline).
- **AUTH7:** confirmed-safe; optional hardening deferred (would change ADR-0014 design for a non-vuln) → recorded in docs/future-ideas.

**Combined gate:** backend unit 566→590 · kb unit 23 · backend db 281/1xf · kb db 18 · frontend vitest 275→276 · typecheck/ruff clean · boundaries OK.

## Wave 4 — Third fresh independent re-audit (2026-09-22)

Five fresh auditors + verify (9 agents). **40 fixed-confirmed, 0 still-broken, 2 CONFIRMED actionable (both LOW), refuted others.** NOT clean → repaired (SEC-RW4), counter still 0. The findings are the audit tail — increasingly esoteric loopback edges, both defense-in-depth-only (no corpus/scope bypass):
- **CFG-DOMLOCAL-1 (LOW):** backend guard rejected `.local` as issuer/jwks host but NOT as a CSP domain (internal asymmetry).
- **BIT-LOOPBACK-EDGE-1 (LOW):** loopback aliases (trailing-dot FQDN, expanded IPv6 `0:0:0:0:0:0:0:1`, IPv4-mapped `::ffff:127.0.0.1`) unmatched on BOTH sides (consistent, not a repair regression).

### Wave-4 repair (SEC-RW4) — DONE (committed)

Closed BOTH comprehensively + symmetrically to end the alias tail: `.local` now rejected as a CSP domain too (backend) + stripped (frontend); both matchers broadened (line-for-line equivalent, hand-rolled IPv6 expander, no new dep) to cover the full alias set, verified NOT over-matching real hosts (127.example.com, example.local.com, ::ffff:8.8.8.8, real IPv6). 34 tests (failing-first). **Gate:** backend unit 590→616 · backend db 281/1xf · kb 23+18 · frontend vitest 276→284 · typecheck/ruff/pyright clean · boundaries OK.

## Wave 5 — CLEAN (consecutive-clean #1) (2026-09-22)

Five fresh auditors + verify. 4 domains (browser/CSP, authz/identity/lifecycle, test-infra/CI, cross-cut) returned detailed CLEAN confirmations — no actionable finding survived, all fixes confirmed holding and the frontend/backend twins verified line-for-line equivalent, no SEC-RW4 regression. The auth/config auditor (W5A1) returned a DEGENERATE response (a StructuredOutput hiccup — "test minimal submission"), so that domain was RE-RUN STANDALONE (prose) to avoid counting a clean result on a domain that didn't genuinely audit. The standalone auth/config re-audit ran a full adversarial probe — forged-token matrix (HS256 downgrade, alg=none, unknown iss, wrong aud, expired, over-lifetime, missing claims, forged sig all rejected; only the valid token accepted), `model_copy` cache attacks (no stale/wrong registry; no offline→prod leak; no first-load bypass), and loopback/.local matcher fuzzing (full alias set rejected, real hosts + `::ffff:8.8.8.8` + `127.example.com` not over-matched) — and returned **CLEAN**. Live bonus evidence: the SEC-R4/CFG-D DB guard correctly REFUSED to run against the repo `.env`'s remote Supabase DSN (the guard working). One informational non-actionable note: non-canonical IPv4 short-forms (`127.1`, packed-decimal `2130706433`) aren't matched — by-design, operator-config-only, parity with the frontend twin maintained; not a finding.

**Wave 5 = CLEAN. Consecutive-clean counter: 1 of 2.**

## Wave 6 — Fresh independent re-audit (2026-09-22) — NOT CLEAN → counter reset

Re-run after the prior session's Wave-6 auditors were all killed mid-run by an account spend limit (the returned `clean:true` was spurious — 0 of 5 agents completed). Five FRESH independent auditors (none implemented; conclusions from current code only, NOT from commit/ledger/loop-log/matrix prose; every finding adversarially verified, default REFUTED without reproducible evidence): (1) auth & host-key & production-config red team, (2) browser & iframe token security, (3) authorization + retrieval isolation + Confluence/identity + server-side lifecycle, (4) config/migration/CI/test-infra integrity, (5) cross-cutting completeness critic. Code UNCHANGED since Wave 5 (HEAD 54370d3). Gate re-verified independently in the main window before the wave: backend unit 616 · kb unit 23 · backend db 281/1xf · kb db 18 · frontend vitest 284 · typecheck/boundaries clean.

Four auditors returned detailed CLEAN with strong code-anchored disproven-attack lists (crafted RS256/HS256/`none` tokens + a 26-case loopback matrix agreeing across both twins + empirical `ENV=production` fail-closed on the datahub placeholder; DB-level RLS isolation exercised 305 non-db + 29 db green on the pinned local DB, AUTH7 re-confirmed bounded-safe from ingestion code; both DB harnesses guard before bootstrap, CI skip-guard enumerated to the single allowlisted xfail). The cross-cut critic returned an overall-CLEAN security verdict but **one new actionable LOW finding**, so the wave is **NOT clean** and the consecutive-clean counter **resets to 0**.

- **W6-5-L1 (LOW, confirmed-defect + twin-divergence):** the backend IPv4-octet numeric check used `str.isdigit()`, True for non-ASCII digits (Arabic-Indic `٥`, fullwidth `１`, superscript `²`) that the frontend twin's ASCII-only `/^\d{1,3}$/` rejects. Reproduced live in the main window: `_is_loopback_host("127.0.0.٥")` → `True` on the backend but the frontend classifies it non-loopback (a divergence of the two loopback matchers — the exact recurring bug the twins were written to close); `_is_loopback_host("127.0.0.²")` → unhandled `ValueError` (`int("²")`) at production-registry load instead of the intended "not a trusted issuer" rejection. Both fail-closed and operator-config-only (the matcher runs only on `offline=False` registry load over operator-edited `platforms.json`, never on a request path), hence LOW — but a genuine actionable defect and a stated-invariant violation.

### Wave-6 repair (SEC-RW6) — DONE (committed 2d23900)

Confirmed by the coordinator via direct reproduction, then repaired failing-test-first (done in the main window rather than a separate repair subagent — disclosed deviation, forced by the same spend-limit that has repeatedly killed subagents; independence is still supplied by the mandatory FRESH re-audit waves that follow, and the loopback code's original implementer was the SEC-RW4 subagent, not the coordinator). Fix: ASCII-only octet check (`o.isascii() and o.isdigit()`) at both octet sites in `platforms.py` (`_is_ipv4_loopback_host` and the IPv4-mapped branch of `_expand_ipv6`), mirroring the frontend's `/^\d{1,3}$/`. 6 new backend tests (direct matcher parity + registry-load, red-before/green-after) + 1 frontend parity test pinning the same invariant on the twin. Real hosts and every valid loopback form unaffected. **Gate:** backend unit 616→622 · full backend db 281/1xf · kb 23+18 · frontend vitest 284→285 · typecheck/ruff/pyright clean · boundaries OK.

**Consecutive-clean counter: 0 of 2.** Two fresh clean waves are now required again (Waves 7 and 8).

## Wave 7 — Fresh independent re-audit (2026-09-22) — NOT CLEAN → counter stays 0

Five FRESH independent auditors on HEAD f5582fe (post-SEC-RW6), same five domains, each told to FIRST prove the SEC-RW6 loopback fix holds with no regression, THEN re-sweep the complete core; conclusions from code only, adversarial, default-REFUTED. Gate re-verified before the wave: backend unit 622 · kb 23 · backend db 281/1xf · kb db 18 · frontend vitest 285 · typecheck/boundaries clean.

Three domains (browser/CSP, authz+identity+lifecycle, config/migration/CI/test-infra) returned detailed CLEAN — SEC-RW6 confirmed backend-only and non-vacuous (the auditor reproduced the revert: the 6 W6-5-L1 tests go red), csp.ts unaffected and correct, RLS isolation re-proven on the local DB, both DB harness guards precede bootstrap, CI skip-guard tied to the single allowlisted xfail, coverage floor 945≫625. The auth/host-key auditor and the cross-cut critic each surfaced one item:

- **W7-A1-1 (LOW, confirmed twin-divergence + missing-test):** the backend `_is_loopback_host` unconditionally `.strip()`s the extracted host, so `[ ::1]` / `[::1 ]` / `[ ::ffff:127.0.0.1]` / `[ 127.0.0.1]` / `127.0.0.1 :80` (whitespace INSIDE the value) classify as loopback on the backend, but the frontend twin `isLocalhostDomain` (csp.ts) never re-trimmed the bracket/plain-host extraction → it classified them as non-loopback. A twin-invariant violation (the two matchers must agree). Confirmed by the coordinator: the backend returns loopback=True for all five, the frontend returned false before the fix. NOT a live bypass — the backend is the stricter, fail-closed side (rejects the platform at registry load) and `[ ::1]` is not a browser-matchable origin — but actionable, so the wave is NOT clean.
- **classify_scope note (cross-cut, potential-risk → DISPROVEN for v1):** `permission.py:classify_scope` uses bare `str.isdigit()` then `int()`, the same crash class as W6-5-L1 (`int("²")` raises). The coordinator independently traced reachability and DISPROVED it for v1: the only live caller is `answer_service` `scope = auth.principal`, hardcoded None on all three AuthContext branches; body principal is inert and numeric-rejected (`_reject_numeric_principal`). So `classify_scope` only ever sees None in v1 → `(None, None)`, no `int()`. Not an actionable v1 finding, but a latent future-phase crash — hardened proactively (see below) rather than deferred, to kill the whole `isdigit→int` class in one slice.

### Wave-7 repair (SEC-RW7) — DONE (committed ea9f33b)

Both repaired together (failing-test-first; done in the main window, same disclosed spend-limit deviation as SEC-RW6, independence supplied by Waves 8+9). W7-A1-1: `host.trim()` after extraction in csp.ts, mirroring the backend's unconditional strip — verified both twins now agree loopback=True on all five malformed forms; 1 frontend parity test. classify_scope: `isascii() and isdigit()` (behaviour-preserving — real space-ids are ASCII decimal), 4 backend tests (superscript/Arabic/fullwidth/mixed). The other three `isdigit` sites were reviewed and left: `run_baseline.py` (isdigit-then-string-compare, no `int()`, eval harness), `setup_supabase.py` (parses the DB's own trusted pgvector version, operator tool), `_reject_numeric_principal` (isdigit-then-raise, no `int()`, over-broad rejection is the safe direction) — none are the crash class. **Gate:** backend unit 622→623 · full backend db 281/1xf · kb 23+18 · frontend vitest 285→286 · typecheck/ruff/pyright clean · boundaries OK.

**Consecutive-clean counter: still 0 of 2.** Waves 8 and 9 must both be clean.

## Wave 8 — Fresh independent re-audit (2026-09-22) — NOT CLEAN → counter stays 0

Five FRESH auditors on HEAD fa6ccf6 (post-SEC-RW7). Because Waves 6 and 7 each found one more esoteric loopback-parity edge, this wave was directed to END the tail: the auth auditor and the cross-cut critic each ran a LARGE cross-runtime differential of the loopback twins (both real runtimes executed — backend via `uv run python`, frontend csp.ts via `node --experimental-strip-types`), and the cross-cut critic additionally enumerated EVERY `isdigit`/`int()` site to confirm that class is closed. Gate re-verified before the wave: backend unit 623 · kb 23 · backend db 281/1xf · kb db 18 · frontend vitest 286 · typecheck/boundaries clean.

Three domains (browser/CSP, authz+identity+lifecycle, config/migration/CI/test-infra) returned detailed CLEAN — the SEC-RW7 trim verified a strict no-op on well-formed inputs and the exact twin of the backend strip; the classify_scope change verified behaviour-preserving and strictly fail-closed and unreachable in v1; RLS isolation re-proven on the local DB; both DB guards precede bootstrap; CI skip-guard tied to the single allowlisted xfail; RW6/RW7 tests revert-simulated as non-vacuous. The two differential auditors BOTH found the same one finding:

- **W8-A1-1 (LOW, confirmed twin-divergence + missing-test):** Python `str.strip()` and JS `String.prototype.trim()` remove DIFFERENT edge whitespace — they disagree on exactly six code points: Python-only U+001C-U+001F + U+0085, JS-only U+FEFF. So the backend `_is_loopback_host`/`_domain_host`/`_is_dot_local_host` (`.strip()`) and the frontend `isLocalhostDomain` (`.trim()`) classified a host carrying one of those six oppositely (e.g. `localhost<BOM>` slipped past the backend production trust guard while the frontend stripped it as loopback). TWO independent auditors ran independent differentials (3,779 and 3,137 inputs) and converged on the IDENTICAL six-char set, and every divergence in both corpora contained one of those six chars — so the divergence set is complete. LOW/fail-closed/operator-config-only (platforms.json is operator-edited, never request input), but a twin-invariant violation and the ROOT of the recurring tail rather than another leaf.

### Wave-8 repair (SEC-RW8) — DONE (committed 8173a0c)

The definitive tail-ender: instead of patching six more characters, both twins now strip ONE shared explicit union set of every code point either runtime strips — backend `_EDGE_WHITESPACE`/`_strip_edges`, frontend `EDGE_WHITESPACE`/`stripEdges` — replacing bare `.strip()`/`.trim()` at all host-matching sites. The set is the EXACT union (U+200B, stripped by neither, is excluded and pinned by a not-over-stripped test). Verified equivalent by the coordinator's OWN cross-runtime differential: 3,993 inputs (every whitespace/control/format code point <= U+FFFF x 10 loopback/non-loopback bases), backend (Python) vs the real csp.ts (node) — **0 divergences** (was 149 before). 8 new backend + 2 new frontend tests, red-before-green. Failing-test-first; done in the main window (same disclosed spend-limit deviation; independence from Waves 9+10). **Gate:** backend unit 623->630 · full backend db 281/1xf · kb 23+18 · frontend vitest 286->288 · typecheck/ruff/pyright clean · boundaries OK.

The `isdigit`/`int()` class was independently confirmed fully closed by the cross-cut critic's site-by-site enumeration (every other site is SAFE: no `int()`, or ASCII-guarded, or fail-closed-reject). With both the digit class and the whitespace-strip class now closed by construction, the loopback-parity tail should be exhausted.

**Consecutive-clean counter: still 0 of 2.** Waves 9 and 10 must both be clean.

## Wave 9 — CLEAN (consecutive-clean #1) (2026-09-22)

Five FRESH auditors on HEAD 201de7f (post-SEC-RW8). Gate re-verified before the wave: backend unit 630 · kb 23 · backend db 281/1xf · kb db 18 · frontend vitest 288 · typecheck/boundaries clean. All five returned CLEAN:

- **Browser/CSP:** independently proved `EDGE_WHITESPACE` is a strict SUPERSET of JS `trim()`'s set (0 chars missing) → no classification can regress; full token surface holds. One item examined and dismissed as build-config, not a code defect (OBI_ORIGIN dev fallback).
- **Authz/identity/lifecycle:** all 6 isolation attacks refuted with reproduction; RLS exercised on the local DB (306 non-db + 33 db); AUTH7 re-confirmed bounded-safe with fresh ingestion evidence; classify_scope confirmed safe on non-ASCII/None.
- **Config/migration/CI/test-infra:** suite counts confirmed (630/288); SEC-RW8 revert-simulated as non-vacuous and confirmed a strict tightening (no rejection weakened); both DB guards precede bootstrap; CI skip-guard tied to the single allowlisted xfail; coverage floor satisfied; docs consistent.
- **Auth/host-key + differential:** a 21,740-input cross-runtime differential (both real runtimes) → 0 divergences; full JWT/host-key/config attack matrix refuted. Raised ONE observation, **W9-A1-OBS**, which it explicitly labelled "NOT a defect": a LOW drift-prevention missing-test — parity is enforced only by parallel per-side tests, not a mechanized CI differential, so a future one-sided edit could reintroduce divergence and pass both suites.
- **Cross-cut completeness critic:** two differentials totalling 856,643 inputs (full BMP sweep + astral chars + interior-substitution stressing `.lower()`/`.toLowerCase()` case-folding and `int()`/`Number()` parsing) → 0 divergences; enumerated every other backend↔frontend twin (active-domain list = parity; env detection = deliberate documented non-twin, fail-closed both sides; base64url client decode = display/renewal-only, not a trust twin; DB live-host guard = parity copy per ADR-0018); vacuous-test checks empirically confirmed non-vacuous. Explicit conclusion: **"The audit tail is closed. No confirmed-defect, no missing-test, no doc-defect, no actionable potential-risk found."**

**Triage of W9-A1-OBS → NON-ACTIONABLE.** (1) Its finder classified it "NOT a defect / drift-prevention, not a live hole." (2) Loopback-twin equivalence is proven across ~882,000 inputs in three independent differentials this wave (21,740 + 856,643 + the coordinator's earlier 3,993), all 0 divergences. (3) The parity behaviour is covered by non-vacuous per-side tests (two auditors confirmed revert→red empirically). (4) The dedicated completeness critic — the auditor whose remit IS missing-tests/drift — independently concluded there is NO missing test and the tail is closed. (5) Clean-exit criteria for the parity are met: tested (not doc-only), mutations caught, no crit/high/med. A mechanized cross-runtime CI differential is a defense-in-depth infra enhancement, not a requirement-coverage gap — recorded in `docs/future-ideas.md` (loopback-twin-differential-ci) as an optional deferred item for the owner to weigh, exactly as AUTH-7's optional hardening was handled.

**Wave 9 = CLEAN. Consecutive-clean counter: 1 of 2.** Wave 10 must also be clean to meet the mandate's two-consecutive-clean exit.









