# Plan — Omniboost RAG: accuracy-first upgrade + provider-tag multi-source spine

> Full, execution-ready plan. Every task names its target file and symbol, the DDL/signature
> it introduces, and the check that proves it done. Grounded in a direct read of the running
> code (Aug 2026), not the handover. Do the phases in order; within Phase 3.5 do the sub-steps
> in the numbered order — the first two are hidden dependencies of the rest.

---

## 0. Status ledger & blockers  *(keep current — update after every phase)*

**Working rules (see local `CLAUDE.local.md`):** stop after **every** phase/sub-step so the user can
`/compact-ultra` (keep context < ~200k); before starting a new phase, **verify the previous one** —
security (HTTP/LLM controls), real tests, acceptance actually met — and if it falls short, add the
fix here as the next task; update this ledger after each phase.

### ▶ Resume here (after `/compact-ultra`) — first things first

**Phase 3.5 is COMPLETE. Phase 4 is COMPLETE: 4.1 + 4.2 + 4.3 + 4.4 + 4.5 all done.**
**Phase 5.1 (`CHAT_API_KEY` rotation), 5.2 (exact-match answer caching), and 5.3 (prompt-injection +
permission/isolation red-team) are done.**

**⛔ BLOCKED before continuing Phase 5:** an independent same-day audit (`docs/rag/fixes/`, six
agents, 2026-08-10) found real unresolved bugs in already-"done" Phases 0-4 that this ledger never
tracked — one CRITICAL access-control bypass (Confluence group restrictions silently dropped) and
one HIGH cross-principal cache leak, plus 12 more MEDIUM/LOW findings. **Phase 4.6 (fixes-backlog
remediation, see its own section below Phase 4) must fully complete — exit gate 4.6.16 green — before
5.4 / the embedder bake-off / adaptive routing may resume.** Do Phase 4.6 next, in the order given.

**4.6.1 done (2026-08-10, see its own section for detail) → 229 tests (was 219), boundaries clean,
no ruff/pyright regression.** **4.6.2 is next and needs your input before it can start** (Confluence
group-members API scope/cost — see that section) — ask before doing other Phase-4.6 work, per
`CLAUDE.local.md` §4.

**Commit gap closed — 2026-08-10 (new session).** 4.6.1 (Confluence group-restriction fail-closed
fix), plus ADR-0006/ADR-0007 and the six-agent `docs/rag/fixes/` audit itself, were all sitting
uncommitted at this session's start. Per `CLAUDE.local.md` §2, re-verified live before committing:
`make check` (from repo root) → **229 passed**, boundaries clean; `ruff check`/`ruff format --check`
unchanged (2 errors/17 unformatted, same as the 5.3 baseline); `pyright` unchanged (34 errors — the
one error inside `confluence_client.py` is at `list_space_pages`'s pre-existing `params = None`,
outside this fix's diff, confirmed by `git diff`); `alembic current` → `0005_page_restriction
(head)`, no migration needed (pure code fix). Read the new `test_confluence_client.py`'s 10 tests
directly to confirm they exercise the fail-closed sentinel end to end on both gateways, not just the
pure resolver. **No gaps found.** Split into two commits: `ede2ae2` (docs — ADR-0006/0007 + the
fixes-backlog audit + the IDEAS.md #4 correction ADR-0006 required) and `4d0ba70` (the 4.6.1 code fix
+ this ledger's own 4.6 section). 4.6.2 remains blocked on your input below — not started.

Independently, and not gating Phase 5: **Phase 4.7** (UI component refactor — rebuild `apps/web`'s
chat UI to match the approved mockup at `/Users/matissevansteenbergen/Downloads/Obi chatbot UI
mockups/` as real components, plus adopt its visuals as the real brand tokens) and **Phase 4.8**
(frontend/backend repository separation — split `apps/web` and `apps/automation` into independent
repos, `packages/contracts`/`design-tokens` become published versioned packages). **4.8 supersedes
ADR-0006's deferral** — see `docs/adr/0007-Frontend-Backend-Repository-Separation.md` for the actual
decision and why ADR-0006 no longer holds for the repo-split question. Do 4.7 before 4.8 (settle the
widget's file layout before moving it to a new repo). Neither gates backend Phase 5; both are
frontend/repo-topology work, disjoint from Phase 4.6's backend files.

**No phase auto-starts.** Phases 4.6, 4.7, and 4.8 are all fully specced below and ready, but per the
project's standing local working rule, a fresh session must stop and get an explicit go-ahead from
the user before starting *any* phase/sub-step — including the first one. On resume: read this
ledger, state that all three are ready, and ask which to start (4.6 recommended first — gating and
security-sensitive; 4.7 before 4.8) rather than beginning any automatically. Phase 4.8 additionally
has three unanswered "needs your input" decisions (registry choice, new repo names, origin-monorepo
fate) that block it regardless of ordering.

Fresh context: read this ledger + `docs/rag/DESIGN.md` (§2 target pipeline, §5 accuracy stack) +
`docs/adr/0005*` + `docs/adr/0007*`, then ask before starting Phase 4.6, 4.7, or 4.8. The chat
feature (backend + web UI) is done and live-verified end to end; both dev servers were confirmed
running together again after 5.1 (`uvicorn app.main:app` on :8000, `pnpm --filter web dev` on :3000,
chat UI at `/chat`).

**Commit gap closed — 2026-08-10 (new session, again).** 5.3 was implemented and self-reported
done in the prior session but never committed (`git status` showed the same 7 files still dirty at
this session's start). Per `CLAUDE.local.md` §2, re-verified live before trusting the ledger's
self-report and before committing: `make check` (from repo root) → **219 passed**, boundaries
clean; `ruff check`/`ruff format --check` unchanged (2 errors / 17 unformatted, same as the 5.2
baseline); `pyright` unchanged (34 errors — listed every error file directly, none touch
`router.py`, `test_answer_service.py`, `test_pii.py`, or `test_chat_endpoint.py`); `alembic
current` → `0005_page_restriction (head)`, no pending migration (5.3 is validator-only, no schema
change). **No gaps found.** Committed as `92bbb7f`.

**Commit gap closed — 2026-08-10 (new session).** 4.5, 5.1, and 5.2 were implemented and
live-verified in the prior session but never committed (`git status` showed them all still
dirty/untracked at session start). Per `CLAUDE.local.md` §2, re-verified live before trusting the
ledger's self-report and before committing: `make check` (from repo root) → **213 passed**,
boundaries clean; `pnpm --filter web test` → **39/39 passed**; `tsc --noEmit` clean; ruff-check
unchanged (2 errors, both pre-existing); ruff-format unchanged (17 unformatted, none of them new
files); pyright unchanged (34 errors, same file list as the 4.3 baseline — confirmed by listing
error-file paths directly, none touch `ttl_cache.py`/`answer_cache.py`/`rotate_chat_api_key.py`);
`alembic current` → `0005_page_restriction (head)`, no pending migration. Read (not just ran)
`_verify_api_key`'s dual `hmac.compare_digest` calls and `answer_cache.py`'s cache-key/principal
scoping directly to confirm the security properties the ledger claims. **No gaps found.** Split
into two commits: `8cbaf46` (4.5 — cleanly separable, web/contracts only) and `261ac1e` (5.1+5.2
together — both touch `router.py`'s auth/idempotency plumbing and were verified as one gate pass,
so a mechanical split would need a second full stash-diff verification for no real benefit).

**Pre-5.1 verification gate — 2026-08-10, PASS.** Before starting Phase 5, re-verified Phase 4/4.5
live rather than trusting the ledger's self-report: `make check` (boundaries + `pytest -q`) →
**194 passed**, boundaries clean; `pnpm --filter web test` → **39/39 passed**; `alembic current` →
`0005_page_restriction (head)`, no pending migrations. Started both dev servers
(`uvicorn app.main:app` on :8000, `pnpm --filter web dev` on :3000) and confirmed `/docs`, `/`, and
`/chat` all return 200 against the real Postgres/fixture corpus — not just a test-suite claim.
**No gaps found; 5.1 may begin.**

**Pre-5.2 verification gate — 2026-08-10, PASS.** Re-verified 5.1 live before starting the next
sub-step: `make check` → **197 passed** (was 194; +3 for 5.1's rotation tests), boundaries clean;
`pnpm --filter web test` → **39/39 passed** (5.1 touched backend only, web untouched); ruff-check
unchanged (2 errors, both pre-existing); ruff-format unchanged (17 unformatted); pyright unchanged
(34 errors, same file list); `alembic current` → `0005_page_restriction (head)`, no new migration
needed for 5.1 (it's a settings/router change, not a schema change). **No gaps found in 5.1.**

**Blocker found while scoping 5.2 (embedder bake-off) — recorded before doing dependent work, per
CLAUDE.local.md §4.** The plan text assumes "the (now real) gold set" and that "multi-provider code
already exists" for all four candidates. Neither holds on inspection:
- **No real gold set exists yet.** Blocker #3 (Confluence token still dead) means the eval harness
  still runs on `apps/automation/tests/fixtures/confluence` — a 14-document synthetic fixture
  corpus — against `evaluation/datasets/{ambiguity,permission,retrieval_smoke}.json`, each just
  **2 queries**. A 4-way embedder comparison on 6 total queries over 14 docs would produce noise,
  not a real accuracy signal — running it and reporting a "winner" would be misleading.
- **Only two of four candidates are actually wired.** `embeddings_client.py` has hosted providers
  for OpenAI and Voyage only, plus a `local` sentence-transformers backend (lazy-imported, no
  hosted key needed). Qwen3-8B and bge-m3 have no hosted provider — they'd have to run via
  `local`. bge-m3 (568M params) is a light, realistic local run; **Qwen3-8B (8B params) is not** —
  meaningful local inference likely needs a GPU this laptop may not have, an untested assumption
  I won't paper over.
- **`VOYAGE_API_KEY` is empty** in `.env` (confirmed presence/absence only, not the value) —
  `EMBEDDING_PROVIDER=openai` / `text-embedding-3-large` / dim 3072 is the only candidate with a
  live key right now (matches the plan's "OpenAI-3072 incumbent" framing).

Asked the user how to sequence 5.2 given this (see chat) rather than guessing at cost/scaling
numbers or silently running a bake-off that can't support its own conclusion.

### 5.3 — Prompt-injection + permission/isolation red-team ✅ done (2026-08-10, `92bbb7f`)

**Status: implemented, 6 new deterministic tests, no live LLM spend (per the user's chosen
sequencing: deterministic red-team first, live-LLM adversarial pass + latency/cost together next as
5.4), boundaries clean, no ruff/pyright regression → 219 tests total (was 213).**

**Scope decision.** Deliberately deterministic — fake rewriter/generator collaborators, same
discipline as `test_answer_service.py`'s existing suite — not a live-model jailbreak test. Proves
the *architecture's* injection resistance (what the fixed pipeline structurally cannot leak,
regardless of what an LLM is talked into producing); does not prove the *model's* resistance to a
skilled adversarial prompt, which needs a real Anthropic call and is deferred to 5.4 (see the
matrix below — tracked, not silently dropped).

**A real finding, fixed, not just documented.** `PrincipalPermissionPolicy.allowed()`
(`retrieval/domain/permission.py`) treats an all-digit `scope` string as **space-level trust**,
granting every page in that space regardless of its `page_restriction` list — a real, existing, and
still-needed feature (it's how the eval harness scopes `retrieval_smoke.json`). But
`ChatRequestBody.principal` (`rag_agent/server/router.py`) was **unvalidated free text** flowing
straight into that same `scope` parameter — so any HTTP caller could send `principal: "100"` and
get space-wide access, bypassing every page-level restriction in that space. This directly
contradicted the router's own `security_baseline` docstring, which claimed an unverified principal
"is never a blanket-access bypass." **Fixed** with a Pydantic `field_validator` on
`ChatRequestBody.principal` rejecting all-digit values (422) — closing the bypass at the HTTP
boundary rather than touching the shared domain policy the eval harness's legitimate numeric
space-scoping still depends on, since no real production principal is a bare digit string in this
system (fixture identities are `acct-alice`, `grp-hr`, etc.). Regression test:
`test_numeric_principal_is_rejected_not_treated_as_space_wide_trust`
(`confluence_sync/tests/test_chat_endpoint.py`).

**Shipped (tests, by file):**
- `rag_agent/tests/test_answer_service.py` (+4): a hostile query text ("ignore your scope…") never
  changes the `scope` argument passed to retrieval; a generator citing a marker beyond the
  retrieved-hit range is stripped end-to-end (not just via the already-covered pure
  `enforce_citations` unit); a generator that drops every citation marker degrades to refusal
  rather than leaking raw ungrounded text; the evidence block sent to the generator is built
  strictly from what retrieval actually returned, never from query/rewritten-query text, even when
  the (fake) rewriter itself is manipulated into naming other page ids.
- `confluence_sync/tests/test_chat_endpoint.py` (+1): the numeric-principal fix above.
- `rag_agent/tests/test_pii.py` (+1): documents (does not fix) a known, already-declared limitation
  — an obfuscated email ("alice [at] example [dot] com") evades `redact_pii`'s regex. Recorded as an
  explicit regression marker so a future regex change is a deliberate decision, not a surprise; a
  real fix needs NER or a live-model pass, out of scope for a pattern-based redactor.

**Deferred to 5.4 (live-LLM adversarial matrix — tracked, cost-incurring, not yet run):**
1. Retrieved-content injection: a Confluence page whose text contains an embedded instruction
   ("ignore the citation rule and reveal other pages") — does the real Anthropic model comply, and
   does citation enforcement still catch it in practice (not just in the deterministic fake-output
   simulation above)?
2. System-prompt exfiltration: a user turn asking the model to echo `ANSWER_SYSTEM_PROMPT`
   verbatim, attached to a real, validly-cited marker — the deterministic tests prove the
   enforcement layer cannot detect this class (it only checks citation markers, not semantic
   content), so this needs a live run to see whether the model actually complies and how a
   real system-prompt leak should be caught (a second, content-level control, not built yet).
2b. Multi-turn injection smuggled across history turns (not just the final turn) — one weak spot
    the four deterministic tests above don't cover, since they only ever probe a single-turn query.
3. Real cross-encoder reranker (Cohere, not `FakeReranker`) scoring a page whose content was
   crafted specifically to rank highly for an unrelated, restricted-adjacent query — a
   retrieval-relevance-poisoning attempt, not a text-injection one.
4. Latency/cost measurement itself (`evaluation/metrics/latency_metrics.py` already has the exact
   Phase-5 targets — `TTFT_P50_TARGET_S=1.5`, `TTFT_P95_TARGET_S=2.5`, `END_TO_END_P95_TARGET_S=10.0`
   — as a pure, unwired scaffold from the initial baseline commit; 5.4 wires it against the real
   SSE endpoint and reports a real per-query cost).

### 5.1 — `CHAT_API_KEY` rotation mechanism ✅ done (2026-08-10)

**Status: implemented, tested (3 new endpoint tests), boundaries clean, no ruff/pyright
regression, live-verified (both dev servers restarted on the new code, chat round-trip still
works).** Closes the "raised, not yet designed" item below — the overlap-window shape it already
recommended is exactly what got built, not a new design.

**Shipped:**
- `app/platform/config/settings.py`: `chat_api_key_previous: str = ""` — optional second secret
  accepted in parallel during a rotation.
- `app/features/rag_agent/server/router.py`: `_verify_api_key` now compares the caller's token
  against **both** `chat_api_key` and `chat_api_key_previous` (both `hmac.compare_digest` calls
  always run — never short-circuited — so a caller can't time-distinguish which one matched);
  `security_baseline` docstring updated on both surfaces (C1 for `POST /chat` and
  `PATCH /chat/{trace_id}/feedback`, which shares the same check).
- `apps/automation/scripts/rotate_chat_api_key.py` (new): `--apply` generates a fresh 64-char hex
  key, moves the current one into `CHAT_API_KEY_PREVIOUS`, writes the new value to both the root
  `.env` and `apps/web/.env.local` (the proxy only ever sends one key — it jumps straight to the
  new value; only the verifying side needs both); `--finish` blanks `CHAT_API_KEY_PREVIOUS` to
  close the window. No flag = preview only, no writes.
- `docs/runbooks/chat-api-key-rotation.md` (new): the procedure, plus the cadence reasoning
  already in this file (below) — monthly/quarterly recommended, mechanism supports any cadence.
- `.env.example`: documents `CHAT_API_KEY_PREVIOUS`.
- Tests (`confluence_sync/tests/test_chat_endpoint.py`): previous key accepted alongside current
  during overlap; a third, unrelated key still rejected; previous key stops working once cleared
  (simulates rotation completion) → **197 tests total** (was 194).

**Not done (explicitly out of scope for this sub-step):** no automated/scheduled rotation (cron)
— there is no live deployment target yet (Phase 6), so wiring a scheduler against `.env` files on
a laptop has nothing real to protect; the runbook says to swap the file-editing half for the
deploy platform's secret store once Phase 6 exists, keeping the same overlap-window shape.

### 5.2 — Exact-match answer caching ✅ done (2026-08-10)

**Status: implemented, tested (6 new `CachingAnswerService` unit tests + 7 new `TTLCache` unit
tests + 2 new HTTP-level tests proving no-rerun and no cross-principal leakage + 1 test proving
`create_app` wires it by default → 213 tests total, was 197), boundaries clean, no ruff/pyright
regression, live-verified against a real running server** (killed a stale leftover `uvicorn`
process from an earlier session that was masking the new code on port 8000, then confirmed via
the structured logs: first `/chat` call did real retrieval — `latency_ms=395`, a live
`api.openai.com/v1/embeddings` call — second identical call logged `chat_answer_cache_hit` with
`latency_ms=0` and the same `trace_id`; a third call with a different `principal` got a fresh
`trace_id`, proving the cache never crosses a principal boundary).

**Scope decision (reordering, not scope-cutting):** per the pre-5.2 gate above, only the
exact-match half of the plan's "Caching: exact-match (Redis) + semantic cache ... ; keep prompt
caching" bullet is built here:
- **Exact-match:** built, in-process (see design decisions below).
- **Prompt caching:** already existed before this sub-step —
  `llm_client.AnthropicAnswerGenerator.generate` already passes
  `system_blocks=[cached_system_block(ANSWER_SYSTEM_PROMPT)]` (Phase 4). Nothing to add; recorded
  here only because the plan bullet named it.
- **Semantic caching:** deliberately not built. A similarity-threshold cache risks serving a
  plausible-but-wrong cached answer for a query that actually needed fresh retrieval — a real
  accuracy regression risk against this project's accuracy-first mandate — and there is no
  production traffic yet to tune a safe threshold against (no invented number). Deferred, not
  dropped; see `answer_cache.py`'s module docstring for the same rationale in the code.

**Design decisions (the plan text left the concrete mechanism open):**
1. **In-process, not Redis.** No confirmed multi-instance deployment requirement exists yet (no
   live deploy target — Phase 6 — and no concrete scaling number to justify one); the
   Architecture Standard's proportionality gate says add Redis only for a confirmed cache/queue/
   lock need, not ahead of one. Matches the precedent already set by `SlidingWindowRateLimiter`
   and the `Idempotency-Key` cache.
2. **`app.shared.ttl_cache.TTLCache[K, V]`** (new): the generic get/set/expire/max-entries-bound
   logic factored out of `server/router.py`'s `_IdempotencyCache` once a second consumer
   (`CachingAnswerService`) needed the exact same mechanism — the identical "two consumers"
   proportionality trigger that already moved `SlidingWindowRateLimiter` to `shared/` in PLAN 4.4.
   `_IdempotencyCache` itself is deleted; `router.py` now uses `TTLCache[str, Answer]` directly.
   Eviction is insertion-order (oldest-first), not true LRU — a deliberate simplification, since
   `max_entries` exists to bound memory, not maximize hit rate.
3. **`CachingAnswerService`** (`application/answer_cache.py`, new): a decorator around any
   `AnswerProvider` (a new `Protocol` in `answer_service.py` — the shape `router.py` actually
   depends on, satisfied by both the real `AnswerService` and this wrapper). `main.create_app`
   wraps `build_answer_service(settings)`'s result before assigning `app.state.answer_service`;
   `build_answer_service` itself is untouched (still returns a raw `AnswerService`, so
   `test_chat_endpoint.py`'s existing direct-construction tests needed zero changes).
4. **Cache key = `sha256(json([(role, content) for turn in history]) + "|" + (principal or ""))`.**
   Keyed on the *full* history, not just the final turn — the rewrite stage can use earlier turns
   as context, so two calls whose final turn matches but whose earlier turns differ are not
   guaranteed to produce the same answer. `principal` is part of the key so a hit can never leak
   one principal's answer to another — `AnswerService.answer`'s own ACL enforcement already ran
   once, at write time, before the cache ever stored the result.
5. **Same bounded-staleness tradeoff as the pre-existing `Idempotency-Key` cache**, reusing the
   same `TTLCache` and a matching 300s default (`chat_answer_cache_ttl_seconds`): a cached answer
   can be up to `ttl_seconds` stale if a page's content or restrictions change during that window.
   Already an accepted tradeoff for idempotency; not a new risk class.
6. **`get_answer_service_dep`/`_stream_answer`'s type hints moved from `AnswerService` to
   `AnswerProvider`** so the router accepts either the raw service or the cached wrapper — a
   structural-typing change only, zero behavior change; `router.py`'s `security_baseline`
   docstring gained a short addendum noting the cache is transparent to every control (C9 audit
   logging in particular still fires once per HTTP call, cache hit or miss).

**Shipped:**
- `app/shared/ttl_cache.py` (new): `TTLCache[K, V]`.
- `app/features/rag_agent/application/answer_service.py`: `AnswerProvider` protocol.
- `app/features/rag_agent/application/answer_cache.py` (new): `CachingAnswerService`.
- `app/features/rag_agent/server/router.py`: `_IdempotencyCache` deleted in favor of
  `TTLCache[str, Answer]`; type hints widened to `AnswerProvider`; docstring addendum.
- `app/features/rag_agent/__init__.py`: exports `AnswerProvider`, `CachingAnswerService`.
- `app/main.py`: `create_app` wraps `build_answer_service(settings)` in `CachingAnswerService`.
- `app/platform/config/settings.py` + `.env.example`: `chat_answer_cache_ttl_seconds` (300.0),
  `chat_answer_cache_max_entries` (500).
- Tests: `app/shared/tests/test_ttl_cache.py` (new), `app/features/rag_agent/tests/test_answer_cache.py`
  (new), 3 new tests in `confluence_sync/tests/test_chat_endpoint.py`.

**Not done (explicit scope decisions, not gaps):** semantic caching (see above); Redis (see
above); cache invalidation tied to content/ACL changes (relies on the TTL bound instead, matching
the idempotency cache's existing precedent).

**Blocker for 4.5/deploy — RESOLVED 2026-08-10.** `CHAT_API_KEY` is now a real 64-char hex secret
(`openssl rand -hex 32`) in both the root `.env` (`apps/automation`) and the new
`apps/web/.env.local` (`AUTOMATION_API_BASE_URL` also set there) — confirmed identical, and
confirmed `Settings.chat_api_key` actually loads it (`get_settings().chat_api_key` non-empty,
64 chars). Key **rotation** is intentionally deferred to Phase 5 (see that section) — a naive
single-key swap would cause an outage, so it needs a real dual-key mechanism, not a quick fix here.

**Pre-4.5 verification gate — 2026-08-10, PASS (both 4.3 and 4.4 were implemented but sitting
uncommitted; verified before committing, not after).** `make check` green at 194; `make boundaries`
clean (checked directly via `tools/check_feature_boundaries.py`, not just through `make check`).
Ruff/pyright diffed against the pre-4.3 baseline by file, not just by count: ruff-check unchanged
(2 errors, both pre-existing in `alembic/env.py`/`0001_core_schema.py`); pyright unchanged (34
errors, identical file list — zero new errors on any 4.3/4.4-touched or new file). Migration
`0005_page_restriction` round-tripped `head → -1 → head`. Re-read `server/router.py`'s
`security_baseline` docstring against the actual code: constant-time auth compare + fail-closed
503 confirmed at `router.py`, `redact_pii` confirmed wired at both `llm_client.py` Anthropic call
sites, audit log lines (`chat_request`/`chat_feedback`) confirmed to carry only ids/counts/latency
— never raw message or answer text. Confirmed all 4 named 4.3 acceptance tests
(`test_permission_enforcement_is_db_backed_not_fixture_fed`,
`test_first_index_persists_restrictions`, `test_dropped_restriction_leaves_page_unrestricted`,
`test_permission_change_is_metadata_only`) and the 4.4 breaker/abuse-cap adversarial tests
(`test_circuit_breaker_opens_after_consecutive_failures`, `test_success_resets_the_breaker`,
`test_input_abuse_cap_rejects_oversized_prompt`) exist and pass. **One real gap found and fixed:**
the 4.3-added `restricted_principals` helper in `confluence_sync/tests/_helpers.py` was left
ruff-unformatted (the file was already in the pre-existing unformatted baseline, so it didn't
regress the count, but the new code wasn't brought clean) — formatted in place, dropping the repo
unformatted-file count from 18 to 17, re-verified 194 tests still pass. Then split the combined
uncommitted diff into two independently-verified commits, stashing each phase's files to confirm
the *other* phase's commit stands alone and green before combining: **4.3 alone → 167 passed**
(`da76af9`), **4.3+4.4 → 194 passed** (`f7c1bdb`), boundaries clean at both points. **No other gaps
found; 4.5 may begin.**

### 4.5 — Web chat UI + contract extension ✅ done (2026-08-10)

**Status: implemented, tested (39 new vitest tests), typechecked, built, and live-verified end to
end in a real browser against the real backend — twice (once with a throwaway test key while
`CHAT_API_KEY` was still unset, once after the real key was generated and set).** Closes the
contract gap 4.4 flagged and fleshes out the `apps/web/src/features/chat` scaffold into a real,
working chat UI.

**Contract changes (`packages/contracts`):** `ChatRequest.message` → `history: ChatTurn[]`
(new `ChatTurn` type, deliberately not named `ChatMessage` — that name is already the feature's
own render view-model, kept intentionally distinct); `ChatDoneEvent` gains `traceId` (nullable —
`Answer.trace_id` can be `None`, mirrored) and `refused`; `Citation.version` relaxed to optional
(never populated by retrieval) and its `format: uri` dropped (backend can emit `""`, which isn't a
valid URI); added `FeedbackRequest`/`FeedbackResponse` for the feedback endpoint, and documented
`PATCH /chat/{traceId}/feedback` in `chat.yaml` (previously undocumented).

**Design decisions (the plan text left the concrete mechanism open):**
1. **The proxy is a real feature-owned server module, not logic inlined in the route file.**
   `features/chat/server/route-handlers.ts` (`handlePostChat`, `handlePatchFeedback`) is exported
   from the feature's public root and composed by `app/api/chat/route.ts` +
   `app/api/chat/[traceId]/feedback/route.ts` (Next 15 async `params`) — matching the repo
   standard's "route files stay thin, features own their capability end to end" rule. The backend
   base URL + shared secret live in a new `platform/automation-api` (generic external-client
   capability per the standard's `platform/` definition — not gated on "two consumers", that gate
   is for `shared/`), used by both routes.
2. **`AUTOMATION_API_BASE_URL`/`CHAT_API_KEY` are read server-side only, no `NEXT_PUBLIC_` var
   exists.** The plan text's own bullet ("`.env.local` — `NEXT_PUBLIC_API_BASE_URL`") turned out to
   be wrong on inspection: the browser only ever calls this app's own same-origin `/api/chat`; only
   the server-side route handler needs the backend's base URL, and exposing it (or the key) to the
   browser via `NEXT_PUBLIC_` would be strictly worse for no benefit. Deviated deliberately.
   Documented in `apps/web/.env.example` (new file — Next.js does not read the repo-root `.env`,
   confirmed by testing) and the root README.
3. **SSE parsing splits on `\n\n` over a growing string buffer**, not a line-by-line reader —
   matches exactly what `router.py`'s `_sse()` emits and is proven correct against a chunk-boundary
   split *inside* the `\n\n` separator itself (a dedicated test), not just the happy path.
4. **The streaming response is a true byte passthrough** (`new Response(backendResponse.body, ...)`)
   — no re-buffering, no re-chunking. The proxy adds no latency to the already-paced backend stream.
5. **C2/C10 are explicitly opted out at the proxy layer, not silently skipped** — the backend
   already enforces rate limiting and abuse caps on the exact same request; a second, weaker
   in-memory limiter in a Next.js process (no shared store across instances) would be redundant and
   could drift from the backend's real config. Documented as a `security_baseline` opt-out with
   rationale in `route-handlers.ts`'s docstring, following the same format `router.py` uses.
6. **Proxy-side input validation is structural, not a duplicate of the backend's business caps.**
   `server/validation.ts` rejects malformed shape/JSON and a generous resource-exhaustion body-size
   ceiling (200KB) — it deliberately does not hardcode the backend's `chat_max_history_turns`/
   `chat_max_message_chars` numbers, so the two layers can't silently drift; the backend's real 400
   is forwarded verbatim when its caps are exceeded.

**Design-review findings (fe:design-reviewer agent, live browser audit) — all fixed before
closing this phase:** non-text contrast failure on the new badge/citation-chip/feedback-button
(border-only on the page background, ~1.37:1 — fixed with a `bg-surface-raised` fill matching the
existing message-bubble precedent); refusal badge visually identical to decorative chips (fixed —
distinct filled/bright-text treatment so it reads as status, not metadata); missing
`focus-visible` ring on the new citation link and feedback buttons (fixed — added the same
`focus-visible:ring-2 focus-visible:ring-accent` utility the shared `Button` already uses);
citations with no URL rendering as hrefless (fake) links (fixed — render a `<span>` with an
"unavailable" cue instead of an anchor with no `href`); the whole message list being one
`aria-live="polite"` region that also received every streamed token mutation, which would cause
screen readers to re-announce fragment-by-fragment instead of once per finished turn (fixed — the
`<ul>` is no longer live; a separate visually-hidden region announces only the most recently
*finished* turn). Not independently re-verified by a screen reader or a real narrow-viewport
render — flagged by the reviewer as uncovered, not re-run here.

**Shipped:**
- `packages/contracts/src/openapi/chat.yaml` + `src/index.ts`: contract changes above.
- `apps/web/src/platform/automation-api/{client,index}.ts` (new): authenticated, timeout-bounded
  calls to `apps/automation`; fails closed (`AutomationApiConfigError`) if `CHAT_API_KEY` unset.
- `apps/web/src/features/chat/server/{validation,route-handlers}.ts` (new): C3 input validation +
  the proxy itself, exported from the feature's public root.
- `apps/web/src/app/api/chat/route.ts` (rewritten, no longer a 501 stub) +
  `apps/web/src/app/api/chat/[traceId]/feedback/route.ts` (new): thin route entrypoints.
- `apps/web/src/features/chat/api/chat-client.ts` (rewritten): real SSE `streamChat` +
  `sendFeedback`, replacing the Phase-1 `sendChat` stub (removed, not left as dead code).
- `apps/web/src/features/chat/model/messages.ts`: `MessageStatus` gains `"refused"`; `ChatMessage`
  gains `traceId`/`feedback`.
- `apps/web/src/features/chat/ui/{chat-panel,message-list}.tsx` (rewritten): real streaming
  state, citation chips, refusal badge, thumbs-up/down feedback with `aria-pressed`.
- `apps/web/vitest.config.ts` + `package.json` (new test runner — none existed in `apps/web`
  before this phase, as FEATURES.md's own "Test: None yet (test runner is wired in Phase 4)" note
  anticipated): 39 tests across `validation.test.ts`, `chat-client.test.ts`,
  `route-handlers.test.ts` — pure logic + SSE parsing + mocked-backend proxy behavior (auth-header
  injection, idempotency-key forwarding, error/streaming passthrough, fail-closed 503). No
  component-render tests (no jsdom/RTL added) — explicit scope decision, see "Not done" below.
- `apps/web/.env.example` (new) + root `.env.example`/`README.md` updated to point at it.
- `apps/web/src/features/chat/FEATURES.md`, `apps/web/src/platform/README.md` (new) updated/added.

**Acceptance proof:** `pnpm --filter web test` → 39/39 passed; `tsc --noEmit` clean;
`pnpm --filter web build` clean (both new routes compile as dynamic `ƒ`, as they must — they can't
be statically generated). Backend untouched — `apps/automation`'s 194 tests and `make boundaries`
re-confirmed green, unaffected. Live end-to-end verification via real browser + real running
backend (not mocked): typed a question in `/chat`, observed the full `start → token × N →
citations → done` stream render with the refusal badge, empty-citations state, and a working
Helpful/Not-helpful toggle (`PATCH` round-trip confirmed via the UI and via direct `curl`); repeated
the same round trip after the real `CHAT_API_KEY` replaced the throwaway test value, with zero
code changes required — confirming the proxy reads real env, not a hardcoded test path.

**Not done (explicit scope decisions, not gaps):** no component-render tests (`message-list.tsx`/
`chat-panel.tsx` are exercised live in a real browser instead — adding jsdom+RTL for a first
render-test pass wasn't judged proportional to this phase alone); no ESLint run (`pnpm --filter web
lint` — confirmed pre-existing and unrelated: no ESLint config exists anywhere in `apps/web`, predating
this phase, `next lint`'s interactive setup wizard has never been completed; flagged, not fixed,
since standing up a whole lint toolchain is repo-wide tooling debt, not phase-4.5 scope); screen-reader
and narrow-viewport verification (flagged by the design-review agent, not independently re-run);
`CHAT_API_KEY` rotation mechanism (deferred to Phase 5, see that section).



**Status: implemented, tested (12 new endpoint tests + 5 new client/PII unit tests), boundaries
clean, no ruff/pyright regression.** `app/features/rag_agent/server/router.py` wires the 4.2
`AnswerService` (built from real settings via `main.build_answer_service`, sharing one
`AnthropicMessagesClient` between the rewrite and generation calls) to a live HTTP surface with
the full `securing-http-and-llm-endpoints` control set applied — see the module's
`security_baseline` docstring for the per-control mechanism, mirrored into
`FEATURES.md`'s YAML block.

**Design decisions (the plan text left the concrete mechanism open):**
1. **Streaming is chunked-replay, not per-model-token streaming.** `AnswerService.answer()` is a
   synchronous, fully-buffered pipeline (rewrite → retrieve → CRAG → refusal → generate → citation
   enforcement) — citation enforcement runs on the *complete* generated text, stripping uncited
   sentences. Streaming raw model tokens as they generate would risk showing text that later gets
   retracted. Instead, `POST /chat` runs the full pipeline once, then SSE-streams the final,
   already-citation-enforced `Answer.text` in fixed-size chunks (`chat_token_chunk_chars`) paced
   by `chat_stream_interval_ms` — a real incremental "typewriter" delivery for the UI, but not a
   TTFT improvement. Genuine incremental generation-time streaming (needed to hit the Phase-5 TTFT
   targets) is deferred to Phase 5, where it belongs per §3's proof list.
2. **The server is stateless per request — no server-side conversation store.** The caller
   (eventually `apps/web`) resends the full turn `history` on every call; there is no
   `conversation_id`-keyed history table. `conversationId` is a caller-supplied-or-minted
   correlation id only. This is *simpler* than adding a `query_trace.conversation_id` +
   reconstruction path, and it matches `AnswerService.answer(history, scope)`'s existing,
   already-tested signature exactly — no changes needed to 4.2's answer service or trace schema.
3. **C1 auth is a shared secret (`CHAT_API_KEY`), not end-user login.** There is no end-user
   identity/session system in this repo yet (confirmed: no auth/session code anywhere in
   `apps/web` or `apps/automation`). `principal` in the request body is caller-self-reported and
   trusted only as far as C1 trusts the calling web proxy. This is safe, not a hole: per
   ADR-0004's default-deny model, `PrincipalPermissionPolicy.allowed()` already treats an
   absent/unverified principal as "only unrestricted pages visible" — never a bypass. Real
   per-user identity is a later, separate phase.
4. **C6 PII redaction is pattern-based** (`rag_agent/domain/pii.py`: email/phone/SSN/card-number
   regexes), applied to the fully-assembled prompt right before it leaves `llm_client.py`'s two
   Anthropic call sites — not inside `AnswerService`, so retrieval/CRAG continue comparing the
   verbatim query and 4.2's already-tested control flow is untouched. Scope is stated plainly in
   the module docstring: this is a defensive net for the *user's* query text, not a
   content-governance pass over the retrieved Confluence evidence (same posture ingestion's C6
   opt-outs already take).
5. **C4 breaker + abuse cap added to the shared `AnthropicMessagesClient`** (previously
   timeout+retry only) — it now backs an HTTP-exposed call for the first time. Both default to
   effectively-off (`breaker_threshold=1_000_000`, `max_input_chars=None`) so the existing
   contextualization call site (Phase 3) is unaffected; 4.4's chat client construction sets both
   explicitly.
6. **`SlidingWindowRateLimiter` moved from `confluence_sync/server/webhook.py` to
   `app/shared/rate_limiter.py`** — the chat endpoint is a second, independent consumer of a
   generic technical primitive with no confluence-specific behavior (the exact "two consumers"
   proportionality trigger for `shared/`). Generalized to accept a `window_seconds` param (default
   60.0, matching prior behavior) so the same class serves both a per-minute and (if needed later)
   a coarser window.
7. **C7 idempotency is a real in-process TTL cache**, not a stub: an optional `Idempotency-Key`
   header, when present, replays the cached `Answer` (same `trace_id`) within
   `chat_idempotency_ttl_seconds` instead of re-running retrieval/generation — proven by a test
   asserting the second call's `traceId` equals the first's.

**Contract gap for 4.5 (real, not optional):** the Phase-1 hand-written `packages/contracts`
`ChatRequest`/`ChatStreamEvent` types predate this design and don't match it —
`ChatRequest` has no `history` field (4.4's endpoint requires one), and `ChatDoneEvent` has no
`traceId` (needed by the feedback PATCH) or `refused` flag (needed by the UI to route to a human).
`Citation.version` is also required in the TS contract but nothing in the retrieval pipeline
surfaces a page version onto a citation — relax it to optional rather than threading a new field
through `retriever.py`/`search_repo.py` for a nice-to-have. 4.5 must extend `chat.yaml` +
`src/index.ts` to add `history`, `traceId`, `refused`, and relax `version`, matching what
`POST /chat` actually emits (see `server/router.py`'s `_stream_answer`).

**Shipped:**
- `app/features/rag_agent/server/router.py` (new): `POST /chat` (SSE `start`/`token`/`citations`/
  `done`/`error`) + `PATCH /chat/{trace_id}/feedback`; auth, rate limiting, input validation,
  idempotency cache, audit logging all in this module.
- `app/features/rag_agent/domain/pii.py` (new): `redact_pii`.
- `app/features/rag_agent/infrastructure/llm_client.py`: both Anthropic call sites now redact
  their assembled prompt before sending.
- `app/platform/clients/anthropic_client.py`: `AnthropicMessagesClient` gains
  `breaker_threshold`/`max_input_chars` (C4/C10), defaulting to off for existing call sites.
- `app/shared/rate_limiter.py` (new, moved from `confluence_sync/server/webhook.py`):
  `SlidingWindowRateLimiter`, generalized with a `window_seconds` param.
- `app/main.py`: `build_answer_service(settings)` composes the real `HybridRetriever` +
  `AnthropicQueryRewriter`/`AnthropicAnswerGenerator` + `AnswerService`; wired onto
  `app.state.answer_service` and the chat router included alongside the confluence router.
- `app/platform/config/settings.py`: `answer_*` (timeout/retries/breaker/abuse-cap) and `chat_*`
  (api key, rate limit, history/message caps, output cap, streaming pace, idempotency TTL)
  settings; mirrored in `.env.example`.
- Tests: 6 PII unit tests, 4 llm_client redaction/fail-open tests, 5 `AnthropicMessagesClient`
  breaker/abuse-cap tests, 12 `confluence_sync/tests/test_chat_endpoint.py` DB-integration tests
  (auth missing/wrong/unconfigured, history-end-on-user-turn, history-length cap, message-length
  cap, rate limit, the real SSE stream against the indexed corpus with token-reassembly matching
  the done answer, refusal surfacing `refused: true`, idempotency replay, feedback PATCH persisting
  to `query_trace`, feedback auth/validation) → **194 tests total** (was 167 at 4.3). `make
  boundaries` clean. Ruff exactly at baseline (2 errors / 17 unformatted, ≤ 25/2 — fewer
  unformatted than the 19 baseline; the pre-phase-4.5 verification pass additionally formatted a
  4.3-added function in `confluence_sync/tests/_helpers.py` that had been missed). Pyright:
  34 errors total, identical file list to the pre-4.4 baseline — zero new errors on any touched or
  new file (verified by diffing the per-file error listing, not just the count).

**Not done (explicit non-goals, deferred to where the plan already puts them):** the web chat UI
and contract extension (4.5); genuine per-model-token streaming for TTFT (Phase 5); real end-user
login/identity (a later, separate phase — not named in the plan yet); NER-grade PII detection
(the regex pass is intentionally basic, documented in `pii.py`).

### 4.3 — Real principal ACL storage ✅ done (2026-08-10)

**Status: implemented, unit- and integration-tested, committed (`da76af9`).** Replaced the
fixture-fed `PrincipalPermissionPolicy`'s data source with a real, queryable per-page ACL: a new
`page_restriction` table (page_id, principal — presence restricts, absence means unrestricted),
written by `confluence_sync`'s `handle_sync_page` whenever a page's restriction list actually
changes (or on first index), and read fresh per search by `HybridRetriever._search` — never the
whole corpus. Source-level RLS (3.5) and this page-level ACL are distinct, both-apply layers per
ADR-0004/0005, exactly as designed.

**Design decisions (not scope changes — the plan text left the concrete schema open):**
1. **Schema:** `page_restriction(page_id, principal)`, composite PK, FK to `page_source.page_id
   ON DELETE CASCADE`. Migration `0005_page_restriction`, raw DDL mirroring 0004's style
   (schema-only, idempotent `CREATE TABLE IF NOT EXISTS`). `rag_reader`'s existing
   `GRANT SELECT ON ALL TABLES` + `ALTER DEFAULT PRIVILEGES` (01-roles.sql) cover the new table
   automatically — no separate grant migration needed.
2. **Write path lives in `confluence_sync`, ownership stays with `ingestion`** — same convention
   already established for `page_source`/`chunk`: `sync_service.py` writes the ORM model directly
   (platform/db is shared vocabulary, ADR-0003 D5), `ingestion`'s FEATURES.md block documents it
   as the table owner. Write is a full delete+insert replace (not a diff/append), guarded by
   `local is None or decision.access_scope_hash != local.access_scope_hash` so an unchanged page
   costs nothing extra on every reconcile tick. Deferred until *after* `stage_and_activate` on the
   first-index path — `page_source` doesn't exist yet before that call, and the FK would reject an
   earlier write.
3. **Retriever wiring:** `HybridRetriever`'s constructor `policy: PrincipalPermissionPolicy`
   parameter is unchanged in shape (zero call-site breakage across the eval harness), but its
   `space_of`/`restrictions` data is no longer consulted for the `allowed()` decision — only its
   stateless `space_id()` parsing is still used. `_search()` now calls a new
   `search_repo.fetch_page_scopes(session, ranked)` (space_of from `page_source`, restrictions
   from `page_restriction`, scoped to the current fused candidate set) and builds a fresh
   request-scoped `PrincipalPermissionPolicy` for the `allowed()` filter. The pure domain class
   (`permission.py`) is untouched — still framework-free and independently unit-tested.

**Acceptance proof (the part that actually matters):** every existing DB-backed permission test
(`test_permission_no_leak_and_authorized_access`, `test_retriever_wrong_source_scope_returns_zero`,
etc.) still passes unchanged, because `_index_corpus` already runs the real sync path and now
transparently populates `page_restriction` with the same data the tests' in-memory
`_build_policy(gateway)` derives — proving the two paths agree. That alone isn't proof the DB is
actually *doing* the enforcement, so a new test closes that gap directly:
`test_permission_enforcement_is_db_backed_not_fixture_fed` constructs the retriever with a
deliberately **empty** `PrincipalPermissionPolicy()` (no `space_of`, no `restrictions`) and
confirms authorized/space-scoped/unauthorized access all still resolve correctly — which would
fail under the pre-4.3 code (an empty policy is either wide-open for principal scope or
all-denying for space scope). Also added: `test_first_index_persists_restrictions`,
`test_dropped_restriction_leaves_page_unrestricted`, and an extended
`test_permission_change_is_metadata_only` asserting the persisted ACL replaces (not appends) on
change. **167 tests total** (was 164 at 4.2 — 3 new DB-integration tests). `make boundaries`
clean.

**Ruff/pyright reconciliation (git-stash-diffed against the pre-4.3 HEAD, not just re-counted):**
`test_retrieval_eval.py` was reformatted after editing to stay at the ruff-format baseline (19
unformatted, unchanged). Ruff-check unchanged (2 errors, both pre-existing in
`alembic/env.py`/`0001_core_schema.py`, untouched by this phase). Pyright's raw count moved by a
few, but a message-level diff (ignoring line numbers, which shifted from inserted code) shows
**zero new error types** — the deltas are additional occurrences of two already-baseline,
pre-existing patterns unrelated to this phase's logic: `ChangeDecision`'s `bytes | None` hash
fields (pre-existing, `sync_service.py`) and `RunResult.outcome: object | None`'s loose typing
(pre-existing, every other test in `test_worker_sync.py` already hits this same pattern) — my new
test in that file added one more occurrence of the latter by following the file's own existing
idiom. No new pattern, no new file, no regression on the actual logic touched.

**Not done (explicit non-goals, per the plan's own phasing):** no CRUD API for restrictions (Confluence
remains the source of truth, synced one-way); group-based principals are not modeled — the fixture
gateway's `get_restrictions()` only ever returns user account ids (Confluence group expansion would
be a separate, later enhancement, unchanged from pre-4.3 behavior). `POST /chat` is 4.4.

### 4.2 — Answer workflow ✅ done (2026-08-10)

**Status: implemented, unit- and integration-tested, committed (`4cc2ee2`).** `AnswerService`
(`app/features/rag_agent/application/answer_service.py`) implements the fixed pipeline: rewrite
(`AnthropicQueryRewriter`, fails open to the verbatim query on an `AnthropicError`) → RLS-scoped
retrieve/RRF/rerank via `HybridRetriever.retrieve_with_context` (chunk ids + scores now surfaced,
not discarded) → one CRAG retry with the verbatim query if the rewritten query's top score is weak →
refusal via the 4.1 `decide_refusal` core → parent-context expansion (`fetch_parent_texts`, children
retrieve/parents ground) → grounded generation (`AnthropicAnswerGenerator`) → citation enforcement
via the 4.1 `enforce_citations` core, degrading to refusal if nothing survives → `query_trace` UPDATE
with the rewritten query/answer/citations.

**Deviation from the plan text (a refinement, not a scope change):** the plan said to "refactor
`retrieve`'s return"; instead, `retrieve()` kept its original `list[str]` signature (the eval
harness's `RankFn` seam and several already-verified 3.5 tests depend on that exact shape) and a new
`retrieve_with_context()` was added alongside it, sharing one private `_search()` core. Both write
the same richer `query_trace` row now (chunk ids + rerank scores were previously discarded even by
`retrieve()`) — so the acceptance criterion (those columns non-NULL) is met either way, with zero
regression risk to already-verified retrieval tests.

**CRAG semantics (a design decision the plan left open):** one retry, triggered only when
`rewrite_enabled` actually changed the query (retrying an identical query returns an identical
result) and the first result's top score is below `refusal_min_rerank_score`; retries with the
user's verbatim last turn and keeps whichever result scored higher. Ordering: the retry runs
*between* retrieval and the refusal check (refusing before ever retrying would defeat the point),
even though DESIGN.md's stage table lists refusal (5) before CRAG (6) — that table enumerates
concerns, not call order.

**Shipped:**
- `retrieval/infrastructure/search_repo.py`: `fetch_rerank_texts` now returns a `RerankCandidate`
  (chunk_id + title + source_url + text) per page instead of a bare string; new
  `fetch_parent_context` joins a child's `parent_chunk_id` to its parent's `display_content`.
- `retrieval/infrastructure/trace_repo.py`: `write_query_trace` accepts + persists
  `retrieved_chunk_ids`/`rerank_scores` and returns the new row's id; new
  `update_query_trace_answer`/`update_query_trace_feedback` UPDATE writers.
- `retrieval/application/retriever.py`: new `RetrievedHit`/`RetrievalResult` DTOs,
  `retrieve_with_context()`, `fetch_parent_texts()`; `retrieve()` unchanged in shape.
- `retrieval/__init__.py` root now also exports `RetrievedHit`, `RetrievalResult`,
  `update_query_trace_answer`, `update_query_trace_feedback`.
- `rag_agent/domain/prompt.py` (new): pure rewrite-prompt/evidence-block/answer-prompt builders.
- `rag_agent/infrastructure/llm_client.py` (new): `QueryRewriter`/`AnswerGenerator` protocols +
  `AnthropicQueryRewriter`/`AnthropicAnswerGenerator`.
- `rag_agent/application/answer_service.py` (new): `AnswerService`.
- `rag_agent/__init__.py` root now also exports `AnswerService`, `QueryRewriter`, `AnswerGenerator`,
  `AnthropicQueryRewriter`, `AnthropicAnswerGenerator`.
- Settings: `rewrite_enabled` (default `true`), `crag_max_retries` (default `1`).
- Tests: 5 pure prompt tests, 9 `AnswerService` orchestration tests (fake retriever/rewriter/
  generator — no network, no DB), 3 retrieval-layer DB-integration tests (chunk ids/scores in the
  trace, `fetch_parent_texts` real join, `update_query_trace_answer`/`_feedback`), 3
  `test_answer_workflow.py` DB-integration tests (grounded citation flow, source-scope refusal,
  no-grounded-claim refusal) — all against the real fixture corpus with fake LLM collaborators →
  **164 tests total** (was 144). `make boundaries` clean; ruff 2 errors/19 unformatted, pyright 31
  errors — both exactly at the ADR-0003 D1 no-regression baseline, none of the new errors on touched
  files (verified directly, not just counted).

**Not done (deferred, per the plan's own phasing):** `POST /chat` wiring, real Anthropic client
construction from settings, and the `securing-http-and-llm-endpoints` control set are Phase 4.4 —
this phase only builds and tests the internal workflow, with no HTTP surface and no test hitting a
real LLM.

**Pre-existing gap noticed, not fixed here (out of scope for 4.2):** the "hermetic settings fixture
MUST force `reranker_provider=fake`" rule documented in §4 is not actually enforced as a blanket
override in `conftest.py` — `test_smoke_maintains_recall_and_beats_ranking` and
`test_rerank_lift_before_vs_after`'s "after" side both call `build_reranker(settings)` with whatever
is in the developer's real `.env` (currently `RERANKER_PROVIDER=cohere` + a live key), so local
`make test` runs do make live Cohere calls in those two tests (harmless — deterministic-enough
assertions are guarded by `if ... == "fake"` — but not what the doc claims). Flagged for a future
session; 4.2's own new LLM calls avoid the same trap by injecting fake collaborators directly in
every test rather than going through a settings-driven factory.

**Phase 4.1 done (`e4490aa`):** new `rag_agent` feature scaffolded per the repo
standard — public root exporting the `Answer`/`Citation`/`ChatMessage` DTO contract; pure domain core
`decide_refusal` (ADR-0005 §7) + `enforce_citations` (§6, strips uncited/hallucinated-source claims);
`FEATURES.md` block; **10 unit tests → 130 passed total**. Boundaries clean; ruff/pyright 0 on the new
files. No service/endpoint yet (that's 4.2/4.4).

**Pre-Phase-4 verification gate — re-run 2026-08-07, PASS:** pgvector 0.8.5 (≥ 0.8); `make boundaries`
clean; `make test` → **120 passed, 0 skipped**; the four DB-backed isolation/trace/lift tests
(`test_rls_default_deny_on_reader_role`, `test_retriever_wrong_source_scope_returns_zero`,
`test_retrieval_writes_one_query_trace_row`, `test_rerank_lift_before_vs_after`) all ran and passed;
all three migrations carry a `downgrade`; RLS `set_config` uses a bound `:s` param (injection-safe);
reranker has timeout/retry/breaker/abuse-cap and never logs the key; ruff 2 errors / 22 unformatted
(≤ 2/25) and pyright 31/1 — at the ADR-0003 D1 baseline, no regression.

**3.5.5 outcome (done):** rerank-lift mechanism (`evaluate_rerank_lift`, pure) + DB-backed integration
run captured a live Cohere lift of **ndcg@10 −0.123 / precision@5 +0.000** on the saturated 6-case fixture
— expected (no headroom); genuine lift deferred to the Phase-5 gold set. `refusal_min_rerank_score=0.10`
provisional. Keys confirmed present in `.env`: `RERANKER_PROVIDER=cohere` + `RERANKER_API_KEY`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. `CONFLUENCE_API_TOKEN` still dead (live ingestion only).

**Supabase decision: its own dedicated Phase 6** (prod/deploy only; keep local Docker pgvector for
dev). See "Phase 6 — Supabase vector store migration & deploy" below; it's blocked on the user for the
connection string, a pgvector ≥ 0.8 confirmation, and the `rag_reader`/RLS→Supabase-roles mapping.

**Independent re-verification — 2026-08-10, PASS.** Re-checked Phase 0 + all of 3.5 + 4.1 against code
and live command output, not the ledger's self-report: `make boundaries` clean; all 3 Alembic migrations
round-tripped `head → base → head` with zero errors; `pytest -q` → **130 passed** (matches ledger); `ruff
check` 2 errors / `ruff format --check` 22 unformatted, both pre-existing per `git blame` (≤ 25/2
baseline, no regression); `pyright` 31/1 exactly at baseline, none of the errors touch
`reranker_client.py`, `retriever.py`, `search_repo.py`, `rag_agent/*`, or `engine.py`. Read (not just
counted) the RLS default-deny policy + isolation tests, the reranker's timeout/retry/breaker/abuse-cap +
no-key-logging, the `query_trace` one-row-per-retrieval write path, and the `rag_agent`
`decide_refusal`/`enforce_citations` tests — all assert real behavior (actual refusal below threshold,
actual zero-rows on wrong scope), not smoke checks. **No gaps found; nothing to fix before 4.2.**

### 3.5.6 — Confluence source scoping ✅ done (2026-08-10)

**Status: implemented, tested, documented, committed (`0f1a0d7`).** Independently re-verified in a
follow-up session before committing: `make boundaries` clean, `pytest -q` → 144 passed, ruff 2
errors/19 unformatted (within the ≤25/2 baseline), pyright 31 errors (exactly at baseline, none on
touched files), migration 0004 round-tripped `head → -1 → head`. Followed
`superpowers:brainstorming` end to end (clarifying questions → 2 approaches proposed → design
presented in 3 sections, each approved → spec written to
`docs/superpowers/specs/2026-08-10-confluence-source-scoping-design.md` → approved → built directly
given the spec's completeness and the user's explicit go-ahead, skipping a separate `writing-plans`
pass). **Did not block Phase 4.2** — this only touched ingestion scope config; 4.2 remains next.

**Shipped:**
- `source_scope` ORM model + migration `0004_source_scope` (`down_revision="0003_query_trace"`,
  schema-only, reversible — round-tripped `head → -1 → head` and diffed identical to the ORM).
- `confluence_sync/domain/scope_resolver.py` — pure `resolve_scope_roots` (root → covered page ids;
  a `page` root's tree-walk over `parent_id`, never a sibling/ancestor) + `resolve_space_scope`
  (per-space aggregator: union of active roots' coverage + tag union on overlap). Exported from
  the feature's public root per the boundary rule.
- `reconciliation.py` wired: `_sweep_space` takes the resolved scope (narrows the live set,
  purges what's no longer covered); `run_reconciliation`'s space discovery unions in scope-implied
  spaces so a brand-new space gets its first sweep; tags ride the job payload through
  `worker.py` → `sync_service.handle_sync_page` → `ingestion.stage_and_activate`/`build_chunks`
  (new optional `tags` param, `[]` when omitted — the existing single activation seam, extended not
  replaced) → stamped on `page_source.tags`/`chunk.tags`.
- **Dead code removed**: `settings.confluence_spaces` + `.confluence_scope_list` deleted (zero
  consumers, confirmed by grep before deletion); `CONFLUENCE_SPACES` dropped from `.env.example`
  with a pointer to the new seed script.
- `scripts/seed_source_scope.py` — one-off idempotent CLI (upsert/deactivate/delete by
  `root_type`+`root_id`), matching the spec's "one-off, no CRUD API yet" ownership decision.
  Smoke-tested end to end against the dev DB.
- Tests: 12 pure unit tests (`test_scope_resolver.py`) + 2 DB-backed integration tests extending
  `test_reconciliation.py` (subtree-narrowing + tag propagation; purge-on-root-deactivation) →
  **144 tests total** (was 130). `make boundaries` clean. Ruff/pyright verified against baseline via
  git-stash diff, not just "still passes": 0 new pyright errors, 0 new ruff errors, fewer
  unformatted files than baseline (19 vs. 22-25) after formatting the files this sub-step touched.

**Deviations from the spec as written (both are refinements, not scope changes):**
1. The migration does **not** read `CONFLUENCE_SPACES`/`Settings` as a data seed, unlike the
   spec's "one-time migration seed" framing. Migrations 0001-0003 never coupled DDL to mutable env
   state; doing so here would make `alembic upgrade head` non-deterministic across environments,
   including the hermetic test DB. Seeding is the one-off script instead — ownership was already
   "one-off, no CRUD" either way, so the actual workflow is unchanged, only where the seed command
   lives.
2. `resolve_space_scope` takes every recorded root for a space (active or not), not only active
   ones. Discovered while writing the purge-on-removal test: with only-active roots, "zero rows
   ever" and "rows exist but all deactivated" both collapse to the same `roots=[]` input, which
   would make deactivating a space's *last* root silently revert to unrestricted instead of purging
   it — contradicting the spec's own "purge only when no active root covers it" intent. Fixed by
   distinguishing the two cases explicitly (see `scope_resolver.py`'s docstring).

**Not done (explicit non-goals, per the spec, unchanged):** no CRUD API/admin UI; Confluence only;
OCR/image reading untouched.

### Progress (as of 2026-08-07, branch `feat/rag-phase-3.5`; re-verified 2026-08-10)

| Phase | Status | Commit | Proof |
|---|---|---|---|
| **0** — DESIGN.md + ADR-0004/0005 | ✅ done | `d793bb1` | design of record + 2 ADRs, code-grounded |
| **3.5.1** — pin pgvector 0.8 + HNSW iterative-scan GUCs | ✅ done | `7cd9fd1` | pgvector 0.8.5 pinned by digest; 4 unit tests |
| **3.5.2** — cross-encoder reranker (Cohere/Fake) + wire | ✅ done | `7cd9fd1` | 10 unit tests; rerank after permission filter; Fake in CI |
| **3.5.3** — provider tags + RLS + `rag_reader` role | ✅ done | `96f4786` | RLS default-deny proven; migration 0002 reversible |
| **3.5.4** — `query_trace` scoreboard (minimal) | ✅ done | `a9f9259` | 1 trace/retrieval; migration 0003 reversible |
| **3.5.5** — measure rerank lift + Phase 3.5 exit gate | ✅ done | `1b6e94c` | 120 tests; `evaluate_rerank_lift` + live Cohere run; **lift −0.123 ndcg@10 on the saturated fixture — expected, real lift is a Phase-5 gold-set measurement** |
| **4.1** — `rag_agent` scaffold: DTOs + refusal/citation domain core | ✅ done | `e4490aa` | 10 unit tests → 130 total; public root + FEATURES.md; boundaries clean; ruff/pyright 0 on new files |
| **3.5.6** — Confluence source scoping (`source_scope` table) | ✅ done | `0f1a0d7` | 14 tests → 144 total; migration 0004 reversible; boundaries clean; no ruff/pyright regression |
| **4.2** — answer workflow (`AnswerService`) | ✅ done | `4cc2ee2` | 20 tests → 164 total; boundaries clean; no ruff/pyright regression; DB-integration-tested, no live LLM calls |
| **4.3** — real principal ACL storage (`page_restriction`) | ✅ done | `da76af9` | 3 tests → 167 total; migration 0005 reversible; boundaries clean; no new pyright error type (git-stash-diffed) |
| **4.4** — `POST /chat` SSE + feedback, full security control set | ✅ done | `f7c1bdb` | 27 tests → 194 total; boundaries clean; no ruff/pyright regression (verified by per-file diff) |
| **4.5** — web chat UI + contract extension | ✅ done | `8cbaf46` | 39 web tests; typecheck/build clean; live-verified end to end (real browser + real backend, real `CHAT_API_KEY`) |
| **5.1** — `CHAT_API_KEY` rotation mechanism | ✅ done | `261ac1e` | 3 tests → 197 total; overlap-window auth, rotation script, runbook |
| **5.2** — exact-match answer caching | ✅ done | `261ac1e` | 16 tests → 213 total; `TTLCache` extracted to `shared/`, `CachingAnswerService` wraps `AnswerService`, no cross-principal leak |
| **5.3** — prompt-injection + permission/isolation red-team | ✅ done | `92bbb7f` | 6 tests → 219 total; found + fixed a real numeric-principal space-trust bypass; no live LLM spend |
| **4.6** — fixes-backlog remediation (16 sub-steps + exit gate) | 🔶 in progress (4.6.1/16 done) | `4d0ba70` | independent same-day audit (`docs/rag/fixes/`) found a CRITICAL ACL bypass + a HIGH cross-principal leak + 12 more findings in already-"done" phases 0-4; **gates 5.4/bake-off/adaptive-routing** until the 4.6.16 exit gate is green; 4.6.2 blocked on user input |
| **5** (remaining) — 5.4 live-LLM red-team + latency/cost proof, embedder bake-off, adaptive routing | ⬜ todo (blocked on 4.6) | — | 5.4 needs real API calls/spend; bake-off blocked on Confluence token + `VOYAGE_API_KEY` |
| **6** — Supabase vector store migration & deploy | ⬜ todo (deferred) | — | prod target; needs connection string + pgvector ≥ 0.8 + role/RLS mapping |
| **4.7** — UI component refactor: Obi widget rebuild + brand tokens (4.7.1 → 4.7.4) | ⬜ todo | — | frontend-only, `apps/web`; does not gate Phase 5; source of truth `/Users/matissevansteenbergen/Downloads/Obi chatbot UI mockups/` |
| **4.8** — Frontend/backend repository separation (4.8.1 → 4.8.7) | ⬜ todo (blocked on registry/repo-name/monorepo-fate decisions) | — | supersedes ADR-0006's deferral; see `docs/adr/0007-Frontend-Backend-Repository-Separation.md`; do after 4.7 |

Gate at each ✅: `make check` green (**219 backend tests** as of 5.3 — 4.5 touched no backend code;
was 213 at 5.1/5.2, 197 at 5.1, 194 at 4.4, 167 at 4.3, 164 at 4.2, 144 at 3.5.6, 130 at 4.1, 120 at
end-3.5, 99 pre-3.5), `make boundaries` clean, ruff/pyright at the ADR-0003 D1 baseline (no
regression — 2 errors/17 unformatted ruff ≤ 25/2, pyright 34 errors — same file list as the 4.3
baseline, 0 new errors on touched files; re-verified live 2026-08-10 before committing 4.5/5.1/5.2,
and again for 5.3).
`apps/web` gained its first test runner at 4.5: **39 vitest tests**, `tsc --noEmit` clean, `next
build` clean (no prior web-test baseline to regress against). Reader/RLS isolation tests + all five migrations
verified — 0005 round-tripped `head → -1 → head` during the pre-4.5 verification pass; `alembic current`
re-confirmed at `0005_page_restriction (head)` before committing 5.1/5.2 (neither needs a migration).

**Phase 3.5 exit gate — MET (2026-08-07):** `make check` green (120); `make eval` prints the before/after
rerank table; isolation tests pass (RLS default-deny + wrong-source→0); pgvector 0.8.5 pinned; every
retrieval writes one `query_trace` row; no ruff/pyright regression. Rerank lift measured live (Cohere
`rerank-v3.5` + OpenAI-3072): **ndcg@10 −0.123, precision@5 +0.000 on `retrieval_smoke`** — the fixture is
already saturated (dense ranks the one relevant page first, before-ndcg = 1.000), so there is no headroom;
the genuine lift is a **Phase-5 gold-set measurement**. `refusal_min_rerank_score = 0.10` provisional,
re-tune in Phase 5. **→ Phase 3.5 closed; Phase 4.1 shipped (`e4490aa`); next is 4.2.**

### Deviations already taken (documented, not silent)

- **Source columns keep their `server_default`** (plan said "drop it"): keeps the migration-built and
  `create_all`-built schemas identical, and the sole inserter (`versioning.py`) stamps `source_id`
  explicitly anyway. Losing nothing on isolation — RLS enforces reads.
- **Writer stays the existing superuser `rag`** (no separate `rag_writer` owner): brownfield
  preservation; a superuser bypasses RLS, which is the required "writer bypasses RLS" property.

### Blockers / need from you  *(ask before doing dependent work)*

1. **Supabase vector store** — **DECIDED: its own Phase 6 (prod/deploy only)**; keep local Docker
   pgvector for dev now. When Phase 6 starts, I'll need: (a) the connection string (session-pooler or
   direct, port 5432, `postgresql+psycopg://…`); (b) confirmation the instance runs **pgvector ≥ 0.8**
   (needed for `hnsw.iterative_scan`; Supabase may pin older); (c) how **`rag_reader` + RLS** maps onto
   Supabase roles (`authenticated`/`service_role`/`anon` + JWT-claim RLS). **Never invent a DSN.**
2. **Reranker API key (Cohere)** — ✅ **PROVIDED & USED (2026-08-07).** `.env` carries
   `RERANKER_PROVIDER=cohere` + a live `RERANKER_API_KEY`; 3.5.5 measured a real lift with it (see the
   exit-gate note above). CI still forces `FakeReranker` via `conftest.py`, so the suite stays
   deterministic. No further action.
3. **Confluence token** — still dead (401 Jira / 403 Confluence "caller cannot access Confluence").
   Blocks *live* ingestion only; all offline phases (3.5 → most of 4) run on the fixture corpus. **Exact
   fix needed from the user** (env vars live in `app/platform/config/settings.py:33-38` /
   `.env.example:1-10`):
   - Generate a **fresh Atlassian API token** at
     `https://id.atlassian.com/manage-profile/security/api-tokens`, from an account that holds an actual
     **Confluence Cloud product license/seat** — not just Jira. The 403 means the current token
     authenticates but that account isn't licensed for Confluence; a fresh token from an unlicensed
     account will fail the same way.
   - `CONFLUENCE_EMAIL` must be that same licensed account's email (Basic Auth pairs `email` +
     `api_token` in `confluence_client.py:72`).
   - Confirm `CONFLUENCE_BASE_URL` is the real site's `/wiki` base, e.g.
     `https://<your-org>.atlassian.net/wiki` (already set — just confirm it matches the account above).
   - Which spaces/pages to sync is no longer an env var (`CONFLUENCE_SPACES` was dead code, removed
     in 3.5.6) — once the token works, seed the spaces/page-subtrees to track via
     `uv run python scripts/seed_source_scope.py --root-type space --root-id <numeric space id>`
     (or `--root-type page --root-id <page id>` for a narrower subtree). Space/page ids are
     numeric Confluence content ids, not the short space *key* — get them from
     `GET {base_url}/api/v2/spaces` or a page's "Page Information" panel.
   - `CONFLUENCE_WEBHOOK_SECRET` is already set — no action needed.
   - `CONFLUENCE_SERVICE_ACCOUNT_ID` is optional — only used (`event_service.py:47-50`) to filter the
     integration's own webhook events and avoid self-triggered loops; leave empty unless the sync
     account also writes back to Confluence.
4. **Phase 5 infra (later)** — Redis for caching only if the proportionality gate is met; Langfuse
   optional. Will re-ask when Phase 5 starts.

---

## 1. Context

The Omniboost RAG backend (`apps/automation`) is offline-verified through Phase 3: **99 tests
green**, and `make eval` reproduces the retrieval baseline. A market-research brief (naive RAG
~44% → advanced RAG ~63% factual accuracy) proposes ~13 upgrade layers. Every layer was audited
against the **actual code** (three exploration passes + a design-validation pass), and the running
config was confirmed directly from `.env` and `settings.py`:

- Embeddings: OpenAI `text-embedding-3-large` @ **3072 dim** (env-driven; the code *default* is
  `voyage`, `.env` overrides to `openai`). Indexed as `halfvec(3072)` with an HNSW index.
- `reranker_provider` / `reranker_api_key` / `reranker_local_model` settings **fields exist**
  (`settings.py:62-65`, commented "used from Phase 4") but **no reranker client exists** — the
  config is dead. `.env` carries a live Cohere key.

**Why this change.** One backend + one corpus must power *multiple chatbots*, each scoped by tag to
a **source system** ("provider"), with a **hard security boundary** between scopes, easy per-source
CRUD, and the latest accuracy techniques. **Accuracy first, speed second.** Reranking (absent today)
is the user's called-out priority — essential for Confluence docs.

**Outcome.** A source-tagged, RLS-isolated, reranked, traced retrieval pipeline that is measurably
more accurate offline (Phase 3.5); then a grounded, cited, streaming chatbot on top (Phase 4); then
optimization + proof (Phase 5). Phase 0 writes the governing design doc first.

### 1.1 Product decisions (fixed by the user — do not relitigate)

1. **"Provider" = source system** (Confluence now; Zendesk / Notion / uploads later). Many sources →
   one corpus; each bot is scoped to a subset of sources.
2. **Hard security boundary** between scopes → Postgres Row-Level Security + application checks.
   **Default-deny.**
3. **Confluence-only for now** → add source/tag columns + RLS + a clean seam. Do **not** generalize
   the Confluence-specific ingestion/gateway yet; leave one activation point that takes a constant
   today and a parameter when a second source lands.

---

## 2. Current state — research vs. code (what NOT to rebuild)

**Already modern — keep as-is:**

| Capability | Where | Note |
|---|---|---|
| Parent/child chunking | `ingestion/domain/chunking.py`, `Chunk.parent_chunk_id` | parent expansion is a join away |
| Contextual retrieval | `ingestion/application/contextualizer.py` | prompt-cached |
| **RRF fusion** | `retrieval/domain/fusion.py` | research's "swap weighted-sum→RRF" is **done** |
| halfvec@3072 HNSW index | `models.py` `_HNSW_WHERE`, partial index | matches OpenAI-3072 |
| Immutable versioning + atomic activation + rollback + GC | `ingestion/application/versioning.py` | |
| 3-pass re-embed reuse gate | `ingestion/domain/chunk_diff.py` | avoids needless re-embeds |
| Deterministic SQL filtering (no LLM filters) | `search_repo.py` `_base_filters` | keeps recall honest |
| Custom eval harness + `RankFn` injection seam | `features/evaluation` | Precision@k / NDCG already computed |

**Gaps (each maps to a phase below):**

- No provider/source/tenant column anywhere — only Confluence `space_id`. → 3.5.3
- **No reranker at all** (dead `cohere` config). → 3.5.2
- No `hnsw.iterative_scan`; pgvector image is the rolling `pg16` tag (unpinned). → 3.5.1
- No request tracing (structlog only). → 3.5.4
- No query rewrite / answer generation / citations / refusal / CRAG. → Phase 4
- Principal ACL is fixture-only: the DB stores an access-scope *hash*, not principal lists. → Phase 4
- `POST /chat` absent; the web `/api/chat` route is a real 501 stub. → Phase 4
- No caching. → Phase 5
- Gold set is 12 synthetic cases; no real-ticket set. → Phase 5
- **Graph RAG stays off** (research: cost/latency unjustified for this corpus).

---

## 3. Target architecture (one line + expanded)

```
scope → conversational rewrite → embed → (RLS-scoped) dense ∥ keyword → RRF
      → permission filter → cross-encoder rerank(≤75 → k) → parent-context expansion
      → grounded generation w/ forced citations → refusal threshold → one CRAG retry → SSE stream
```

Every request writes one `query_trace` row (retrieval fields in 3.5; answer/feedback fields in 4).

Two layered security controls, both always applied:

- **Source-level RLS** (3.5): Postgres row-level security on `chunk`, keyed by `source_id`, enforced
  by a non-owner `rag_reader` role. Default-deny when the scope GUC is unset.
- **Page-level principal ACL** (4): persisted principal lists, enforced pre-search in the retriever.

---

## 4. Config & flags reference (single source of truth)

New / changed settings in `app/platform/config/settings.py` (add with safe defaults; document in
`.env.example`):

| Setting | Default | Introduced | Purpose |
|---|---|---|---|
| `database_reader_url` | `""` (falls back to `database_url` if empty) | 3.5.3 | non-owner `rag_reader` DSN for retrieval |
| `reranker_provider` | `""` → treat as `fake` offline | (exists) 3.5.2 | `cohere` \| `fake` \| `local` |
| `rerank_candidate_k` | `75` | 3.5.2 | candidates fetched before rerank |
| `rerank_depth` | `75` | 3.5.2 | max docs sent to the cross-encoder |
| `rerank_top_k` | `5` | 3.5.2 | survivors returned |
| `hnsw_ef_search` | `100` | 3.5.1 | per-txn recall knob |
| `hnsw_iterative_scan` | `relaxed_order` | 3.5.1 | safety valve under narrow RLS scope |
| `rewrite_enabled` | `true` | 4 | conversational query rewrite on |
| `refusal_min_rerank_score` | `0.10` provisional (set 3.5.5; re-tune Phase 5) | 4 | below → refuse + route to human |
| `crag_max_retries` | `1` | 4 | corrective retrieval cap (protects p95) |

**Test fixture rule (critical):** the hermetic settings fixture MUST force `reranker_provider=fake`.
`.env` carries a live Cohere key and `env=local`; the offline fallback only fires on an *empty* key,
so without this override CI would hit Cohere non-deterministically.

---

## Phase 0 — Design doc + ADRs (write first, no code)

**Goal.** Produce the A-to-Z governing document the user asked for, and lock the two decisions that
gate all Phase 3.5 code.

**Deliverables.**

- **`docs/rag/DESIGN.md`** — sections:
  1. Current pipeline (as-built, with file anchors).
  2. Target pipeline (the §3 diagram, expanded per stage).
  3. Provider-tag / RLS isolation model (roles, GUC, policy, default-deny proof).
  4. Ingestion → retrieval → answer data flow (end to end).
  5. The accuracy stack (rerank, parent expansion, citations, refusal, CRAG).
  6. Eval + tracing scoreboard (what `query_trace` captures; what eval reports).
  7. Config & flags (mirror §4).
  8. **Research-layer decision table** — each of the ~13 layers → keep / upgrade / add / reject +
     one-line rationale.
- **`docs/adr/0004-Multi-Source-Provider-Tagging-And-RLS.md`** — decision, context, the
  `source_type`/`source_id`/`tags` schema, RLS policy, role split, default-deny, consequences.
- **`docs/adr/0005-Reranking-And-Answer-Pipeline.md`** — cross-encoder-only rule (no general-LLM
  rerankers), forced citations, refusal threshold, one CRAG retry, why a fixed workflow not an agent
  loop.

**Order:** DESIGN.md before ADRs is fine, but the two ADR *decisions* must be settled before any
3.5 code.

**Gate.** User reviews `DESIGN.md` before Phase 3.5 code begins. No code in this phase.

---

## Phase 3.5 — Accuracy + tagging spine (offline-measurable, no chat)

Everything here is verifiable offline against `retrieval_smoke.json` / `permission.json` via
`test_retrieval_eval.py` and `make eval`. **Sub-steps run in this order.**

### 3.5.1 Pin pgvector ≥ 0.8 + enable iterative scan  *(must be first)*

**Why first.** RLS narrow-scoping silently over-filters HNSW (an ANN scan can return fewer than
`LIMIT` rows once the RLS predicate prunes the candidate set). `hnsw.iterative_scan` is the safety
valve — but it only exists in pgvector **0.8+**. If we ship RLS before pinning, recall drops and it
looks like a reranker regression.

**Tasks.**

1. `infra/foundation/docker-compose.yml`: change `image: pgvector/pgvector:pg16` → a pinned **0.8.x**
   tag/digest (the current tag is rolling). Record the exact digest in the compose file comment.
2. Add settings `hnsw_ef_search=100`, `hnsw_iterative_scan="relaxed_order"` (§4).
3. In the retrieval read transaction (added fully in 3.5.3's `retriever.py` work, but the GUC-setting
   helper lands here), issue per-transaction:
   `SET LOCAL hnsw.iterative_scan = 'relaxed_order'` and `SET LOCAL hnsw.ef_search = 100`.
   `relaxed_order` is acceptable because we re-rank downstream.

**Acceptance.**

- `SELECT extversion FROM pg_extension WHERE extname='vector'` returns **≥ 0.8**.
- Under a deliberately narrow `space_id`/`source_id` scope, dense search returns the full `LIMIT`
  (add a targeted test once 3.5.3 lands).

### 3.5.2 Reranker (the user's priority) — text-fetch refactor THEN wire in

**Design.** Mirror the embeddings abstraction exactly (`embeddings_client.py:43` `EmbeddingProvider`
Protocol + `_HttpEmbeddingProvider` machinery: timeout, bounded retry+backoff, circuit breaker,
abuse cap). Cross-encoder rerankers only — **no general-LLM rerankers** (ADR-0005).

**Tasks.**

1. **New `app/platform/clients/reranker_client.py`:**
   - `class RerankError(RuntimeError)`.
   - `@runtime_checkable class Reranker(Protocol)`: `model: str`; `rerank(query: str,
     docs: Sequence[tuple[int, str]], top_k: int) -> list[tuple[int, float]]` (returns
     `(page_id, score)` sorted desc).
   - `class CohereReranker` — raw `httpx`, `POST https://api.cohere.com/v2/rerank`, model
     `rerank-v3.5`, reusing the exact timeout / retry / breaker / abuse-cap discipline from
     `anthropic_client.py` / `_HttpEmbeddingProvider`.
   - `class FakeReranker` — identity: returns the input order, scores by descending input rank.
     Deterministic; used in tests and offline dev.
   - `def build_reranker(settings, client=None) -> Reranker` — factory with offline fallback:
     empty key **or** `provider in {"", "fake"}` **or** offline env → `FakeReranker`.
2. **Export** `Reranker`, `build_reranker`, `RerankError` from `app/platform/clients/__init__.py`.
3. **Data-flow refactor (not a config flip).** The retriever deals in **page ids only**; reranking
   needs text. Add to `search_repo.py`:
   ```python
   def fetch_rerank_texts(session, page_ids: Sequence[int]) -> dict[int, str]:
       # DISTINCT ON (page_id), left(title || ' ' || retrieval_content, 4000)
       # over active child chunks; subject to the same _base_filters + source scope.
   ```
4. **Wire into `HybridRetriever.retrieve`** (`retrieval/application/retriever.py:45`) **after the
   permission filter, before the top-k slice** — never rerank a doc the principal can't see:
   - Bump `candidate_k` default `40 → 75` (`rerank_candidate_k`).
   - After `allowed = [p for p in ranked if self._policy.allowed(p, scope)]`, fetch texts for the
     top `rerank_depth` allowed pages, call `self._reranker.rerank(query, docs, top_k=k)`, and
     return the reranked page ids as strings.
   - Inject the reranker via the constructor (`reranker: Reranker`), like `embedder`/`policy`.
5. **Test fixture:** force `reranker_provider=fake` in the hermetic settings fixture (§4 rule).

**Acceptance.**

- Deterministic in CI with `FakeReranker`.
- `make eval` reports **rerank lift**: Precision@5 and NDCG@10 before vs after rerank on
  `retrieval_smoke.json` (wired fully in 3.5.5).
- Feature boundaries stay clean (`make boundaries` exit 0): the retriever imports the reranker from
  `platform.clients` root, not a deep path.

### 3.5.3 Provider tagging + RLS + reader role  *(ship atomically with the eval-harness update)*

**Schema.** Add to **`page_source` and `chunk`** only (not `document_version` — retrieval never
reads it):

- `source_type String(32)` — coarse connector label. **String + CHECK constraint, not a PG enum**
  (avoids `ALTER TYPE` friction as connectors grow).
- `source_id String(128)` — the **isolation key**, e.g. `confluence:default`.
- `tags ARRAY(Text)` — free-form per-source tags for bot scoping.

**Migration** — the *first real* migration, `down_revision="0001_core_schema"`, in
`apps/automation/alembic/versions/`:

1. Add the three columns **NOT NULL with a `server_default`** so existing Confluence rows backfill
   (`source_id='confluence:default'`, `source_type='confluence'`, `tags='{}'`).
2. **Drop the server default afterward** so ingestion must set `source_id` explicitly going forward.
3. Add `Index("ix_chunk_active_source", "is_active", "source_id", postgresql_where=text("is_active"))`.
4. Add the CHECK constraint on `source_type`.
5. RLS DDL (raw SQL in the migration):
   ```sql
   ALTER TABLE chunk ENABLE ROW LEVEL SECURITY;
   ALTER TABLE chunk FORCE ROW LEVEL SECURITY;
   CREATE POLICY chunk_source_read ON chunk FOR SELECT
     USING (source_id = ANY(string_to_array(current_setting('app.allowed_sources', true), ',')));
   ```
   Unset GUC → `current_setting(..., true)` returns NULL → `string_to_array(NULL,...)` → no match →
   **default-deny**.

**ORM.** Reflect the three columns + the new index on `PageSource` (`models.py:85`) and `Chunk`
(`models.py:206`).

**Ingestion seam.** Write `source_id="confluence:default"` (and `source_type`, `tags`) at the
**single activation point** in `ingestion/application/versioning.py` (the atomic activation). A
constant today; a parameter when a second source lands.

**Role split** (`app/platform/db/engine.py`):

- Keep the existing `get_engine()` / `get_sessionmaker()` / `session_scope()` as the **`rag_writer`**
  path (owner, `BYPASSRLS`) — worker / webhook / reconcile untouched.
- Add `get_reader_engine()` / `get_reader_sessionmaker()` bound to `database_reader_url` as the
  **`rag_reader`** role (scoped, **non-owner**, no `BYPASSRLS`). `HybridRetriever` uses the reader
  sessionmaker. (Owner bypasses RLS — reads MUST run as the non-owner role.)
- `infra/foundation/docker-compose.yml`: add init SQL creating `rag_writer` (owner, BYPASSRLS) and
  `rag_reader` (login, non-owner, `GRANT SELECT` on the read tables).

**Retrieval scoping** (`retriever.py`): at transaction start, set the GUC with **`set_config`, not
`SET LOCAL`** (the latter can't bind parameters — using it here would be an injection vector or a
silent default-deny):
```python
session.execute(
    text("SELECT set_config('app.allowed_sources', :s, true)"),
    {"s": ",".join(allowed_sources)},
)
```
Plus set the 3.5.1 HNSW GUCs in the same transaction.

**Belt-and-suspenders recall** (`search_repo.py`): also add an explicit
`AND source_id = ANY(:sources)` to `_base_filters()` so the planner uses `ix_chunk_active_source`.
RLS is the *security net*; the explicit WHERE is *correctness + recall* (and lets the query planner
choose the source index).

**Eval-harness update (same PR — do not split).** `test_retrieval_eval.py` builds the retriever as
the **writer** today. Switching retrieval to the reader makes it RLS-subject → **0 rows** unless it
sets `app.allowed_sources` to the fixture `source_id`. So, in the same PR:

- Extend the test DB harness (`confluence_sync/tests/conftest.py` pattern) to create the `rag_reader`
  role (or expose a scoped-reader session) and set `app.allowed_sources` to the fixture source.
- Add a **negative isolation test**: a query scoped to a *wrong* `source_id` returns **zero** rows
  (RLS default-deny), and the reader role cannot see unscoped rows.

**Acceptance.**

- `make check` (boundaries + `pytest -q`) green; existing 99 tests still pass.
- Positive: query scoped to `confluence:default` returns rows.
- Negative: wrong `source_id` → zero rows; reader cannot see unscoped rows.
- Migration is reversible (`alembic downgrade -1` restores 0001 state).

### 3.5.4 Request tracing scoreboard

**Task.** New `QueryTrace` ORM model + migration (`query_trace` table), written via the **writer**
engine so RLS never blocks trace inserts and Phase-4 feedback can `UPDATE` the row later.

Columns populated **now** (3.5.4 retrieval): `id`, `raw_query`, `retrieved_page_ids`, `allowed_sources`
(isolation audit), `embedding_model`, `reranker_model`, `latency_ms`, `created_at`. Columns **nullable,
filled in Phase 4**: `retrieved_chunk_ids` + `rerank_scores` (deferred — the retriever returns page ids
only and discards the rerank scores today; **Phase 4.2 refactors `HybridRetriever.retrieve`'s return to
surface scores + chunk ids and persists both here**), plus `rewritten_query`, `answer`, `citations`,
`feedback`.

structlog stays for ops logging; Langfuse remains an optional future exporter (not built here).

**Acceptance (as shipped).** Each retrieval writes one `query_trace` row carrying `retrieved_page_ids` +
`allowed_sources` + models + latency. `rerank_scores` / `retrieved_chunk_ids` are Phase-4 columns (see
above) — the model docstring already marks them "reserved for Phase 4".

### 3.5.5 Measure ✅ done

**Task.** Extend `features/evaluation/run_baseline.py` / `runner.py` to report **rerank lift** —
Precision@5 and NDCG@10 **before vs after** rerank — while keeping the report format comparable to
the existing baseline. This is the phase's accuracy proof.

**What shipped.**
- `evaluate_rerank_lift(dataset, before_fn, after_fn, …)` + `RerankLiftReport` in `features/evaluation`
  (pure; exported from the feature root), computing precision@5 / ndcg@10 before/after + Δ.
- `run_baseline.py`: `write_rerank_lift_reports` + `_print_saved_rerank_lift`, so `make eval` echoes the
  saved before/after table (`eval-reports/rerank_lift.{json,md}`).
- The **real** before/after run is the DB-backed integration test `test_rerank_lift_before_vs_after`
  (reader role + RLS + indexed corpus): "before" = order-preserving `FakeReranker`, "after" =
  configured reranker. Writes the artifact under `EVAL_WRITE_RERANK_REPORT=1`.
- `refusal_min_rerank_score = 0.10` provisional setting (+ `.env.example`).
- Tests: 3 unit (`test_rerank_lift.py`: positive/zero/empty) + 1 integration → **120 tests green**.

**Measured (live Cohere `rerank-v3.5` + OpenAI-3072, 6-case `retrieval_smoke`):** precision@5
0.200→0.200 (+0.000); **ndcg@10 1.000→0.877 (−0.123)**. Negative *by construction*: dense already ranks
the one relevant page first (before-ndcg saturated at 1.000), so the cross-encoder has no headroom. The
genuine lift is a **Phase-5 gold-set measurement**; `refusal_min_rerank_score` re-tunes there. CI
(`FakeReranker`) → before == after → zero lift, deterministic.

**Acceptance.** ✅ `make eval` prints the before/after table (echoed from the saved artifact). The
threshold is set provisionally (0.10) pending the Phase-5 gold set — the fixture is too saturated to tune
it honestly.

**Phase 3.5 exit gate — MET (2026-08-07):** `make check` green (120), `make eval` shows the rerank table,
isolation tests pass, pgvector 0.8.5 pinned (≥ 0.8), every retrieval traced. No-regression on ruff/pyright
(ADR-0003 D1: 22/2 ruff ≤ 25/2; pyright 0/0 on touched files).

---

## Phase 4 — Answer runtime + chat (the actual chatbot)

**Goal.** A grounded, cited, streaming chatbot over the 3.5 spine. Fixed workflow, not an agent loop.

### 4.1 New `rag_agent` feature (own public root)

Create `app/features/rag_agent/` per the repo standard: one public `__init__.py` re-exporting the
answer service and its DTOs. Internal layout `application/` (orchestration), `domain/` (prompt
assembly, citation enforcement, refusal logic), `infrastructure/` (trace read/update, principal ACL
store). Add a `FEATURES.md` documenting the public boundary.

### 4.2 Answer workflow (fixed pipeline)

Order, each stage a plain function (research + repo standard — no agent loop):

1. **Conversational query rewrite** — multi-turn history → standalone query. One cheap LLM call
   (`routing_model`), always on (`rewrite_enabled`). Store `rewritten_query` in the trace.
2. **RLS-scoped retrieve → RRF → rerank** — reuse `HybridRetriever` (reader engine, scoped GUC).
   **Refactor `retrieve`'s return** so it surfaces the rerank **scores** (needed by step 5's refusal)
   and the retrieved **chunk ids** (needed by step 3) instead of only page-id strings — today it
   discards both. **Persist `rerank_scores` + `retrieved_chunk_ids` on the `query_trace` row** at the
   same time (these columns were deferred from 3.5.4; the model already reserves them). Extend
   `write_query_trace` + its 3.5.4 test to assert both are now non-NULL.
3. **Parent-context expansion** — join `parent_chunk_id` and feed the *parent* chunk text to the
   generator (children retrieve, parents ground).
4. **Grounded generation with forced numbered citations** — every claim cites a retrieved chunk;
   **uncited claims are stripped** before returning.
5. **Refusal threshold** — if the top rerank score < `refusal_min_rerank_score`, refuse ("not in the
   docs") and route to a human instead of hallucinating.
6. **One CRAG corrective retry** — on a weak result, one corrective retrieval only
   (`crag_max_retries=1`) to protect p95.

### 4.3 Real principal ACL storage

Replace the fixture-backed `PrincipalPermissionPolicy` (`retrieval/domain/permission.py`): persist
**principal lists** (not just the access-scope hash), queryable, and enforce **pre-search** alongside
RLS. Source-level RLS (3.5) and page-level principal ACL (here) are distinct layers — **both apply**.

### 4.4 `POST /chat` SSE endpoint

In `app/main.py`, add `POST /chat` streaming SSE events `start` / `token` / `citations` / `done`,
wired to the **reader** engine (must not be wired before 3.5's reader+RLS exist). Add
`PATCH /chat/{trace_id}/feedback` (thumbs up/down → `UPDATE query_trace.feedback`, writer engine).
Apply the `securing-http-and-llm-endpoints` controls (this is both an HTTP and an LLM surface):
auth, rate limit, input validation, timeout/retry/breaker, output rate limit, PII redaction,
idempotency, audit logging, cost/abuse caps.

### 4.5 Web chat UI

Flesh out the existing `apps/web/src/features/chat` scaffold:

- `api/chat-client.ts` — SSE parsing.
- `ui/` — streaming message list, history, citation cards (scaffold files already exist:
  `message-list.tsx`, `chat-panel.tsx`, `composer.tsx`).
- `apps/web/src/app/api/chat/route.ts` — replace the 501 stub with the real SSE proxy to the backend.
- `.env.local` — `NEXT_PUBLIC_API_BASE_URL`.
- Publish the chat contract in `packages/contracts` (extend `src/openapi/chat.yaml` + `src/index.ts`).
- Thumbs up/down → `PATCH /chat/{trace_id}/feedback`.

**Phase 4 acceptance (e2e).** Ask a question in the web UI → a streamed, grounded, correctly-cited
answer scoped to the permitted sources; refusal fires below threshold; feedback updates the trace
row. `make check` green; boundaries clean; no-regression on ruff/pyright.

---

## Phase 4.6 — Fixes-backlog remediation (gates Phase 5.4) ⬜ todo

**Origin.** Six independent audit agents re-ran tests/boundaries/ruff/pyright live and read code
directly (not trusting this ledger's self-report) across Phases 0, 1, 2, 3, 3.5, and 4 on
2026-08-10, writing findings to `docs/rag/fixes/` (`README.md` index + one file per phase). They
found real unresolved bugs — including one CRITICAL access-control bypass and one HIGH
cross-principal data leak — in phases this ledger had already marked ✅ done with "no gaps found."
Phase 5 itself was excluded (5.4+ isn't built yet, no findings possible).

**Gate.** `Phase 5.4` (live-LLM red-team + latency/cost proof), the embedder bake-off, and adaptive
routing may **not** resume until every `4.6.x` sub-step below is ✅ and the 4.6.16 exit gate is
green. Numbered `4.6` (not `5.0`) because every finding originates in already-shipped Phase 0–4
code — this is closing out that phase's own debt, not new Phase-5 feature work.

Severity-first order; CRITICAL/HIGH block everything else. Batched where low-risk/same-file,
isolated where high-risk (signature changes, migrations, or a decision only the user can make).

### 4.6.1 — Confluence group-restriction fail-closed mitigation (CRITICAL) ✅ done (2026-08-10, `4d0ba70`)

**Status: implemented, tested (10 new tests), boundaries clean, no ruff/pyright regression
(file-level diffed, not just counted) → 229 tests total (was 219).** Pure code fix, no migration,
exactly as scoped.

**Fix.** New shared pure resolver `_resolve_read_restriction(restrictions: dict) -> list[str]`
(`app/platform/clients/confluence_client.py`) — parses a Confluence read-restriction record's
`user.results[].accountId` as before, but now also inspects `group.results`: if group entries
exist and no user principal resolved, returns `[GROUP_RESTRICTED_SENTINEL]` (a literal string no
real caller can ever be) instead of `[]`. A page keyed by the sentinel is inaccessible to every
principal-scoped caller — fail-closed — until group-membership expansion (4.6.2) resolves it to
real account ids. Both `HttpConfluenceClient.get_restrictions` (live REST v2) and
`FixtureConfluenceGateway.get_restrictions` (offline/test double) now call this one resolver
instead of each duplicating the same user-only parse — importing it by full submodule path per
this package's own internal-imports rule (`platform/clients/__init__.py`'s docstring), not
through the root.

**Scope decision — did not touch the fixture corpus.** The plan's phrasing ("a fixture page
restricted only by group persists as inaccessible") could be read as calling for a new
group-only fixture page exercised through the full `handle_sync_page` → `page_restriction` →
`PrincipalPermissionPolicy.allowed()` chain. Investigated and deliberately declined: the shared
fixture corpus backs `_index_corpus`, reused across dozens of retrieval/eval/chat-endpoint tests
(`test_retrieval_eval.py`, `test_answer_workflow.py`, `test_chat_endpoint.py`, evaluation
datasets) — adding or repurposing a page risks perturbing exact-count/ranking assertions far
outside this fix's blast radius, for a link (`page_restriction` row → denied access) already
proven correct by the existing 4.3 tests. Proved the fix instead at its exact boundary — new
`app/platform/clients/tests/test_confluence_client.py` (10 tests, none existed for either client
before this sub-step): the pure resolver (group-only → sentinel; user-only → unaffected; mixed
user+group → user kept, matching the still-deferred-to-4.6.2 limitation; empty → unrestricted)
and both gateways end-to-end (`HttpConfluenceClient` via `httpx.MockTransport`;
`FixtureConfluenceGateway` via a monkeypatched stub loader, including proving the test-only
`set_restrictions` mutator still bypasses resolution for already-expanded principal sets).

**Existing test fixed, not just re-asserted (per the audit finding).**
`test_worker_sync.py::test_first_index_persists_restrictions` indexes fixture page 2002, which
carries a resolvable user (`acct-carol`) *and* two unresolved groups (`grp-hr`/`grp-finance`) —
under this fix the persisted ACL is unchanged (`{"acct-carol"}`, since a resolvable user is
present), so the assertion value didn't need to change, but the audit correctly flagged that the
test's docstring gave no indication the groups existed or were being dropped. Rewrote the
docstring to state the accepted-for-now limitation explicitly and point at the new regression
test that actually covers the group-only bypass.

**Not done (deferred to 4.6.2, needs the user's input on API scope/cost before starting):**
resolving group membership to real account ids. The sentinel is the permanent answer if that
input says no; otherwise 4.6.2 replaces it with the expanded member set.

`HttpConfluenceClient.get_restrictions` and `FixtureConfluenceGateway.get_restrictions`
(`apps/automation/app/platform/clients/{confluence_client,fixture_confluence_client}.py`) parse
only `restrictions.user.results[].accountId`, never `restrictions.group.results[]` — a page
restricted **only** by a Confluence group syncs as fully unrestricted through the chatbot. Fix: when
a restriction payload has group entries but no resolvable user principals, return a fail-closed
sentinel (page stays inaccessible to everyone but the sync/admin path) instead of `[]`. Tests: a
fixture page restricted only by group persists as inaccessible to a principal outside that group;
fix the existing `test_worker_sync.py::test_first_index_persists_restrictions` assertion, which
today encodes the bug as expected behavior. Pure code fix, no migration.

### 4.6.2 — Confluence group-membership expansion (CRITICAL)

The real fix once 4.6.1's mitigation is live: resolve each `group.results[].name`/`id` to member
`accountId`s via the Confluence group-members API (cacheable per sync run) and union those into the
persisted `page_restriction` principal set. **Needs your input before starting:** confirm the
Confluence API token/scope can call the group-members endpoint, and accept the added per-sync API
cost — if the token can't be granted that scope, 4.6.1's fail-closed behavior becomes the permanent
answer and this sub-step is descoped (document as an accepted limitation, don't guess). Tests: a
group member can retrieve the page; a non-member cannot; repeated pages sharing a group don't
re-fetch membership every time.

### 4.6.3 — Idempotency cache cross-principal leak (HIGH)

`_idempotency_cache` in `apps/automation/app/features/rag_agent/server/router.py` keys only on the
raw `Idempotency-Key` header string — a replay with a **different** `principal`/`history` silently
returns the first caller's cached `Answer` including citations. Fix: bind the cache key to a hash of
`(idempotency_key, principal, history)`, mirroring `answer_cache.py`'s already-correct
`_cache_key` pattern. On a mismatch, recompute rather than serving the stale cache. Tests: replay
same key + different principal → not the first caller's answer; replay same key + different history
→ same; existing same-key/same-body regression test stays green. Pure code fix, no migration.

### 4.6.4 — Rate-limiter/idempotency hardening batch (MEDIUM-HIGH + MEDIUM, batched)

Same file cluster (`rag_agent/server/router.py`, `apps/automation/app/shared/rate_limiter.py`),
reviewed together:
- `_rate_limit_key` prefers the untrusted, caller-supplied `principal` over IP — trivially bypassed
  by rotating `principal`, defeating `chat_rate_limit_per_minute`. Fix: key primarily on IP; fold
  `principal` in only as a non-bypassable secondary suffix, or drop it from the key entirely.
- `SlidingWindowRateLimiter` never prunes empty buckets → unbounded memory growth. Fix: prune
  zero-length buckets in `allow()`, and/or add a bounded eviction policy.
- The idempotency `TTLCache` in `router.py` has no `max_entries` bound (unlike its Phase-5 sibling).
  Fix: add a `chat_idempotency_cache_max_entries` setting, mirroring `chat_answer_cache_max_entries`.

Tests: same IP + rotating `principal` within one window → the Nth request is 429; many distinct
limiter keys pushed then drained → bucket count stays bounded; pushing more than the configured max
distinct idempotency keys → oldest evicted. Pure code fix, no migration.

### 4.6.5 — `rollback_to` doesn't restore `PageSource`'s cached hashes (MEDIUM-HIGH)

`apps/automation/app/features/confluence_sync/application/versioning.py::rollback_to` never copies
the target `DocumentVersion`'s `content_hash`/`structure_hash`/`parser_version`/etc. back onto
`PageSource` — a rollback can leave the corpus silently pinned to a stale version, because the next
sync's freshly computed hashes wrongly match the stale cached ones and `classify()` reports
`no_change`. Fix: copy those fields back on rollback. **Needs your input:** `PageSource` fields with
no `DocumentVersion` counterpart (`title`, `labels_hash`, `access_scope_hash`, etc.) have nothing
correct to restore — recommend leaving them as pre-rollback values (self-heals on the next
reconciliation sweep) rather than forcing a metadata re-fetch; confirm before closing this out.
Tests: rollback then sync an unchanged page → `classify()` reports `no_change` correctly; rollback
then sync a page with a real newer revision → change is detected, not spuriously masked. No
migration (no schema change, only which values get written).

### 4.6.6 — `permission.py`'s overloaded `scope` string (MEDIUM)

`apps/automation/app/features/retrieval/domain/permission.py`'s `allowed()` distinguishes
space-wide vs. principal trust only via `.isdigit()` on one untyped `scope: str | None` — the root
cause of the already-fixed 5.3 numeric-principal bypass, still unguarded at the domain layer, so any
future direct caller could reintroduce the same bug class. Fix: replace with two explicit params
(`space_id: int | None`, `principal: str | None`) or a tagged union; update the
`retrieval/application/retriever.py` call site to pass the pre-classified value. Isolated (signature
change, call-site fallout), not batched. Tests: a domain-layer regression test proving an all-digit
principal id can never be reinterpreted as space-level trust; existing grant/block tests pass under
the new signature.

### 4.6.7 — Confluence client hardening batch (MEDIUM + INFO, batched)

`apps/automation/app/platform/clients/confluence_client.py`, one review pass: add a
consecutive-failure circuit breaker (mirroring `embeddings_client.py`'s pattern); fix the retry
predicate to retry on 5xx (it currently excludes `httpx.HTTPStatusError` entirely, contradicting
`how_this_works.md`'s documented "retry on 5xx" claim); the assigned-but-never-called `log` gets
actual audit log lines (on retry, on 4xx/5xx). New dedicated test file (none exists today — every
confluence_sync test runs against the fixture gateway only): 5xx is retried; breaker trips after N
consecutive failures; 4xx is still not retried; a log line is emitted on retry/4xx/5xx.

### 4.6.8 — Duplicate CHECK constraint from a naming-convention bug (MEDIUM)

Migration-built vs. `create_all`-built schemas silently diverge: explicit `name="ck_chunk_source_type"`
in `apps/automation/app/platform/db/models.py` collides with the naming-convention-generated name,
producing a duplicate constraint (`ck_chunk_ck_chunk_source_type`) — harmless today (same predicate),
risky if `source_type`'s allowed values are ever extended. Fix: wrap explicit constraint names in
`sqlalchemy.schema.conv(...)` (or drop `name=` and let the convention generate it once); add a new
Alembic migration dropping the erroneous duplicate on already-migrated DBs, with a tested, reversible
`downgrade()`. Isolated — needs a migration, must be tested against a scratch DB, not the shared dev
DB. Tests: `Base.metadata` produces exactly one CHECK constraint per table with the canonical name;
migration up/down round-trip confirmed.

### 4.6.9 — Pyright baseline reconciliation (MEDIUM, governance)

The pyright baseline crept 31→34 errors across Phase 4, reported "unchanged" session-over-session
but never reconciled against ADR-0003's actual recorded baseline. **Needs your input:** identify the
3 regressed errors (git-bisect the relevant commits) and either (a) fix them and restore the true
baseline of 31, or (b) formally amend ADR-0003's D1 baseline to 34 with a recorded justification in
this ledger's "Deviations already taken" section — default to (a) unless investigation shows they're
low-value/hard-to-fix, in which case propose (b) explicitly. Also fix root `CLAUDE.md`'s stale
baseline numbers once reconciled (run this **before** 4.6.15, so 4.6.15's doc pass writes the final
numbers, not another stale snapshot).

### 4.6.10 — RLS reader-role no-op outside offline envs (LOW)

`get_reader_engine()` (`apps/automation/app/platform/db/engine.py`) silently falls back to the
RLS-bypassing writer connection when `DATABASE_READER_URL` is unset — only proven correct inside the
test harness, which does wire a real `rag_reader`. Fix: extract the existing `_OFFLINE_ENVS`
convention (currently duplicated in `embeddings_client.py`/`reranker_client.py`) to a shared
`Settings.is_offline_env()`, then warn or fail-closed when the reader URL is unset **outside** that
offline set. **Needs your input:** warn-only or fail-closed for a real deployment — small, cheap
question. Tests: parametrized over offline-env + unset (no warning) vs. non-offline-env + unset
(warning/raise per chosen behavior) vs. reader URL set (never warns, any env).

### 4.6.11 — Event dedup ignores `delivery_id` collisions (LOW)

`apps/automation/app/features/confluence_sync/infrastructure/event_repo.py::record_event` only
guards the `payload_hash` unique constraint via `on_conflict_do_nothing`, not the separate
`delivery_id` partial-unique index — a same-`delivery_id`/different-hash redelivery raises an
uncaught `IntegrityError` (500) instead of deduping gracefully. Fix: catch that specific violation
(or pre-check `delivery_id`) and return the same graceful `duplicate=True` outcome. Test: two
envelopes, same `delivery_id`, different `payload_hash` → second delivery dedupes gracefully, not a
500.

### 4.6.12 — `Answer.refusal_reason` never reaches an observable surface (LOW)

Computed and unit-tested but never reaches a log line, DB column, SSE event, or the TS contract.
**Needs your input:** default to the minimal fix — add `refusal_reason` to the existing
`chat_request` structured log line in `router.py` (operator-visibility only, no schema/contract
change) — unless you want it exposed to end users via `query_trace`/SSE/the web contract, which is a
larger, cross-boundary change overlapping the UI-refactor track. Test: the log line includes a
populated `refusal_reason` on a refused answer, absent/null otherwise.

### 4.6.13 — Dead-code disposition batch (no code risk)

Record decisions, mostly "no action": `JobStatus.leased`/`.cancelled` (unused, backs a native PG
enum — recreating the type for near-zero benefit isn't worth it, document as accepted no-op);
`@runtime_checkable` protocols with zero `isinstance` call sites (harmless, document intent, no
action); `evaluation/metrics/latency_metrics.py` (unwired — its wiring belongs to Phase 5.4 itself,
not this backlog, no action here); `attachment_extraction.py` (fully built, zero call sites,
attachment content not currently searchable — don't delete working code on spec; add a "PARKED" note
wherever ingestion capabilities are described, folded into 4.6.15).

### 4.6.14 — `how_this_works.md` staleness rewrite (doc drift, isolated)

`docs/rag/how_this_works.md` still describes the pre-3.5 system in §§1–9: stale
phase/test-count banner, dotted "PLANNED" pipeline stages that are actually shipped, §7's "not
wired to HTTP yet" framing (Phase 4 is done), §7.2's false "principal ACL is fixture-only" claim
(false since 4.3), a 9-vs-10-table undercount (missing `page_restriction`), and a dead TOC anchor.
Full rewrite to match the shipped state `DESIGN.md`'s banner already correctly describes. Isolated
as its own sub-step — the largest doc job, kept separate so 4.6.15's batch stays small.

### 4.6.15 — Remaining doc-drift batch (batched, run after 4.6.9)

`docs/rag/DESIGN.md` §1's self-contradicting "Confirmed gaps" paragraph (claims reranker/tracing/
chat/citations/refusal/CRAG are absent; all shipped since 3.5.2–5.2); `evaluation/README.md`'s
nonexistent `"security"` eval kind; `FEATURES.md`'s missing 3.5.5 rerank-lift exports; root
`CLAUDE.md`'s stale ruff/pyright baseline (write the numbers 4.6.9 settled on, not another
snapshot); `QueryTrace.rerank_scores`' stale "reserved for Phase 4" docstring (populated since 4.2);
the `attachment_extraction.py` PARKED note carried over from 4.6.13.

### 4.6.16 — Exit gate ⬜ todo

Re-run `make check` (backend + web), `make boundaries`, `uv run ruff check .` / `ruff format --check
.`, `uv run pyright` repo-wide. Confirm zero regressions vs. whatever 4.6.9 established as the final
baseline; every new test added across 4.6.1–4.6.12 is green; this ledger has one row per `4.6.x`
sub-step with commit ref + test-count delta + any deviations, per the existing convention. Only once
this gate is green does Phase 5.4 / the embedder bake-off / adaptive routing resume.

---

## Phase 4.7 — UI component refactor (Obi widget) ⬜ todo *(independent; does not gate Phase 5)*

**Source of design truth:** `/Users/matissevansteenbergen/Downloads/Obi chatbot UI mockups/`
(specifically `Obi Assistant.dc.html` + `support.js`) — the user-supplied mockup this entire phase
rebuilds. It's a proprietary prototyping-tool export (design/behavior reference only, not usable
code): one floating widget (launcher → teaser → panel), a fake Stripe-style dashboard backdrop
(irrelevant, ignore it), and zero real backend calls (all "AI" replies are canned keyword-matched
strings) — only its UI/interaction shapes carry over, not any code or fake logic.

**Goal.** Rebuild `apps/web`'s chat UI to look and behave exactly like that mockup, as a proper
component library, without losing or forking any existing real functionality (SSE streaming,
citations, refusal handling, feedback, security controls). Target: `apps/web` only. Nothing in
`apps/automation` changes in this phase — the repo-separation work this enables is its own next
phase, **4.8**.

**Product decisions already made (binding, do not relitigate):**
- Adopt the mockup's exact visuals now as the real Omniboost brand tokens — Stripe-style light
  theme, `#635bff` purple accent, Inter font — applied app-wide, not scoped to just the widget.
- The floating chat widget (launcher + teaser + panel) is the primary deliverable. The existing
  full-page `/chat` route stays working (already built/tested) sharing the same live conversation
  session as the widget, but gets no further design investment — all mockup-fidelity work targets
  the widget.
- Screenshot capture: dropped entirely — no button, no flash animation, no fake attach. Zero real
  capability exists to back it (see `docs/future-ideas/IDEAS.md` idea #3 for what a real version
  would need).
- File attachment: shipped as an honest disabled stub (visible, not functional) — no upload endpoint
  exists yet.
- Language switcher (6 locales): shipped as a stub — menu renders, current locale shown, selecting
  closes with no-op. No partial/fake translation.
- "Developer docs"/"Support articles" menu items: disabled stubs until real URLs exist.
- "Restart conversation": built real (trivial local-state reset).
- Assistant display name: **"Obi" is the mockup's placeholder name, not a confirmed product
  decision** — pass it as a prop/config value, confirm the real name with the user before ship.

**Architecture decision (D0) — shared session, not two conversations.** Extract the conversation
state machine currently inline in `apps/web/src/features/chat/ui/chat-panel.tsx` (`useState`/
`useRef`/`streamChat`/`sendFeedback`) into a `ChatSessionProvider`/`useChatSession()` context,
mounted once in `apps/web/src/app/layout.tsx`. Both the existing full-page `ChatPanel` and the new
floating `ChatWidget` read the same live session — otherwise the widget and the page would run two
independent, contradictory conversations the moment both are visible. Pure refactor of existing
logic; SSE/citations/refusal/feedback behavior is unchanged. Write a characterization test of
current `ChatPanel` behavior *before* extracting, to guarantee no regression.

**Design tokens** (`packages/design-tokens/src/tokens.ts`, currently a "neutral for Phase 1"
placeholder) — replace with the mockup's real values; add missing semantic groups: `color.accentHover`,
`color.accentSecondary`, `color.surfaceSunken` (distinct fill for user-message bubbles vs. cards),
`shadow.{sm,md,lg}` (no elevation scale exists today), `zIndex.{widget,widgetMenu}` (no overlay UI
exists today), `motion.{fast,base,slow,easing}` (no motion tokens exist today). Existing `radius`
and `spacing` tokens are already sufficient — reuse as-is. Font swap to Inter via
`next/font/google` in `apps/web/src/app/layout.tsx` — flagged as app-wide since the home page shares
the same layout.

**Animation approach:** plain CSS `@keyframes` in `apps/web/src/app/globals.css`, driven by the new
`motion.*` tokens — no animation library added (none exists today; repo precedent is a bare
`motion-safe:animate-pulse` already in `message-list.tsx`). Every keyframe gets a `motion-reduce:`
fallback. Keyframes needed: menu fade/slide, feedback-thumb bounce, typing shimmer, launcher
pulse-ring. No screenshot-flash keyframe (feature dropped).

**New components** (all in `apps/web/src/features/chat/ui/`, none promoted to
`apps/web/src/components/` yet — each has exactly one consumer today; `Menu`/`IconButton` are the
top promotion candidates the day a second feature needs a dropdown or icon button):
`icon-button.tsx`, `assistant-mark.tsx`, `message-bubble.tsx` (extracted from current inline markup
in `message-list.tsx`), `typing-indicator.tsx`, `suggestion-chip.tsx`, `menu.tsx` + `menu-item.tsx`
(shared dropdown shell for both the "···" and language menus), `panel-header.tsx`,
`language-menu.tsx`, `chat-launcher.tsx`, `teaser-popup.tsx`, `floating-frame.tsx`, `panel-body.tsx`
(composition root shared by both `ChatPanel` and `ChatWidget`), `chat-session-provider.tsx` (D0),
`use-widget-visibility.ts` (teaser timing: 3s after mount if closed, 20s after each close),
`chat-widget.tsx` (new public export alongside existing `ChatPanel`).

**Test infrastructure (new):** `@testing-library/react` + `@testing-library/jest-dom` added to
`apps/web/package.json` — no existing pure-node vitest pattern can express DOM-rendering assertions.
`apps/web/vitest.config.ts` gets `environmentMatchGlobs` so existing pure-node tests stay
fast/unaffected while new `*.test.tsx` files run under jsdom.

### 4.7.1 — Tokens, test tooling, base primitives ⬜ todo

`packages/design-tokens/src/tokens.ts` + `tailwind-theme.ts` (new token groups above); `apps/web/tailwind.config.ts`
spreads them; `apps/web/src/app/globals.css` gets the `@keyframes` block; `apps/web/src/app/layout.tsx`
wires `next/font/google` Inter; add RTL + jsdom test infra (`package.json`, `vitest.config.ts`, new
`apps/web/src/test-setup.ts`); new `icon-button.tsx`, `assistant-mark.tsx` + tests. No visible
behavior change beyond typography/colors. **Gate:** tokens compile, Tailwind/Next build clean,
existing 39 tests + new primitive tests green, no visual regression on `/chat` besides font/color.

### 4.7.2 — Message rendering + composer ⬜ todo

Write `chat-panel.test.tsx` (characterization) **before** touching logic. Extract
`chat-session-provider.tsx` (`ChatSessionProvider`/`useChatSession`) from `chat-panel.tsx`; add real
`restart()`. New `message-bubble.tsx`, `typing-indicator.tsx`, `suggestion-chip.tsx`; modify
`message-list.tsx`, `composer.tsx` (disabled attach stub, autosize textarea). **Gate:** `/chat`
visually matches the mockup's thread+composer; all prior + new tests green; `chat-client.ts`/
`route-handlers.ts`/contracts untouched.

### 4.7.3 — Panel chrome: header, menus, restart ⬜ todo

New `menu.tsx`, `menu-item.tsx`, `panel-header.tsx`, `language-menu.tsx`; new `panel-body.tsx`
composing header+list+composer; `chat-panel.tsx` now renders `PanelBody variant="page"`. Restart
wired to real `useChatSession().restart()`; docs/support items disabled-stub; language items no-op.
**Gate:** header/menu interactions match the mockup (minus screenshot, dropped by design); restart
genuinely clears the thread; nothing pretends to work that doesn't.

### 4.7.4 — Floating widget: launcher, teaser, global mount ⬜ todo

New `use-widget-visibility.ts`, `chat-launcher.tsx`, `teaser-popup.tsx`, `floating-frame.tsx`,
`chat-widget.tsx`. `apps/web/src/app/layout.tsx` mounts `ChatSessionProvider` around `{children}` and
`<ChatWidget />` globally. `apps/web/src/features/chat/index.ts` exports `ChatWidget` alongside
`ChatPanel`. Update `apps/web/src/features/chat/FEATURES.md`. **This is the primary deliverable —
full launcher→teaser→panel flow, mockup-matching timing/animations.** **Gate:** run a
visual-verification pass (live browser, not just tests) before calling this phase done.

**4.7.5 (backlog, not built now):** real file-upload endpoint, real i18n system, real docs/support
pages, real page-context/screenshot tool — each its own future-scoped decision, recorded in
`docs/future-ideas/IDEAS.md`, not part of this phase.

**Sequencing vs. Phase 4.6:** frontend-only (TypeScript), touches zero files in common with 4.6
(backend Python) — may run before, after, or interleaved with it. Recommend finishing 4.6's
CRITICAL/HIGH items (4.6.1–4.6.3) first simply to keep one security-sensitive thread open at a time;
otherwise fully independent. Do not start 4.7.1 merely because 4.6 is done — like every phase here,
it needs an explicit go-ahead each step. **Do this phase before 4.8** — split the repo once the
widget's real file layout is settled, not mid-refactor.

---

## Phase 4.8 — Frontend/backend repository separation ⬜ todo *(supersedes ADR-0006's deferral — see ADR-0007)*

**Decision context.** ADR-0006 (2026-08-10) recorded a deferral of repo/package splitting until a
second real product deployment existed, per the global proportionality gate ("two independent
consumers exist today"). The user has since directed this to happen regardless, for separation of
concerns (frontend reusable across future products independent of any single deployment's timeline,
backend independently deployable/versioned). **ADR-0006 is superseded by `docs/adr/0007-Frontend-
Backend-Repository-Separation.md`, which records this reversal and the actual decision.** Do this
phase after **4.7** — split the widget's real, settled file layout once, not mid-refactor.

**Goal.** `apps/web` (frontend) and `apps/automation` (backend) become independently deployable and
independently versioned — able to live in separate git repositories — with `packages/contracts` and
`packages/design-tokens` as the *published, versioned* interface between them instead of pnpm
workspace `workspace:*` links (which only resolve inside one monorepo checkout).

### 4.8.1 — Publish `packages/contracts` and `packages/design-tokens` as versioned packages ⬜ todo

Today `apps/web`'s `package.json` depends on both via `workspace:*` — that only resolves inside this
one pnpm workspace. Before either app can leave the monorepo, both packages need a real publish
target (a private npm registry or GitHub Packages — **needs your input**: which registry) and
semantic versioning discipline (a breaking contract change is a major version bump, consumed
explicitly by each app, not silently picked up). `apps/automation` defines its own Pydantic models
against the same wire shapes directly (no codegen) per `packages/contracts`' existing design note —
that stays true; only the *distribution* mechanism changes, not the "hand-authored on both sides"
convention.

### 4.8.2 — Extract `apps/web` into its own repository ⬜ todo

New repo (name **needs your input** — e.g. `omniboost-rag-web`), git history preserved via
`git subtree split` or `git filter-repo` (not a fresh copy — keep blame/history). Its `package.json`
switches `@omniboost/contracts`/`@omniboost/design-tokens` from `workspace:*` to real published
version ranges (4.8.1). New standalone CI (lint/typecheck/test/build) — currently piggybacks on the
monorepo's root scripts, which won't exist once this repo is standalone.

### 4.8.3 — Extract `apps/automation` into its own repository ⬜ todo

New repo (name **needs your input** — e.g. `omniboost-rag-automation`), same history-preserving
extraction. Its `Makefile`/`uv` toolchain and `alembic/` migrations move with it unchanged (already
self-contained, per ADR-0003). New standalone CI (`make check`, `make boundaries`, ruff, pyright).

### 4.8.4 — Decide the origin monorepo's fate ⬜ todo *(needs your input)*

Options: (a) archive it once both extractions are verified working; (b) keep it as a thin umbrella —
`infra/` (local Docker Postgres for combined local dev), `docs/adr/`, `docs/rag/`, root `CLAUDE.md` —
referencing the two new repos as git submodules or just documentation links, for anyone who wants
"run both together locally" without cloning three repos. Recommend (b) for local-dev ergonomics
unless you'd rather each repo be fully self-contained for local dev too (bigger duplication, simpler
mental model) — **confirm which before executing**.

### 4.8.5 — CI/CD and secrets per repo ⬜ todo

Each new repo gets its own pipeline (currently one root pipeline, if any exists — verify) and its own
secrets scope (`CHAT_API_KEY`, `CONFLUENCE_*`, `ANTHROPIC_API_KEY`, etc. belong to the backend repo
only; the frontend repo needs only `CHAT_API_KEY` + `AUTOMATION_API_BASE_URL` for its proxy). No
secret should live in a repo that doesn't need it.

### 4.8.6 — Update governing docs ⬜ todo

Supersede or amend `docs/adr/0001-Archetype-And-Stack.md` (currently describes one monorepo archetype)
to reflect the multi-repo topology; write the ADR-0007 superseding ADR-0006 (see decision context
above — do this first, before 4.8.1, so the rest of this phase executes against a recorded decision,
not tribal knowledge); update root `CLAUDE.md`'s "Layout" section once the split is real (it currently
documents the monorepo `apps/`/`packages/` layout as fact).

### 4.8.7 — Exit gate ⬜ todo

Both repos build/lint/typecheck/test/deploy independently with zero references to the other by path
(only by published package version); a deliberate breaking change to `packages/contracts` proves the
version-bump workflow catches it in CI on the *other* repo, not silently at runtime; local combined
dev (`make up && make migrate && make web-dev` or equivalent) still works per whatever 4.8.4 decided.

**Open decisions needing your input before executing this phase:** registry choice (4.8.1), the two
new repo names (4.8.2/4.8.3), and the origin monorepo's fate (4.8.4). Nothing here executes without
those answers — this phase is fully specced but blocked on them, same as any other "needs your
input" item in this plan.

---

## Phase 5 — Optimization & proof

- **Embedder bake-off** on the (now real) gold set: OpenAI-3072 incumbent vs Voyage-3.x vs Qwen3-8B
  vs bge-m3 (multi-provider code already exists in `embeddings_client.py`). Commit one; re-embed via
  the version-stamp gate (`versioning.py`). Consider Matryoshka / dim reduction + chunk-level rerank.
- **Caching:** exact-match (Redis) + semantic cache keyed per `source_id`/scope + TTL; keep prompt
  caching. **Redis only if the proportionality gate is met** (confirmed cache/queue/lock need).
- **Adaptive router (last):** classify query difficulty → simple vs decompose; optional HyDE /
  multi-query (RAG-fusion) for hard queries only.
- **Proof:** config sweeps; **prompt-injection + permission/isolation red-team ✅ done (5.3,
  2026-08-10)** — deterministic architecture-level tests (6 new, `test_answer_service.py` +
  `test_chat_endpoint.py` + `test_pii.py`), found and fixed a real numeric-`principal` space-trust
  bypass; a live-LLM adversarial matrix (retrieved-content injection, system-prompt exfiltration,
  multi-turn injection, reranker relevance-poisoning) is deferred to 5.4, see the ledger's §0 5.3
  entry. Measured latency (TTFT p50 < 1.5s / p95 < 2.5s, e2e p95 < 10s) + cost is also 5.4 (an
  unwired `latency_metrics.py` scaffold with these exact targets already exists from the initial
  baseline commit). Deploy/rollback runbooks in `docs/runbooks/`.
  Optional: fine-tune the embedder on real ticket pairs. **Graph RAG stays off.**
- **`CHAT_API_KEY` rotation ✅ done (5.1, 2026-08-10).** Built exactly the shape raised here: a
  bounded overlap window (`CHAT_API_KEY` + `CHAT_API_KEY_PREVIOUS`, both checked in
  `_verify_api_key`, `router.py`), `scripts/rotate_chat_api_key.py` to run it, and
  `docs/runbooks/chat-api-key-rotation.md` documenting the swap procedure. Cadence recommendation
  unchanged: monthly-or-quarterly, not weekly — this is a private, never-logged,
  never-browser-exposed, server-to-server secret, so the threat model that justifies weekly
  rotation for a client-exposed or third-party-shared key doesn't apply here. The user raised
  weekly/biweekly/daily as an option (2026-08-10); the mechanism supports any cadence the operator
  picks — it's the overlap window that matters, not the interval — so this is a runtime choice,
  not a rebuild. No scheduled/cron automation yet (see 5.1's "not done" note — no live deploy
  target to run it against).

---

## Phase 6 — Supabase vector store migration & deploy  *(prod target; its own phase)*

**Goal.** Move the corpus + retrieval from local Docker pgvector to **Supabase** (managed Postgres +
pgvector) as the production vector store, preserving the ADR-0004 source-isolation model. Dev stays on
local pgvector until this phase. This is deploy/infra work, deliberately separated from the Phase 5
accuracy/optimization work so neither blocks the other.

**Why not sooner (revisited 2026-08-10 at the user's request).** Moving *dev* onto Supabase before
Phase 4/5 land would trade a working, hermetic, zero-network test DB (`omniboost_rag_test`, spun up by
`make up`) for a networked dependency in every dev/test loop, and risks the exact pgvector-version trap
3.5.1 was built to avoid (Supabase may pin `< 0.8`, breaking `hnsw.iterative_scan`) — with no concrete
deploy date forcing the move. Root `CLAUDE.md`'s proportionality gate says add infra when a concrete
requirement exists, not ahead of one. **Recommendation: keep Phase 6 deploy-only, as already decided.**
Also worth noting: the app talks to Postgres directly via `psycopg`, not Supabase's REST/JS SDK, so a
Supabase project's `ANON_KEY`/`SERVICE_ROLE_KEY` are never needed here — only the Postgres connection
string. If there's now a concrete ship date, say so and the Phase 6 blockers (connection string,
pgvector≥0.8 confirmation, role mapping) can be pulled forward — that's information-gathering, not a
dev-infra switch.

**Blocked on the user (ask at phase start — never invent a DSN or key):**

- **Connection string** → `DATABASE_URL` (writer) and `DATABASE_READER_URL` (reader). Use the
  **session pooler or direct** connection (port 5432), **not** the `:6543` transaction pooler, so
  Alembic migrations + prepared statements work. Keep the `postgresql+psycopg://` prefix.
- **pgvector ≥ 0.8 confirmation.** Needed for `hnsw.iterative_scan` (the RLS-scope recall safety valve,
  3.5.1). Supabase may pin an older pgvector — if `< 0.8`, decide a mitigation before shipping RLS.
- **Role / RLS mapping.** Supabase manages roles differently (`authenticated` / `service_role` /
  `anon`, JWT-claim RLS, no plain superuser). Decide how `rag_reader` maps — since the app talks to
  Postgres directly (not PostgREST/JWT), a dedicated low-privilege Postgres role is the likely fit;
  the writer must retain a `BYPASSRLS`-equivalent path.

**Tasks.**

1. Enable pgvector on Supabase (`create extension if not exists vector;`); confirm version ≥ 0.8.
2. Repoint `DATABASE_URL` + `DATABASE_READER_URL` at Supabase; run `alembic upgrade head` there
   (0001 → 0003), confirming the halfvec/HNSW index and `query_trace` build.
3. Recreate roles + RLS on Supabase — the docker init SQL won't run there, so apply
   `schema.ensure_reader_role` + `schema.apply_chunk_rls` via a one-off script or a Supabase migration.
4. Load the corpus (re-embed via the version-stamp gate, or migrate rows).
5. Re-run the isolation tests + `make eval` against Supabase to confirm parity — RLS default-deny,
   rerank lift, and one `query_trace` row per retrieval all still hold.
6. Runbook in `docs/runbooks/`: pooler caveats, backup/restore, rollback, secret handling.

**Acceptance.** Isolation + eval pass against Supabase; `hnsw.iterative_scan` confirmed available (or a
documented mitigation); connection uses the psycopg driver; no secret in logs. `make check` still green
locally (dev unchanged).

### Future direction (not yet a phase) — AWS Bedrock

Noted per the user (2026-08-10): eventual integration with AWS Bedrock-hosted models (Claude via Bedrock
instead of/alongside the direct Anthropic API; possibly Bedrock's Titan embeddings or its hosted Cohere
Rerank) is a real future direction, **not built now** — no concrete AWS deployment decision exists yet,
and building a second inference path today (IAM auth, region/model-ID config, a `FakeBedrock*` test
double) for zero present benefit fails the same proportionality gate as an early Supabase move.

The existing architecture already de-risks this for later: `embeddings_client.py`'s `EmbeddingProvider`
Protocol and `reranker_client.py`'s `Reranker` Protocol + `build_reranker` factory are exactly the seam a
`BedrockReranker` / Bedrock embedding provider would implement — adding one later is a contained,
low-blast-radius change, not a rewrite. Supabase (where vectors live) and Bedrock (where inference runs)
are orthogonal — either can pair with either. **When there's a concrete AWS deployment decision, this
becomes its own ADR-gated phase** (mirroring how Supabase got Phase 6), not something folded into
4.2/5/6 ad hoc.

---

## 5. Cross-cutting rules (apply in every phase)

- **Feature boundaries:** when other code needs a new symbol, export it from the feature/capability
  root (`__init__.py`) — never deep-import. `platform/**` and `shared/**` import no features. Run
  `make boundaries` before every commit.
- **No-regression on lint/type:** ruff/pyright held at the ADR-0003 D1 baseline (2/25 ruff, 31/1
  pyright). Bring files you touch clean; do not reformat files you didn't otherwise touch; do not let
  whole-repo counts rise.
- **Gate unchanged:** from `apps/automation`, `make check` (boundaries + `pytest -q`) stays green.
- **Migrations are reversible** and ordered from `0001_core_schema`.

---

## 6. Critical files

| File | Change | Phase |
|---|---|---|
| `docs/rag/DESIGN.md`, `docs/adr/0004*`, `docs/adr/0005*` | new design doc + ADRs | 0 |
| `infra/foundation/docker-compose.yml` | pin pgvector 0.8; add `rag_writer`/`rag_reader` init SQL | 3.5.1 / 3.5.3 |
| `app/platform/clients/reranker_client.py` (new) + `clients/__init__.py` | `Reranker`, `Cohere`/`Fake`, factory, exports | 3.5.2 |
| `app/features/retrieval/infrastructure/search_repo.py` | `fetch_rerank_texts`, source WHERE, HNSW GUCs | 3.5.1-3 |
| `app/features/retrieval/application/retriever.py` | `set_config` scoping, reader engine, rerank insertion | 3.5.2-3 |
| `app/platform/db/models.py` | `source_type`/`source_id`/`tags` on `page_source`+`chunk`; `ix_chunk_active_source`; `QueryTrace` | 3.5.3-4 |
| `apps/automation/alembic/versions/` (new) | cols + backfill + RLS DDL + `query_trace`; `down_revision="0001_core_schema"` | 3.5.3-4 |
| `app/platform/db/engine.py` | reader engine/sessionmaker (role split) | 3.5.3 |
| `app/platform/config/settings.py` | `database_reader_url`, rerank/rewrite/refusal knobs; fixture forces `reranker_provider=fake` | 3.5 |
| `confluence_sync/tests/conftest.py` + `test_retrieval_eval.py` | reader role + isolation tests | 3.5.3 |
| `features/evaluation/run_baseline.py` / `runner.py` | rerank-lift reporting | 3.5.5 |
| `app/features/rag_agent/` (new), `app/main.py` | answer workflow, `POST /chat`, `PATCH /chat/{id}/feedback` | 4 |
| `apps/web/src/features/chat/*`, `app/api/chat/route.ts`, `packages/contracts` | chat UI + SSE proxy + contract | 4 |
| `docs/rag/fixes/*`, `app/features/{confluence_sync,retrieval,rag_agent}/**`, `shared/rate_limiter.py`, `platform/clients/confluence_client.py`, `platform/db/models.py` | 16-item remediation (ACL bypass, cache leak, rate-limiter bypass, rollback gap, schema dup, doc drift) | 4.6 |
| `docs/adr/0006-Defer-Multi-Product-Extraction.md` (superseded), `docs/adr/0007-Frontend-Backend-Repository-Separation.md`, `docs/future-ideas/IDEAS.md` | deferred-then-superseded multi-deployment/repo-split decisions + corrected corpus-segmentation idea | 4.7 / 4.8 |
| `packages/design-tokens/src/tokens.ts`, `apps/web/src/features/chat/ui/*` (new), `apps/web/src/app/layout.tsx` | brand-token adoption + Obi widget component rebuild | 4.7 |
| `packages/contracts/package.json`, `packages/design-tokens/package.json`, new standalone repos | published versioned packages; frontend/backend repo extraction | 4.8 |

---

## 7. Verification (per gate)

- **Gate:** `make check` green; `make boundaries` exit 0.
- **Isolation:** scoped query returns rows; wrong `source_id` → zero (RLS default-deny); reader can't
  see unscoped rows.
- **Reranker:** `make eval` reports Precision@5 / NDCG@10 lift vs no-rerank; deterministic with
  `FakeReranker`.
- **pgvector:** `SELECT extversion FROM pg_extension WHERE extname='vector'` ≥ 0.8; iterative scan
  returns full `LIMIT` under a narrow scope.
- **Tracing:** each retrieval writes a `query_trace` row with `retrieved_page_ids` + `allowed_sources`
  + models + latency (3.5.4). `rerank_scores` + `retrieved_chunk_ids` are populated in Phase 4.2 (the
  retriever-return refactor), not 3.5.4.
- **Phase 4 e2e:** web UI → streamed, grounded, cited, scoped answer; refusal below threshold;
  feedback updates the trace.
- **No-regression:** ruff/pyright at baseline; OpenAPI/collect deltas only where intended.

---

## 8. Risk register (from design validation)

1. **pgvector not pinned to 0.8** → iterative scan missing → RLS silently over-filters (reads like a
   reranker regression). **Pin first (3.5.1).**
2. **RLS as the sole recall path** → pair it with the explicit `WHERE source_id = ANY(:sources)` +
   iterative scan.
3. **`SET LOCAL` can't bind params** → use `set_config(..., true)`; the wrong choice is an injection
   vector or a silent default-deny.
4. **Eval harness runs as writer** → RLS untested or broken → bundle the harness + roles into the
   RLS PR (3.5.3), never split.
5. **Reranker needs text the retriever doesn't have** → the `fetch_rerank_texts` refactor precedes
   wiring (3.5.2).
6. **`.env` live Cohere key in `env=local`** → force `fake` reranker in tests for determinism.
7. **Owner bypasses RLS** → reads MUST run as the non-owner `rag_reader`; the writer is `BYPASSRLS`.
