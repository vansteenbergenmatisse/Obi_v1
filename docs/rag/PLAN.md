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

**Phase 4.7 (Obi widget) status, summarized here — full as-built detail in its own section below.**
Built across several sessions (2026-08-10/11), independent of Phase 4.6/5, never blocking either.
Currently **done in code, uncommitted, with a disclosed test gap** — see Phase 4.7's own "Known
gaps / debt" for exactly what that gap is (a deleted test file's coverage not replaced, three other
test files that now fail to compile). Do not treat it as closed until that's cleared; the ledger
row in the phase table below carries the same caveat. **Resume Phase 4.6 at 4.6.13 next** — that
deferral (4.7 before 4.6.13) was the user's explicit request and is now resolved; it doesn't reopen
4.6's gate on Phase 5.4, only the order changed.

*(The detailed sub-step-by-sub-step history that used to live here — every deviation, live-browser
bug caught, and copy decision across roughly ten sessions — was consolidated into Phase 4.7's own
section on 2026-08-11 at the user's request, once the widget itself was far enough along that the
history was no longer useful as a day-to-day reference. It's still in git history for anyone who
needs it.)

**New this session (2026-08-11): 4.7.8 built, Phase 7 scoped.** The user asked for
click-to-zoom-preview on attached/screenshotted images, plus vision analysis of every such image.
Checked the code first rather than trusting the description — neither existed. Per the user's own
split (frontend-only → build now; touches backend/contracts/security → new phase): built **4.7.8**
(`image-lightbox.tsx` + `attachment-strip.tsx` wiring, +2 tests, all passing, `tsc` clean, zero new
regressions — verified by diffing against the pre-session `aae90e5` baseline) and added **Phase 7**
(vision-grounded image analysis, superseding `docs/future-ideas/IDEAS.md` #3) as a scoped-not-
designed requirement. Phase 7 is not started — no contract change, no backend call, no design pass
or ADR yet. This does not change the existing plan: still resume Phase 4.6 at 4.6.13 next; Phase
4.7's disclosed test gap (above) is still open and unrelated to this addition.

#### 4.6 progress snapshot (2026-08-11 session) — read this before doing anything else

**Done, verified, committed — 4.6.1 through 4.6.11 (11 of 16 sub-steps).** Test count climbed
219 → 272 across these, boundaries clean throughout, ruff/pyright never regressed (pyright's true
baseline was reconciled 31→34 at 4.6.9, see ADR-0003 D1). Commit refs, one per sub-step:

| Sub-step | What | Commit |
|---|---|---|
| 4.6.1 | Confluence group-restriction fail-closed (CRITICAL) | `4d0ba70` |
| 4.6.2 | Confluence group-membership expansion (CRITICAL) | `21dffd5` |
| 4.6.3 | Idempotency cache cross-principal leak (HIGH) | `7e841bf` |
| 4.6.4 | Rate-limiter/idempotency hardening batch | `ee9f817` |
| 4.6.5 | `rollback_to` restores `PageSource` cached hashes | `144cd79` |
| 4.6.6 | `permission.py` overloaded `scope` string removed | `309f4e8` |
| 4.6.7 | Confluence client breaker + 5xx retry + audit logs | `93cad11` |
| 4.6.8 | Dedupe `source_type`/`root_type` CHECK constraints (+ migration `0006`) | `be4c8f8` |
| 4.6.9 | Pyright baseline reconciled 31→34 (ADR-0003 D1 amendment, doc-only) | `b6974ef` |
| 4.6.10 | RLS reader-role fails closed outside offline envs | `d897a40` |
| 4.6.11 | Event dedup: `delivery_id` collision no longer a 500 | `0a61fb4` |
| 4.6.12 | `refusal_reason` on the `chat_request` log line (+ a real `chat_router.log` monkeypatch bug found via `pyright` and fixed before any test ran) | `9d7c0bf` |

Full narrative for each — root cause, design decisions, exact diff, verification commands and
output — is in that sub-step's own `### 4.6.x` section further down this file. Read those, not
just this table, before touching any of that code again.

**4.6.12 — done, verified, and committed this session (2026-08-11, `9d7c0bf`).** Docker Desktop's backend
was genuinely hung (not just the container: a socket ping to `~/.docker/run/docker.sock` timed out
rather than erroring) — fixed by force-killing the stuck `com.docker.backend`/`docker-agent`
processes and relaunching clean; `omniboost_rag_pg` came up healthy on :5434 afterward, `alembic
current` → `0006_dedupe_source_type_check (head)`, no pending migration.

While the DB was still down, ran the full non-DB gate (`make boundaries`, `ruff check`, `ruff
format --check`, `pyright`) on the uncommitted diff as a substitute sanity pass and found a real
bug via `pyright` (36 errors, not the 34 baseline): the tests monkeypatched `chat_router.log` where
`chat_router` was `rag_agent`'s exported **`APIRouter` instance**, not the **module** whose
module-global `log.info(...)` calls `router.py`'s code actually makes — patching the instance would
have silently no-op'd, both tests logging zero entries and failing on first real run. Fixed by
adding a `chat_router_module` export (`sys.modules[...]` lookup — immune to the instance-shadowing
footgun and to isort reordering, see `### 4.6.12` below for the full mechanics) and repointing the
tests at it. Confirmed via `pyright` (back to 34) and an empirical `python -c` check before Postgres
came back, then confirmed for real once it did: both new tests pass, `make check` → **274 passed**
(was 272), boundaries clean, ruff/pyright unchanged at the 2/15/34 baseline. Full narrative in
`### 4.6.12` below.

**Local dev environment brought up + one unplanned web fix — 2026-08-11, after 4.6.12.** Not part
of the numbered plan; recorded here because it changed running state and one file. At the user's
request, checked and started the full local stack:
- `omniboost_rag_pg` (Postgres, :5434) — already healthy from the 4.6.12 verification above.
- Backend (`uv run uvicorn app.main:app --port 8000`, from `apps/automation`) — was **not**
  running (no listener on :8000); started it. `/docs` → 200. `/` → 404 is expected (no root route
  is defined; `/docs` is the real liveness check).
- Web (`pnpm --filter web dev`, :3000) — was already running from an earlier session. `/chat` → 200.

**Unplanned fix, uncommitted — `apps/web/src/app/layout.tsx`.** User reported a React hydration
error in the browser: the server-rendered `<html>` didn't match the client tree, diffing in a
`data-scribe-recorder-ready="true"` attribute. That attribute does not exist anywhere in this
codebase — it's a browser extension (a screen-recording/dictation tool, "Scribe") injecting an
attribute onto `<html>` before React hydrates, exactly the "browser extension messes with the HTML
before React loaded" case the Next.js hydration-mismatch docs call out by name. Fixed with the
standard, documented workaround: added `suppressHydrationWarning` to the `<html>` tag in
`RootLayout`. Verified live, in the user's actual Chrome (real extensions active, not a clean
headless profile): reloaded `/chat` via `claude-in-chrome`, read the console with
`onlyErrors: true` and a broad pattern — no hydration warning, no errors. **Not committed** —
one-line, outside any phase's scope; ask before committing if you want it bundled separately from
4.6.13+.

**What's left: 4.6.13, 4.6.14, 4.6.15, 4.6.16 (the exit gate) — all still ⬜ todo, full scope
already specified in their own sections below, unchanged from the original plan text.** Only once
4.6.16 is green does Phase 5.4 / the embedder bake-off / adaptive routing resume.

**4.6.2 caveat, still open:** implemented against the fixture gateway per the user's explicit
"implement now, verify later" choice — **live Confluence verification of the group-membership
endpoint is still outstanding** (Confluence token still dead, blocker #3) and must happen before
trusting 4.6.2's live behavior. Not gating 4.6.13+.

**Two "needs your input" flags raised so far, not blocking (defaults were taken, see each
section for the reasoning), open for your override at any time:**
- 4.6.5: `PageSource` fields with no `DocumentVersion` counterpart are left at their pre-rollback
  values on `rollback_to` (self-heal on next reconciliation sweep) rather than forced to re-fetch.
- 4.6.9: pyright baseline formally amended to 34 (not fixed back to 31) — the 3 "new" errors are a
  4th occurrence of an already-accepted `RunResult.outcome: object | None` typing pattern, not a
  new bug class.
- 4.6.10: `get_reader_engine()` fails closed (raises `ReaderRoleMisconfiguredError`), not warn-only,
  outside an offline env when `DATABASE_READER_URL` is unset.

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

**Phase 4.7 is now ✅ done (2026-08-11)** — see its own section for the full narrative. What's left,
independent of Phase 5: **Phase 4.8** (frontend/backend repository separation — split `apps/web` and
`apps/automation` into independent repos, `packages/contracts`/`design-tokens` become published
versioned packages). **4.8 supersedes ADR-0006's deferral** — see
`docs/adr/0007-Frontend-Backend-Repository-Separation.md` for the actual decision and why ADR-0006 no
longer holds for the repo-split question. 4.7 finishing first (settling the widget's file layout
before moving it to a new repo) was the whole point of that ordering — 4.8 may now proceed whenever
its own blockers clear. 4.8 doesn't gate backend Phase 5; it's frontend/repo-topology work, disjoint
from Phase 4.6's backend files.

**No phase auto-starts.** Per the project's standing local working rule, a fresh session must stop
and get an explicit go-ahead from the user before starting *any* phase/sub-step. On resume: read
this ledger, state what's ready (4.6.13 next, per the deferral note above; 4.8 also available but
blocked on its own "needs your input" decisions below), and ask which to start rather than beginning
any automatically. Phase 4.8 has three unanswered "needs your input" decisions (registry choice, new
repo names, origin-monorepo fate) that block it regardless of ordering.

Fresh context: read this ledger + `docs/rag/DESIGN.md` (§2 target pipeline, §5 accuracy stack) +
`docs/adr/0005*` + `docs/adr/0007*`, then ask before starting Phase 4.6.13 or Phase 4.8. The chat
feature (backend + web UI) is functionally done; the floating widget is now the **only** chat
surface (the old `/chat` route was removed — see Phase 4.7's own section) — both dev servers run
together (`uvicorn app.main:app` on :8000, `pnpm --filter web dev` on :3000, widget on every page).
Phase 4.7's own section has the current, disclosed test/commit gap; don't treat it as fully closed
until that's cleared.

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
existing message-bubble precedent); refusal badge visually identical to decorative chips (claimed fixed here, but **this claim was
false** — see the Phase 4.7 re-verification note at the top of this ledger (§0): the badge was
still plain-neutral through 4.5, 4.6, and all of 4.7 until caught and actually fixed during that
re-verification pass); missing
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
| **4.6** — fixes-backlog remediation (16 sub-steps + exit gate) | 🔶 in progress (4.6.1+4.6.2/16 done) | — | independent same-day audit (`docs/rag/fixes/`) found a CRITICAL ACL bypass + a HIGH cross-principal leak + 12 more findings in already-"done" phases 0-4; **gates 5.4/bake-off/adaptive-routing** until the 4.6.16 exit gate is green; 4.6.2 live-verification still outstanding (Confluence token dead) |
| **5** (remaining) — 5.4 live-LLM red-team + latency/cost proof, embedder bake-off, adaptive routing | ⬜ todo (blocked on 4.6) | — | 5.4 needs real API calls/spend; bake-off blocked on Confluence token + `VOYAGE_API_KEY` |
| **6** — Supabase vector store migration & deploy | ⬜ todo (deferred) | — | prod target; needs connection string + pgvector ≥ 0.8 + role/RLS mapping |
| **4.7** — Obi widget: chat UI rebuild, brand tokens, screenshot capture, real i18n, `/chat` route removed, image lightbox (4.7.8) | ✅ done, **uncommitted** | `206baab` (first sub-step only); everything since, including the `/chat` removal, the layout bug fix, and 4.7.8, is uncommitted | frontend-only, `apps/web`; does not gate Phase 5; source of truth `docs/rag/reference/obi-mockup/` + `docs/rag/OBI-WIDGET-DESIGN.md`; test suite not re-run since the last two rounds of changes — see Phase 4.7's own "Known gaps / debt" |
| **4.8** — Frontend/backend repository separation (4.8.1 → 4.8.7) | ⬜ todo (blocked on registry/repo-name/monorepo-fate decisions) | — | supersedes ADR-0006's deferral; see `docs/adr/0007-Frontend-Backend-Repository-Separation.md`; do after 4.7 |
| **7** — Vision-grounded image analysis (attachments + screenshot capture) | ⬜ todo (just scoped, 2026-08-11) | — | supersedes `docs/future-ideas/IDEAS.md` #3; every image added via attachment or the screenshot button gets analyzed by a vision-capable model call, folded into the answer; touches contracts + `apps/automation` + security review — not frontend-only, see Phase 7's own section |

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
5. **Docker Desktop down (2026-08-11 session, ACTIVE).** Mid-4.6.12, the local Docker daemon
   stopped responding (`docker info` timed out; `docker compose ps` couldn't reach the socket).
   `open -a Docker` was tried and the Docker Desktop process tree did relaunch (confirmed via `ps
   aux`), but the daemon still wasn't answering `docker info` after ~7 minutes of waiting — looked
   stuck mid-startup, not just slow. **User will restart Docker manually.** Once
   `docker compose -f infra/foundation/docker-compose.yml ps` shows `omniboost_rag_pg` as
   `healthy` again, 4.6.12's two new tests can run and everything from 4.6.12 onward can resume —
   see the "4.6 progress snapshot" section above for the exact next steps.

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

### 4.6.2 — Confluence group-membership expansion (CRITICAL) ✅ done (2026-08-10, `21dffd5`)

**Status: implemented, tested (8 new tests + 2 existing `test_worker_sync.py` assertions
updated), boundaries clean, no ruff/pyright regression → 237 tests total (was 229). No live
Confluence verification** — the user chose "implement now, verify later" given the token is
still dead (blocker #3): the group-membership endpoint has only ever been exercised against a
mocked transport, never a real Confluence instance.

**Design.** `_resolve_read_restriction` (`confluence_client.py`) gains an optional
`resolve_group: Callable[[GroupRecord], list[str]] | None` parameter. Each group on a
restriction record is passed to it; returned account ids are unioned into the principal list
(de-duplicated, order-preserving). Fail-closed is preserved, not weakened: no resolver (the old
default), or a resolver that finds zero members for every group on the record, still returns
`GROUP_RESTRICTED_SENTINEL` when no user principal is present either — a failed/empty lookup can
never silently open access.

- **`HttpConfluenceClient`** gets a per-instance `_group_members_cache: dict[str, list[str]]`
  (the client is already documented "instantiate once and reuse" across a sync run, so this
  cache lives exactly as long as it needs to) and `_fetch_group_members`, which calls Confluence's
  v1 REST group-membership endpoint (`GET {base}/rest/api/group/by-id/{groupId}/member`, falling
  back to the deprecated name-based path when a restriction record has no `id`) — REST **v2** has
  no group-membership endpoint yet. **Flagged, not silently assumed:** this exact path/response
  shape is unverified against a live Confluence instance; the docstring on
  `_fetch_group_members` says so explicitly and points back at this ledger's blocker #3. A wrong
  path/shape fails the request (4xx/5xx), which the cache stores as `[]` and which
  `_resolve_read_restriction` turns into the same fail-closed sentinel 4.6.1 already proved
  correct — a config/API mistake degrades to "inaccessible," never "world-readable."
- **`FixtureConfluenceGateway`** gets a parallel fixture-backed resolver
  (`_group_members_for`) reading a new `tests/fixtures/confluence/group_members.json`
  (`grp-hr` → `acct-dave`, `grp-finance` → `acct-erin`), plus a `set_group_members` test mutator
  matching the existing `set_restrictions` pattern for scenarios the static fixture can't express.
- **`test_worker_sync.py::test_first_index_persists_restrictions`** (and
  `test_permission_change_is_metadata_only`'s initial assertion) updated: fixture page 2002's
  persisted principal set is now `{"acct-carol", "acct-dave", "acct-erin"}` (the user plus both
  groups' expanded members), not just `{"acct-carol"}` — the group-membership expansion this
  sub-step ships, landing through 4.3's existing, unmodified `page_restriction` write path.

**Not done (explicit, tracked, not silent):** confirming the real endpoint path/shape and running
a live group-member sync once the Confluence token works — re-verify before trusting this
sub-step's live behavior, per `CLAUDE.local.md` §2. A consecutive-failure circuit breaker for
Confluence calls (including this new endpoint) is 4.6.7's job, not duplicated here.

**Shipped (tests, by file):** `app/platform/clients/tests/test_confluence_client.py` (+8): pure
resolver expands via a fake `resolve_group` and unions across groups without duplicates; a
resolver that finds nobody still fails closed; `HttpConfluenceClient` expands a real group-only
restriction via a mocked v1 member endpoint; two pages sharing one group hit the member endpoint
exactly once (cache proof); a 403 from the member endpoint stays fail-closed, not open;
`FixtureConfluenceGateway` expands via the new `group_members.json` fixture and via the
`set_group_members` override.

### 4.6.3 — Idempotency cache cross-principal leak (HIGH) ✅ done (2026-08-10, `7e841bf`)

**Status: implemented, tested (2 new tests), boundaries clean, no ruff/pyright regression → 239
tests total (was 237). Pure code fix, no migration, exactly as scoped.**

**Fix.** New `_idempotency_cache_key(idempotency_key, principal, history)`
(`app/features/rag_agent/server/router.py`) hashes `sha256(idempotency_key + "|" +
json(turns) + "|" + (principal or ""))` — mirroring `answer_cache._cache_key`'s already-correct
binding. `_stream_answer` now computes this composite key once (`cache_key`) and uses it for both
`cache.get`/`cache.set` instead of the raw `Idempotency-Key` header string, so a replay of the same
header with a different `principal` or `history` is treated as a fresh request (a new trace id),
never a hit on another caller's cached `Answer`. The `chat_request_replayed` log line still logs
the raw header value (for operator correlation), not the hash.

**Tests (`confluence_sync/tests/test_chat_endpoint.py`, +2):**
`test_idempotency_key_replay_with_different_principal_is_not_the_first_callers_answer` (same
`idempotency-key` header, `principal` "acct-alice" vs "acct-bob" → different trace ids) and
`test_idempotency_key_replay_with_different_history_is_not_the_first_callers_answer` (same header,
different final-turn content → different trace ids). The existing
`test_idempotency_key_replays_cached_answer_without_rerunning` (same key + same body → same trace
id) stays green, unchanged.

**Verification:** `make check` (from repo root) → **239 passed** (was 237), boundaries clean;
`ruff check`/`ruff format --check` unchanged (2 errors / 17 unformatted, same baseline); `pyright`
unchanged (34 errors, identical file list — none touch `router.py` or
`test_chat_endpoint.py`, confirmed by listing error-file paths directly); `alembic current` →
`0005_page_restriction (head)`, no migration (pure code fix, no schema change).

### 4.6.4 — Rate-limiter/idempotency hardening batch (MEDIUM-HIGH + MEDIUM, batched) ✅ done (2026-08-10)

**Status: implemented, tested (7 new `SlidingWindowRateLimiter` unit tests + 2 new
`test_chat_endpoint.py` HTTP-level tests), boundaries clean, no ruff/pyright regression → 248 tests
total (was 239). Pure code fix, no migration, exactly as scoped.**

**Fix 1 — `_rate_limit_key` dropped `principal` entirely, IP only.** The old key preferred
`principal:{principal}` when supplied, else `ip:{client_ip}` — since `principal` is untrusted
caller-self-reported free text (same trust class the 5.3 red-team finding already flagged), any
caller could defeat `chat_rate_limit_per_minute` outright by sending a different `principal` on
every request. `_rate_limit_key(request)` (`rag_agent/server/router.py`) now always returns
`ip:{client_ip}` — the one dimension a caller cannot freely rotate. Both call sites (`POST /chat`,
`PATCH /chat/{trace_id}/feedback`) updated; the `security_baseline` docstring and
`FEATURES.md`'s YAML mirror both corrected (they previously documented the bypassable behavior as
the intended design).

**Fix 2 — `SlidingWindowRateLimiter` bounded memory (`app/shared/rate_limiter.py`).** Two
complementary mechanisms, since either alone misses a case the other catches: a key whose bucket
empties out (every hit aged past the window) is now dropped from the dict opportunistically the
next time that same key is looked up — but a key that is looked up exactly once and never again
(many distinct one-shot IPs) would never trigger that prune, so a new optional
`max_tracked_keys` constructor param evicts the oldest-inserted key outright once the dict exceeds
it, mirroring `TTLCache.max_entries`'s same oldest-first bound and rationale. New
`chat_rate_limiter_max_tracked_keys` setting (default 1000) wires it for the chat limiter;
`webhook.py`'s limiter is untouched (unbounded, `max_tracked_keys=None` default) — its key is
already IP-only, and this fix's scope is the file cluster the finding named, not every consumer of
the shared primitive. Added `__len__` for testability.

**Fix 3 — idempotency `TTLCache` gained a `max_entries` bound.** New
`chat_idempotency_cache_max_entries` setting (default 500, matching
`chat_answer_cache_max_entries`'s existing precedent exactly); `_idempotency_cache` now passes it
through. `TTLCache` itself already supported `max_entries` (built for the Phase-5 answer cache) —
this was a wiring gap at one of its two call sites, not a missing capability.

**Shipped (tests, by file):**
- `app/shared/tests/test_rate_limiter.py` (new, 7 tests): window enforcement (allow-until-max,
  re-allow after the window elapses, independent distinct keys); the two PLAN 4.6.4 fixes directly
  — an expired bucket is pruned from the dict on next access, bucket count stays bounded across 50
  distinct one-shot keys with `max_tracked_keys=10`, oldest-key-evicted-first, and unbounded
  behavior is preserved when `max_tracked_keys` is `None` (the pre-existing webhook.py call site's
  shape).
- `confluence_sync/tests/test_chat_endpoint.py` (+2):
  `test_rate_limit_is_keyed_by_ip_not_by_rotating_principal` (same IP, `principal` "acct-alice"
  then "acct-bob" within a `chat_rate_limit_per_minute=1` window → the second request is 429, which
  would have passed under the pre-fix principal-first key);
  `test_idempotency_cache_evicts_the_oldest_key_once_max_entries_exceeded`
  (`chat_idempotency_cache_max_entries=2`, three distinct `Idempotency-Key` headers, then replaying
  the first (now-evicted) key returns a fresh trace id, not the original cached `Answer`).

**Verification:** `make check` (from repo root) → **248 passed** (was 239), boundaries clean;
`ruff check` unchanged (2 errors, both pre-existing in `alembic/env.py`/`0001_core_schema.py`);
`ruff format --check` unchanged (17 unformatted — the new `test_rate_limiter.py` and the edited
`test_chat_endpoint.py` were both formatted before this check, so the count didn't regress);
`pyright` unchanged (34 errors, identical file list — none touch `router.py`, `settings.py`,
`rate_limiter.py`, or either touched/new test file, confirmed by listing error-file paths
directly); `alembic current` → `0005_page_restriction (head)`, no migration (pure code fix, no
schema change).

### 4.6.5 — `rollback_to` doesn't restore `PageSource`'s cached hashes (MEDIUM-HIGH) ✅ done (2026-08-10)

**Status: implemented, tested (3 new tests), boundaries clean, no ruff/pyright regression → 251
tests total (was 248). Pure code fix, no migration, exactly as scoped.**

**Location correction (not a scope change):** the plan text named
`confluence_sync/application/versioning.py`; the real file is
`apps/automation/app/features/ingestion/application/versioning.py::rollback_to` — `versioning.py`
is owned by `ingestion`, not `confluence_sync` (confirmed by reading `app/features/ingestion/
__init__.py`'s public root, which already exports `rollback_to`).

**Fix:** `rollback_to` now also copies `content_hash`, `structure_hash`, `parser_version`,
`chunker_version`, `contextualization_version`, `embedding_model`, `embedding_dim`, and
`retrieval_schema_version` from the target `DocumentVersion` onto `PageSource` — the exact set of
fields that exist on both models. `current_cf_version` was already restored correctly pre-fix (not
part of the bug).

**"Needs your input" item — resolved by taking the plan's own recommendation:** `PageSource`
fields with no `DocumentVersion` counterpart (`title`, `labels_hash`, `access_scope_hash`,
`attachment_manifest_hash`, `source_url`, `source_modified_at`, `tags`, `parent_id`, `source_type`,
`source_id`, `space_id`, `page_status`) are left as their pre-rollback values — nothing correct
exists to restore them to, and they self-heal on the next reconciliation sweep (which re-fetches
metadata regardless of any rollback). **Flagging for your explicit confirmation per the plan's own
"confirm before closing this out" — not blocking on it, since it's the plan's own stated default and
is reversible (a later sweep corrects any drift either way).**

**Verification of the fix's real effect (not just "tests pass"):** confirmed by deliberately
reverting the fix locally and re-running the new test file — both
`test_rollback_restores_page_source_hashes_and_pipeline_stamps` and
`test_rollback_then_real_newer_revision_is_detected_not_masked` failed against the pre-fix code
(the latter with `decision.meaningful == False` — the exact silent-masking bug the plan described),
then passed once the fix was restored. `test_rollback_then_unchanged_sync_reports_no_change` is a
sanity check (doesn't discriminate old vs. new behavior on its own, since the version-guard branch
in `classify()` short-circuits before the hash comparison in this particular scenario) but matches
the plan's literal acceptance wording.

**Shipped:**
- `app/features/ingestion/application/versioning.py::rollback_to`: the 8-field restore, with a
  comment explaining which fields are deliberately left alone and why.
- `app/features/confluence_sync/tests/test_versioning_rollback.py` (+3): direct field-level
  assertion that a rollback repoints all 8 fields at the target version; a `classify()`-level
  regression test (mirroring `sync_service.handle_sync_page`'s own call, read-only) proving an
  unchanged re-sync after rollback still reports `no_change`; a `classify()`-level regression test
  proving the source revision that was active *immediately before* the rollback (the scenario that
  actually exposes the bug — re-serving a version whose hash was the one PageSource had cached) is
  still detected as a real change, not masked.

**Verification:** `make check` (from repo root) → **251 passed** (was 248), boundaries clean;
`ruff check` unchanged (2 errors, both pre-existing in `alembic/env.py`/`0001_core_schema.py`);
`ruff format --check` unchanged (17 unformatted, new/edited files excluded from that count);
`pyright` unchanged (34 errors, identical file list — the two errors in the edited test file are
both pre-existing, on the unmodified `test_rollback_restores_prior_version`, confirmed by line
number); `alembic current` → `0005_page_restriction (head)`, no migration (pure code fix, matches
the plan's own "no migration" expectation).

### 4.6.6 — `permission.py`'s overloaded `scope` string (MEDIUM) ✅ done (2026-08-11)

**Status: implemented, tested (2 new tests), boundaries clean, no ruff/pyright regression → 253
tests total (was 251). Pure code fix, no migration, exactly as scoped.**

**Fix.** `PrincipalPermissionPolicy.allowed()` (`retrieval/domain/permission.py`) no longer takes a
raw `scope: str | None` and re-derives trust kind from `.isdigit()` — it now takes explicit
keyword-only `space_id: int | None` and `principal: str | None`. The `.isdigit()` classification
itself moved to a new pure module-level function, `classify_scope(scope) -> tuple[int | None, str |
None]`, called exactly **once** per search — in `HybridRetriever._search`
(`retrieval/application/retriever.py`), which replaces its old `self._policy.space_id(scope)` call
(the `space_id()` method is deleted, not deprecated) and passes the classified pair to both the
existing space-scoped `keyword_search`/`dense_search` calls and the new `allowed(space_id=...,
principal=...)` call. This closes the actual root cause the 5.3 finding only patched at one caller
(`ChatRequestBody.principal`'s HTTP-boundary validator): the domain layer itself can no longer
reinterpret an all-digit *principal* string as space-level trust, because `allowed()` never inspects
string shape at all anymore — that decision is made once, upstream, and handed in pre-classified.

**Scope decision — kept `HybridRetriever`'s `policy` constructor parameter unchanged.** It was
already documented (PLAN 4.3) as unused for the live `allowed()` decision — the request-scoped
`live_policy` built fresh from `page_source`/`page_restriction` per search does the real work — and
`test_permission_enforcement_is_db_backed_not_fixture_fed` specifically exercises passing a bare
`PrincipalPermissionPolicy()` as an acceptance proof that this is true. Removing the parameter would
delete that proof's premise for no benefit 4.6.6's finding actually asked for; the finding is about
`allowed()`'s signature, not about this pre-existing, already-tested dead-parameter status.

**Shipped (tests, by file):**
- `retrieval/tests/test_fusion_and_permission.py`: `test_classify_scope_splits_digit_strings_from_principal_ids`
  (new); `test_space_scope_grants_space_and_blocks_others`/`test_principal_scope_blocks_unauthorized`
  updated to the new keyword-only signature;
  `test_numeric_principal_argument_is_never_reinterpreted_as_space_trust` (new) — the actual
  regression proof: a restricted page's `allowed()` check with `principal="200"` (an all-digit
  string passed directly, bypassing `classify_scope`) is denied, not silently granted as space
  trust.
- `confluence_sync/tests/test_retrieval_eval.py`: `test_permission_no_leak_and_authorized_access`'s
  direct `policy.allowed(...)` assertion updated to classify `case.scope` first via the now-exported
  `classify_scope`.
- `retrieval/__init__.py`: exports `classify_scope` (consumed cross-feature by the
  `confluence_sync` eval test, per the boundary rule — root-only).

**Verification:** `make check` (from repo root) → **253 passed** (was 251), boundaries clean;
`ruff check` unchanged (2 errors, both pre-existing in `alembic/env.py`/`0001_core_schema.py`);
`ruff format` applied to the touched files (`retriever.py`, `test_retrieval_eval.py`) to stay at
the baseline — format-unformatted count actually **dropped** 17→16 (no regression, net
improvement); `pyright` unchanged (34 errors, identical file list — none touch `permission.py`,
`retriever.py`, `__init__.py`, or either touched test file); `alembic current` →
`0005_page_restriction (head)`, no migration (pure code fix, no schema change).

### 4.6.7 — Confluence client hardening batch (MEDIUM + INFO, batched) ✅ done (2026-08-11)

**Status: implemented, tested (5 new tests), boundaries clean, no ruff/pyright regression → 258
tests total (was 253). Pure code fix, no migration, exactly as scoped.**

**Location correction (not a scope change):** the plan text says "New dedicated test file (none
exists today)" — that was true when the finding was written, but 4.6.1/4.6.2 already created
`app/platform/clients/tests/test_confluence_client.py` in the interim. New tests were added to
that existing file instead of creating a duplicate.

**Fix 1 — consecutive-failure circuit breaker,** mirroring `anthropic_client.py`'s persistent
instance-state pattern (chosen over `embeddings_client.py`'s per-call-only counter, since this
client is documented "instantiate once and reuse" across a whole sync run — the same reasoning
that already justified 4.6.2's `_group_members_cache`): `_get` now checks
`self._consecutive_failures >= self._breaker_threshold` before every request, raising the new
`ConfluenceCircuitBreakerOpenError` without attempting the network call; a successful `_get`
resets the counter to 0. New `confluence_breaker_threshold` setting (default 5, matching every
other breaker's default in this codebase).

**Fix 2 — retry predicate now retries 5xx.** `_get` split into an outer `_get` (breaker) and an
inner `_get_with_retry` (the tenacity-decorated method, unchanged retry/backoff shape); `_RETRYABLE`
gained `httpx.HTTPStatusError`. Safe to add unconditionally: inside `_get_with_retry`,
`raise_for_status()` is only ever called for a `>=500` response — a 4xx is returned as a normal
`Response`, never raised — so this closes exactly the "retry on 5xx" gap `how_this_works.md`
already (wrongly) documented as real, without touching 4xx behavior at all.

**Fix 3 — audit log lines.** `_get_with_retry` now logs `confluence_client_5xx`/`confluence_client_4xx`
(url + status) before returning/raising, and a new `_log_before_retry` tenacity `before_sleep` hook
logs `confluence_client_retry` (attempt number + error) between attempts.

**Shipped:**
- `app/platform/clients/confluence_client.py`: `ConfluenceCircuitBreakerOpenError`, `_get`/
  `_get_with_retry` split, `_log_before_retry`, `_RETRYABLE` gains `httpx.HTTPStatusError`.
- `app/platform/config/settings.py` + `.env.example`: `confluence_breaker_threshold` (5).
- `app/platform/clients/tests/test_confluence_client.py` (+5):
  `test_http_client_retries_on_5xx_then_succeeds`, `test_http_client_4xx_is_not_retried`,
  `test_http_client_breaker_trips_after_consecutive_failures`,
  `test_http_client_success_resets_the_breaker` (proves a success clears the counter rather than
  failures accumulating across it), `test_http_client_logs_retry_and_status_lines` (via
  `structlog.testing.capture_logs()` — no prior precedent in this repo for asserting structured-log
  output; used here since asserting only side effects would miss whether the log lines actually
  fire).

**Verification:** `make check` (from repo root) → **258 passed** (was 253), boundaries clean;
`ruff check` unchanged (2 errors, both pre-existing in `alembic/env.py`/`0001_core_schema.py` — two
transient new errors in the test file, both fixed before this check: a >100-char line and a
nested-`with` that ruff's `SIM117` flagged, merged into one `with ... , ...:`); `ruff format` count
unchanged (16 unformatted, none of the touched files among them); `pyright` unchanged (34 errors,
identical file list — the one pre-existing `confluence_client.py` error shifted line number
184→227 from inserted code above it, confirmed by reading it directly, not a new error); no
migration (pure code + settings addition, no schema change).

### 4.6.8 — Duplicate CHECK constraint from a naming-convention bug (MEDIUM) ✅ done (2026-08-11)

**Status: implemented, tested (3 new pure metadata tests), migration applied to the real dev DB
and round-trip verified on both a scratch DB and the dev DB, boundaries clean, no ruff/pyright
regression → 261 tests total (was 258).**

**Confirmed live, not just theoretical — worse than the plan text described.** Directly querying
both databases before touching anything: the `omniboost_rag_test` DB (built via
`schema.create_all()`, never through Alembic) had all **four** explicit `CheckConstraint` names
double-prefixed (`ck_chunk_ck_chunk_source_type`, `ck_page_source_ck_page_source_source_type`,
`ck_source_scope_ck_source_scope_root_type`, `ck_source_scope_ck_source_scope_source_type`) — the
plan only named `ck_chunk_source_type` as an example, but the same bug affects every explicit
`CheckConstraint(name=...)` in `models.py`. Worse: the real **dev** DB (`omniboost_rag`, migrated
through the actual 0001→0005 chain) had a genuine **duplicate** on `chunk` and `page_source` (both
the buggy and the canonical name present simultaneously) — not a divergence risk, an
already-existing defect. Root cause: migration `0001_core_schema.py`'s baseline calls
`schema.create_all()` against the (buggy) ORM metadata, producing the double-prefixed name; then
`0002_provider_tags_and_rls.py` runs `DROP CONSTRAINT IF EXISTS ck_{tbl}_source_type` (the
canonical name) before re-adding it — which matched nothing on a 0001-built DB, so it *added* a
second, correctly-named constraint instead of replacing the first. `source_scope` was unaffected
on the real dev DB only because migration `0004_source_scope.py` created it via raw DDL directly,
never through `create_all()`.

**Fix.** All four `CheckConstraint(..., name="...")` calls in `models.py` now wrap the name in
`sqlalchemy.schema.conv(...)`, which marks it pre-resolved so the naming convention
(`ck_%(table_name)s_%(constraint_name)s`) no longer re-interpolates it. Confirmed directly: a fresh
`schema.create_all()` run now produces the canonical name on every table, matching the hand-written
migration DDL exactly (verified by building the fixed schema against the test DB and reading `\d`
output before reverting).

**Migration `0006_dedupe_source_type_check`:** drops each table's buggy double-prefixed constraint
via `DROP CONSTRAINT IF EXISTS` (idempotent — a no-op on `source_scope`, which never had the real
duplicate, and on any DB built fresh from the now-fixed `models.py`); `downgrade()` re-adds the
exact buggy name alongside the untouched canonical one, restoring the pre-migration shape exactly.
**Round-trip tested twice, per the plan's "scratch DB, not the shared dev DB" instruction:** first
against a disposable `omniboost_rag_scratch_4_6_8` database seeded with the exact real-world
pre-migration constraint shape (upgrade → exactly one canonical constraint per table survives;
downgrade → the buggy duplicate reappears, canonical untouched), then applied for real to the dev
DB (`alembic upgrade head` → duplicate gone; `alembic downgrade -1` → duplicate back, confirmed via
`\d`; `alembic upgrade head` → clean again, dev DB left at head).

**Shipped:**
- `app/platform/db/models.py`: `conv(...)` around all four explicit `CheckConstraint` names;
  `from sqlalchemy.schema import conv`.
- `alembic/versions/0006_dedupe_source_type_check.py` (new): the cleanup migration.
- `app/platform/db/tests/test_models_constraints.py` (new, 3 tests): pure `Base.metadata`
  inspection (no DB) proving each table has exactly one canonically-named CHECK constraint —
  confirmed to fail against the pre-fix code (reverted `models.py` locally, all 3 failed with the
  double-prefixed names, then passed once the fix was restored), per this project's "verify the
  fix's real effect" convention.

**Verification:** `make check` (from repo root) → **261 passed** (was 258), boundaries clean;
`ruff check` unchanged (2 errors, both pre-existing in `alembic/env.py`/`0001_core_schema.py`);
`ruff format` unchanged (16 unformatted, none of the touched/new files among them); `pyright`
unchanged (34 errors, identical file list — the new test file needed one `str(c.name)` cast to
satisfy `Constraint.name`'s `_ConstraintNameArgument` type, added before this count, not counted as
a regression); `alembic current` → `0006_dedupe_source_type_check (head)`.

### 4.6.9 — Pyright baseline reconciliation (MEDIUM, governance) ✅ done (2026-08-11)

**Status: reconciled, no code changes, no test count change (261, unchanged from 4.6.8).**

**Investigation.** Built a disposable git worktree at `e4490aa` (Phase 4.1, the last commit
confirmed at the true 31-error baseline by this ledger's own "Independent re-verification —
2026-08-10" entry), ran `pyright` there, and diffed its 31 errors against head's 34 by
file+rule+message (not line number, which drifts with every inserted line). Every one of the 31
baseline errors is still present (same file, same rule, same message) — nothing was silently
fixed and re-broken. The 3 new errors are **not a new error type**: they're a 4th occurrence of a
pattern already present 3 times in `test_worker_sync.py` before Phase 4.3 —
`reportOptionalMemberAccess`/`reportAttributeAccessIssue` on `worker.RunResult.outcome: object |
None`, which is deliberately typed `object` because `RunResult` is shared across three handlers
(`_handle_sync_page`/`_handle_delete_page`/`_handle_reconcile_space`) with different return
shapes. PLAN 4.3's own ledger section already disclosed this at the time: "my new test in that
file added one more occurrence of the latter by following the file's own existing idiom" — a
self-documented repeat, not a silent regression that slipped through "unchanged" reporting.

**Decision: (b), not (a).** A real fix (a proper `Union`/generic on `RunResult.outcome` so each
handler's test can narrow without Pyright complaining) is a legitimate typing improvement, but it
touches the shared dataclass and all three handler call sites for a purely cosmetic gain — nothing
here is a functional bug, the tests already pass and already exercise real behavior correctly.
Judged not proportional to a governance/baseline-bookkeeping item, per the plan's own "propose (b)
explicitly" escape hatch for low-value fixes. **Flagging for your explicit confirmation — not
blocking, since it only formalizes what "unchanged (34 errors)" already meant in every 4.6.x
verification note above.**

**Shipped:** `docs/adr/0003-Feature-Boundary-Enforcement.md`'s D1 deviation amended in place with
the full bisect finding and rationale — the baseline is now formally 34/1, not silently drifted.
Root `CLAUDE.md`'s stale numbers are deliberately left for 4.6.15 (its own batch already lists that
edit; doing it here would just be overwritten by that pass) — this sub-step's job was settling
*what* the number is, not writing it into every doc that mentions it.

**Verification:** no code touched, so `make check`/boundaries/ruff/pyright are all identical to
4.6.8's readout (261 passed, 2 ruff-check / 16 unformatted, 34 pyright errors — now the *documented*
baseline, not just an observed count); no migration.

### 4.6.10 — RLS reader-role no-op outside offline envs (LOW) ✅ done (2026-08-11)

**Status: implemented, tested (10 new tests), boundaries clean, no ruff/pyright regression → 271
tests total (was 261). Pure code fix, no migration, exactly as scoped.**

**Decision — fail-closed, not warn-only.** The reader role's entire purpose is RLS enforcement
(ADR-0004); silently falling back to the RLS-bypassing writer connection in a real deployment is a
security regression, not a convenience — a warning buried in structured logs is easy to miss on a
production boot, while a raised exception is a loud, immediate startup failure that can't ship
unnoticed. Matches this codebase's existing posture everywhere else a security control's config is
missing (fail-closed sentinels in 4.6.1/4.6.2, the numeric-principal HTTP validator in 5.3, every
circuit breaker). **Flagging for your explicit confirmation — not blocking**, since the plan called
this "a small, cheap question" either way could have answered.

**Fix.** `Settings.is_offline_env()` (`platform/config/settings.py`) replaces the `_OFFLINE_ENVS`
constant duplicated in `embeddings_client.py` and `reranker_client.py` (both now call the shared
method instead). `get_reader_engine()` (`platform/db/engine.py`) now raises a new
`ReaderRoleMisconfiguredError` when `database_reader_url` is unset outside an offline env; inside
one, it falls back to `database_url` exactly as before, silently (no warning — the plan's own test
matrix specified "offline-env + unset (no warning)").

**Shipped:**
- `app/platform/config/settings.py`: `_OFFLINE_ENVS` module constant + `Settings.is_offline_env()`.
- `app/platform/clients/embeddings_client.py` / `reranker_client.py`: drop the duplicated
  `_OFFLINE_ENVS`, call `settings.is_offline_env()`.
- `app/platform/db/engine.py`: `ReaderRoleMisconfiguredError`; `get_reader_engine()` fails closed
  outside an offline env when the reader URL is unset.
- `app/platform/db/tests/test_engine_reader_role.py` (new, 10 tests, parametrized): 4 offline envs
  (local/test/dev/ci) fall back silently; 3 non-offline envs (production/staging/prod) raise
  `ReaderRoleMisconfiguredError`; 3 envs (including production) with the reader URL set never
  raise. No live DB needed — `create_engine()` doesn't connect eagerly, so a syntactically-valid,
  unreachable URL is enough; `get_settings()` monkeypatched per test (not the global `.env`-backed
  cache) to avoid polluting other tests' settings.

**Verification:** `make check` (from repo root) → **271 passed** (was 261), boundaries clean;
`ruff check` unchanged (2 errors, both pre-existing in `alembic/env.py`/`0001_core_schema.py`);
`ruff format` improved (15 unformatted, was 16 — `embeddings_client.py` brought clean since this
sub-step touched it, per the project standard's "files you edit are brought clean"; its untouched
test file's pre-existing dirt was left alone); `pyright` unchanged (34 errors, identical file
list); no migration (pure code + settings addition, no schema change); the existing DB test harness
(`confluence_sync/tests/conftest.py`) already sets `DATABASE_READER_URL` explicitly for every test
run, so the new fail-closed path is never hit by the rest of the suite.

### 4.6.11 — Event dedup ignores `delivery_id` collisions (LOW) ✅ done (2026-08-11)

**Status: implemented, tested (1 new test), boundaries clean, no ruff/pyright regression → 272
tests total (was 271). Pure code fix, no migration, exactly as scoped.**

**Fix.** `record_event`'s `pg_insert(...).on_conflict_do_nothing(index_elements=["payload_hash"])`
only suppressed a conflict on that one named constraint — a same-`delivery_id`/different-hash
redelivery still violated the separate `ux_event_ledger_delivery_id` partial-unique index,
uncaught. Dropped `index_elements` entirely: a target-less `ON CONFLICT DO NOTHING` absorbs a
violation on *either* unique constraint in one round trip (Postgres semantics — no target means
any unique/exclusion violation on the table), simpler than catching a specific `IntegrityError` or
adding a pre-check `SELECT`, and `ingest_event`'s existing `event_id is None ->
duplicate=True` handling already does the graceful part for free.

**Verified the fix's real effect:** reverted `event_repo.py` locally and re-ran the new test —
failed with the exact uncaught `IntegrityError` on `ux_event_ledger_delivery_id` the finding
described, then passed once the fix was restored.

**Shipped:**
- `app/features/confluence_sync/infrastructure/event_repo.py::record_event`: target-less
  `on_conflict_do_nothing()`.
- `app/features/confluence_sync/tests/test_event_dedup.py` (+1):
  `test_same_delivery_id_different_payload_dedupes_gracefully_not_500` — same `delivery_id`, a
  bumped `cf_version` (changes `payload_hash`) → second ingest dedupes (`duplicate=True`, no
  second job), not a 500.

**Verification:** `make check` (from repo root) → **272 passed** (was 271), boundaries clean;
`ruff check` unchanged (2 errors, both pre-existing); `ruff format` unchanged (15 unformatted, none
of the touched files among them); `pyright` unchanged (34 errors — a transient 35th from
`first_envelope.cf_version + 1` on an `int | None` field was fixed before this count, by hardcoding
the second envelope's `cf_version` instead of arithmetic on an optional); no migration (pure code
fix, no schema change).

### 4.6.12 — `Answer.refusal_reason` never reaches an observable surface (LOW) ✅ done (2026-08-11)

**Status: implemented, tested (2 new tests), boundaries clean, no ruff/pyright regression → 274
tests total (was 272). Took the minimal fix, per the default called out below — operator-visibility
only, no schema/contract change.**

**Fix.** `Answer.refusal_reason` (computed since 4.1, unit-tested since 4.2) was never surfaced
anywhere observable outside the process. Added it to the existing `chat_request` structured log
line in `_stream_answer` (`router.py`, non-cached branch): `refusal_reason=answer.refusal_reason`
— `None` when not refused, a static templated string (never user query/retrieved content, so no
new PII-redaction or log-injection surface) when it is. Mirrored in the `C9_audit` line of the
`security_baseline` docstring above it and in `FEATURES.md`'s chat-endpoint entry.

**A real bug found and fixed mid-flight, entirely without the DB.** Wrote 2 new tests wrapping the
real bound `log` object (`_LogRecorder`, forwards while recording — `structlog.testing.
capture_logs()` doesn't work here: `cache_logger_on_first_use=True` means the module's `log` proxy
resolves its processor chain on its first-ever call across the whole test run, so a later
`capture_logs()` context has no effect once dozens of earlier chat tests have already warmed it).
The first draft imported `router` from `rag_agent`'s public root and monkeypatched
`chat_router.log` — but that `router` is the **`APIRouter` instance**
(`server/router.py:112`), not the **module**; `router.py`'s own code logs via the bare
module-global `log.info(...)`, resolved through the module's own `__dict__`, a different object
entirely. Patching the instance would have silently no-op'd — both tests would have recorded zero
log entries and failed the first time they ran. Caught by `pyright` (36 errors, not the 34
baseline — both new, both `Cannot access attribute "log" for class "APIRouter"`) while Postgres was
still down and no test could run yet; confirmed the type-checker's read was correct via an
empirical, DB-free `python -c` check before trusting it.

**The actual fix:** recovering the real module by import statement alone doesn't work either — a
plain `import a.b.c as x` still resolves through the same shadowed package attribute (`server/
__init__.py`'s `from ...router import (..., router)` overwrites the package's own submodule
reference with the instance, since the imported name collides with the submodule's filename — a
standard Python footgun). Only `sys.modules[...]` is immune, since it's a direct cache lookup by
dotted string name, never subject to attribute shadowing:

```python
chat_router_module = sys.modules[f"{__name__}.router"]  # server/__init__.py
```

Re-exported from `rag_agent/__init__.py` alongside `router`, documented there as test-only.
Deliberately not the "capture the module before the shadowing import runs" ordering trick — that
also works, but `ruff check --fix`'s isort rule wants to reorder those two imports, and reordering
silently breaks it with no error signal; `sys.modules` can't be un-done by an autofix.

**Shipped:**
- `app/features/rag_agent/server/router.py`: `refusal_reason` field on the `chat_request` log line
  + `security_baseline` docstring update.
- `app/features/FEATURES.md`: mirrored `C9_audit` mechanism string.
- `app/features/rag_agent/server/__init__.py`, `app/features/rag_agent/__init__.py`: new
  `chat_router_module` export (test-only handle on the real `router.py` module, see fix above).
- `app/features/confluence_sync/tests/test_chat_endpoint.py` (+2): `_LogRecorder` helper;
  `test_chat_request_log_includes_refusal_reason_when_refused`,
  `test_chat_request_log_has_no_refusal_reason_when_not_refused`.

**Verification:** `uv run pytest .../test_chat_endpoint.py -q -k refusal_reason` → 2 passed. `make
check` (from repo root) → **274 passed** (was 272), boundaries clean. `ruff check` unchanged (2
errors, pre-existing); `ruff format --check` unchanged (15 unformatted); `pyright` unchanged (**34**
errors — was transiently 36 with the bug above, confirmed back to baseline by diffing the
pre-fix/post-fix error-file lists, not just the count). `alembic current` →
`0006_dedupe_source_type_check (head)`, no migration (pure code + log field, no schema change).

### 4.6.13 — Dead-code disposition batch (no code risk) ✅ done (2026-08-11)

**Status: decisions recorded, one code comment added (2 lines, `enums.py`), no logic change, no
migration. 274 tests unchanged (pure-doc/comment sub-step, nothing to re-run beyond the gate).**

Re-verified every claim against the running code before recording a decision — one of the four
turned out to be stated too broadly and is corrected below.

- **`JobStatus.leased`/`.cancelled` — confirmed unused, accepted no-op.** `claim_job`
  (`platform/jobs/queue.py`) transitions a claimed job straight `pending → running`; `leased` is
  never assigned to any job, only read defensively inside `reap_expired`'s recoverable-states
  filter (`Job.status.in_([JobStatus.leased, JobStatus.running])`) in case a future code path ever
  sets it. `cancelled` has zero producers and zero consumers anywhere. Recreating the type to drop
  two members buys nothing — it's a native Postgres ENUM (migration 0001), not a plain CHECK, so
  removal needs its own migration for zero behavior change. **Decision: keep, no action beyond a
  2-line explanatory comment** (added directly above the two members in `enums.py`) so a future
  reader doesn't spend time re-deriving this.
- **`@runtime_checkable` protocols — claim corrected, not all five are truly zero-`isinstance`.**
  Grepped every `isinstance(..., <Protocol>)` call site repo-wide against all six
  `@runtime_checkable` protocols (`ConfluenceGateway`, `EmbeddingProvider`, `Reranker`,
  `AnswerProvider`, `QueryRewriter`, `AnswerGenerator`). Five have zero call sites and stay exactly
  as the original finding described (harmless — `@runtime_checkable` costs nothing and the
  substitutability it documents is real even without a runtime check — no action). **`Reranker` is
  the sixth and is actually exercised**: `test_reranker_client.py:39` asserts
  `isinstance(FakeReranker(), Reranker)` to prove the fake satisfies the protocol structurally. Not
  dead code — no action needed there either, but the batch's "zero isinstance call sites" framing
  was inaccurate for this one member and is corrected here rather than silently carried forward.
- **`evaluation/metrics/latency_metrics.py` — confirmed unwired, no action.** Only import site is
  its own test (`test_latency_metrics.py`); not re-exported from `app.features.evaluation`'s public
  root. Wiring it into the runner is Phase 5.4's job, not this backlog's — leaving as-is.
- **`attachment_extraction.py` — confirmed zero call sites, PARKED note deferred to 4.6.15 as
  planned.** Only import site is its own test; not re-exported from `app.features.ingestion`'s
  public root. Fully built and passing its own tests, just not wired into the ingestion pipeline
  (attachment content isn't searchable yet) — not deleting working code on spec. The "PARKED" note
  itself is written in 4.6.15 (batched with the rest of that sub-step's doc-drift fixes), per the
  original plan text; nothing to do here beyond recording that disposition.

**Verification:** `make check` (from repo root) → **274 passed** (unchanged — no test-relevant code
changed), boundaries clean; `ruff check`/`ruff format --check` unchanged (2 errors / 15 unformatted,
same baseline as 4.6.12); `pyright` unchanged (34 errors, same file list); no migration.

### 4.6.14 — `how_this_works.md` staleness rewrite (doc drift, isolated) ✅ done (2026-08-11)

**Status: doc-only rewrite, one bonus code-comment fix (`retrieval/__init__.py`, no logic change).
274 tests unchanged; boundaries clean; ruff/pyright unchanged (2/15/34 baseline).**

Rewrote every stale section identified, verifying each replacement against the running code first
(not just against `DESIGN.md`'s banner, which itself warns its own file:line anchors predate 4.6.x):

- **Banner (§ intro)** — replaced the "Phases 1–3, 99 tests" framing with the current shipped scope
  (Phases 1–4, 3.5, 5.1–5.3, 4.6.1–4.6.13; 274 backend tests) and what's still `PLANNED`
  (4.6.14–4.6.16, then 5.4+).
- **§1 diagram** — the dotted "PLANNED" segment (rerank → parent expand → grounded answer → SSE
  chat) is solid/shipped now; redrawn as one continuous read+answer flow with RLS noted on the DB
  subgraph.
- **§3** — title and TOC corrected **9 → 10 tables**; added the missing `page_restriction` table
  (row + ER-diagram entity), confirmed against `models.py`'s actual `__tablename__` list (10, not
  9); the `query_trace` row description updated from "answer/citation columns reserved for Phase 4"
  to "written by the answer runtime on the same row" (Phase 4 is done).
- **§7** — retitled "retrieval, the answer runtime, and chat"; corrected the "not yet wired to an
  HTTP endpoint" claim (`rag_agent`'s router *is* `retrieval`'s only consumer and is mounted in
  `main.py`); added rerank as pipeline stage 7 (previously undocumented — the reranker runs inside
  `retriever.py`, after the permission filter); corrected §7.2's "fed by fixtures" claim (real,
  `page_restriction`-backed since 4.3); added **new §7.3** (the `rag_agent` answer runtime: rewrite →
  CRAG retry → refusal → parent expansion → generation → citation enforcement) and **§7.4** (the
  `POST /chat`/feedback HTTP surface) — neither existed in this doc before, despite being Phase 4's
  main deliverable.
- **§9.4, §10, §11** — updated from future tense ("Phase 4 will add", "target pipeline") to past
  tense with a per-item shipped/planned status column; §11's "post-3.5"/"post-4" framing and its
  `make test` (99 tests) reference corrected to `make check` (274 tests).
- **Two dead TOC anchors found and fixed** — the plan only named one (§3's "the-7-tables" target
  against a heading that already said "9 tables"); grepped every TOC anchor against every heading's
  actual slug and found a second, unrelated one at §12 (TOC still read "Open design discussion —
  Confluence source scoping", a leftover from before that section was rewritten to "implemented" —
  target and link text both wrong). Verified the fix with a slugify script that confirms zero
  remaining mismatches, not by eye.
- **§2 code-tree diagram** — `rag_agent` was missing from `features/`, the reranker client was
  still marked `(PLANNED)` under `platform/clients/`, `shared/` listed only `hashing.py` (also has
  `rate_limiter.py`, `ttl_cache.py`), and the table count repeated the stale "7 tables" — all fixed
  against the actual directory listing.
- **Anchor index (bottom table)** — added the reranker client, `rag_agent`'s answer service/
  refusal/citations/router/cache, and `DESIGN.md`; corrected "7 tables" → "10 tables".
- **Bonus fix, same root cause as the §7 finding**: `app/features/retrieval/__init__.py`'s own
  docstring still said "Status: not yet wired into `app.main`" — corrected in the same pass since
  it's the identical stale claim living in code instead of docs, zero behavior change.

**Verification:** `make check` → **274 passed** (unchanged), boundaries clean; `ruff check`/`ruff
format --check` unchanged (2 errors / 15 unformatted); `pyright` unchanged (34 errors, same file
list); no migration.

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

## Phase 4.7 — Obi widget (chat UI) ✅ done, uncommitted *(independent; does not gate Phase 5)*

**What this phase built:** replaced `apps/web`'s chat UI with a pixel-accurate rebuild of the
user-supplied Obi mockup (`docs/rag/reference/obi-mockup/Obi Assistant.dc.html`, a proprietary
prototyping-tool export — design/interaction reference only, no reusable code, no real backend).
The floating widget (launcher → teaser → panel) is now the **only** chat surface in `apps/web` —
the old standalone full-page `/chat` route existed for most of this phase and was removed at the
end once the widget covered everything it did. This section is the ledger's as-built summary,
rewritten 2026-08-11 to describe what actually exists today rather than the sub-step-by-sub-step
history that got it there (that history — every deviation, live-browser bug caught, and copy
decision — is preserved in git history and in `docs/rag/OBI-WIDGET-DESIGN.md`'s own revision trail
for anyone who needs it; nothing here contradicts it, it's just no longer the front door).

**Not committed as of this writing** — see `docs/rag/OBI-WIDGET-DESIGN.md` §8 and this file's own
§0 status ledger for the exact test/verification gap before that should happen.

### Architecture

- **D0 — one shared conversation, not two.** `ChatSessionProvider`/`useChatSession()`
  (`features/chat/ui/chat-session-provider.tsx`) owns all session state — messages, pending,
  restart, and (as of the widget-only cleanup) the widget's own UI-copy `locale` — mounted once in
  `apps/web/src/app/layout.tsx` alongside `ChatWidget`. Nothing else mounts a second provider.
- **Floating overlay, not a flex sibling.** The mockup lays its panel out as a flex sibling that
  shrinks a fake host dashboard; `floating-frame.tsx` instead uses `position: fixed`, pinned to the
  right edge, full height, on top of page content — this app's real pages aren't designed to
  resize for a docked panel. Same visual width/border/shadow as the mockup
  (`clamp(360px,29%,440px)`, `-4px 0 16px rgba(35,38,59,0.04)`).
- **One surface.** `ChatWidget` is the feature's only UI export. There is no full-page chat route;
  opening the widget (launcher or teaser click) is the only way to reach the conversation.

### Component map (`apps/web/src/features/chat/ui/`, all feature-internal — none promoted to
`apps/web/src/components/` yet, each has exactly one consumer)

| Component | Role |
|---|---|
| `chat-session-provider` | Conversation state machine + `locale` — `ChatSessionProvider`/`useChatSession`, mounted once in `app/layout.tsx`. |
| `chat-widget` | Public root: `ChatLauncher` + conditional `TeaserPopup` while closed, `FloatingFrame` wrapping `panel-body` while open. |
| `use-widget-visibility` | Launcher/teaser timing (3000ms initial, 20000ms repeat after each close/dismiss), fake-timer tested. |
| `chat-launcher` / `teaser-popup` / `floating-frame` | Closed-state button, proactive nudge card, open-state chrome. `floating-frame` carries `data-obi-widget-root` so the screenshot capture can hide the widget during its own capture. |
| `panel-body` | Composition root: `panel-header` + `contour-background` + `message-list` + `composer`. Owns the screenshot-capture handler (`html-to-image` → `Composer`'s imperative handle) and the capture flash overlay. |
| `panel-header` | Chrome bar — mark/name, More/Screenshot/Language/Close icon row; owns the menus' mutually-exclusive state; locale-aware labels. |
| `menu` / `menu-item` | Shared dropdown shell for both header menus. |
| `language-menu` | Real six-locale switcher — calls `useChatSession().setLocale`. |
| `contour-background` | Ambient wavy-line SVG behind the message thread, pixel-exact to the mockup. Pure decoration. |
| `message-list` / `message-bubble` / `typing-indicator` | Thread rendering — greeting, empty-state suggestion chip, per-turn bubbles/citations/feedback, the ~90-word typing-indicator bank. Locale-aware. |
| `composer` | Message input, send, image attachments (file-picker + clipboard-paste + screenshot, all through one pipeline). `forwardRef` exposing `ComposerHandle.addAttachmentFile` for the header's screenshot button. |
| `attachment-strip` | 40×40 thumbnail preview row for composer attachments; clicking a thumbnail opens `image-lightbox` (4.7.8). |
| `image-lightbox` | Full-size zoomed preview overlay for a clicked attachment/screenshot thumbnail (4.7.8) — local preview only, closes on Escape/backdrop/close-button, no analysis. |
| `icon-button` / `assistant-mark` | Shared primitives. |

`model/i18n.ts` holds the widget's own six-locale UI-copy table. `model/messages.ts` holds the
render view-model. Public root `index.ts` exports `ChatWidget` and `ChatSessionProvider` only.

### Design tokens, motion, pixel spec

Real brand tokens (not placeholders) live in `packages/design-tokens/src/tokens.ts`: the mockup's
own light Stripe-esque theme, `#635bff` indigo accent, Inter via `next/font/google`. Every
`@keyframes` the widget uses is in `apps/web/src/app/globals.css` (`menu-in`, `feedback-pop`,
`typing-shimmer`, `typing-spin`, `teaser-in`, `launcher-pulse`, `screenshot-flash`), each with a
`motion-reduce:` fallback. The full pixel-for-pixel spec (exact padding/radius/shadow/timing values
per component) lives in `docs/rag/OBI-WIDGET-DESIGN.md` §2–4 rather than duplicated here — that
file is kept in sync with the code, not with this ledger's narrative.

### Product decisions — current state (what's real vs. an honest stub)

| Piece | Status |
|---|---|
| Chat send/receive, streaming, citations, refusal, feedback, restart | **Real** — the actual `apps/automation` pipeline, unchanged by this phase. |
| Image attachment (file-picker + clipboard-paste) | **Real capture and preview**, honest stub on send — no vision backend exists, so attachments are dropped with an inline notice and the message sends as text only. Clicking a thumbnail (4.7.8) opens a **real, full-size zoomed preview** (`ImageLightbox`) — still local-only, no analysis. |
| Screenshot button (header, between More and Language) | **Real capture** of the page behind the widget (`html-to-image`), lands in the same attachment pipeline as any other image — same honest "not analyzed yet" notice on send, same real click-to-zoom preview (4.7.8) once captured. Building real analysis needs a vision-capable backend call; that requirement is now scoped as **Phase 7** (supersedes the former `docs/future-ideas/IDEAS.md` #3). |
| Suggestion chip (empty-state) | **Real** — sends an honestly-answerable question ("What can you help me with?") through the real session. Copy is adapted from the mockup's Stripe-only "My verification status," which had no Confluence equivalent. |
| Language switcher (6 locales) | **Real for the widget's own UI copy** (greeting, chip, placeholder, footer, teaser, header labels) — does **not** change what language the RAG agent answers in; that's the model's own behavior against `apps/automation`, unscoped backend work. Translations are direct/unreviewed, same quality bar as the mockup's own table, not professionally localized. |
| "Developer docs" / "Support articles" menu items | **Honest disabled stubs** — no real target page exists yet. |
| Assistant display name "Obi" | Still the mockup's placeholder, not a confirmed product decision. |

### Known gaps / debt (disclosed, not silently carried)

- **Test suite not re-run since the last two sub-steps** (contour background + suggestion chip;
  screenshot + real i18n + `/chat` removal) — both were built and verified only by `tsc --noEmit`
  + `pnpm --filter web build`, per an explicit user instruction to skip the test gate for those
  passes. Before trusting this phase as done by this repo's normal bar (`CLAUDE.local.md` §2):
  - `chat-panel.test.tsx` was deleted along with `ChatPanel` — its characterization coverage
    (streaming, citations, refusal, error, feedback, restart, abort-on-unmount) has no replacement.
    `chat-widget.test.tsx` does not exercise all of the same paths.
  - `language-menu.test.tsx`, `chat-launcher.test.tsx`, and `message-list.test.tsx` now fail
    because those components call `useChatSession()` (for `locale`) without those tests providing
    a `ChatSessionProvider` wrapper.
  - The full `pnpm --filter web test` count from before this cleanup was 113; it has not been
    re-run since.
- **A real layout bug shipped and was caught live, not by any test**: adding the contour
  background's absolutely-positioned layers made `panel-body.tsx`'s message thread collapse to
  zero height (its children stopped contributing to the flex container's auto height), clipping
  the greeting/suggestion-chip invisible while the composer rendered directly under the header.
  Fixed by giving the panel's root section `h-full` so `flex-1` has a real height to grow into.
  Caught only by opening the widget in a real browser — another data point for why
  `CLAUDE.local.md`'s live-verification requirement exists, not just unit tests.
- No dependency-audit concerns beyond the one new dependency added, `html-to-image` (real
  screenshot capture) — justified because no existing capture utility exists in this repo and the
  alternative (`getDisplayMedia()`) is a much heavier permission-grant flow for a one-click
  affordance.

### Verification status

`tsc --noEmit` and `pnpm --filter web build` clean as of the last change (including the `h-full`
layout fix above, confirmed live in a real browser: greeting, suggestion chip, contour background,
composer, and footer all render in the correct order and are all visible). No automated test run
covers the current state end to end — see "Known gaps" above. Nothing in this phase has touched
`apps/automation`.

**Sequencing vs. Phase 4.6:** frontend-only (TypeScript), touches zero files in common with 4.6
(backend Python) — independent of it either direction. **Do this phase before 4.8** — split the
repo once the widget's real file layout is settled, not mid-refactor.

### 4.7.8 — Attachment/screenshot image lightbox (click-to-zoom) ✅ done (2026-08-11)

**Context.** The user reported seeing (elsewhere, not yet in this widget) an "attach or screenshot
an image, click it, see a full-size zoomed preview" pattern and asked for it here, plus for every
such image to be analyzed for context. On inspection, **neither existed**: `attachment-strip.tsx`
only ever rendered a 40×40 thumbnail with a remove button, `message-list.tsx` didn't render sent
images at all (attachments are dropped before send, per the stub above), and no vision-capable
backend call exists anywhere in this repo. Per the user's own scoping rule (2026-08-11): implement
now whatever is frontend-only with no impact on the backend/vector-store/overall structure; put
everything else in a new phase. Split accordingly:

- **Click-to-zoom (frontend-only) — built here.** `image-lightbox.tsx` (new): a full-viewport
  overlay (`z-widget-menu`, the stack's existing top layer — no new z-index token needed),
  `role="dialog"`/`aria-modal`, closes on Escape, backdrop click, or its own close button.
  `attachment-strip.tsx` wraps each thumbnail in its own `<button aria-label="View {name}">`
  (kept separate from the existing remove button) that opens the lightbox for that attachment;
  internal `zoomedId` state, no prop-API change for `Composer` (still just `attachments`/
  `onRemove`). This only covers the composer's **pre-send** attachment strip — the only place any
  image currently renders — since sent attachments still don't reach `message-list.tsx` (that's
  the backend/contract work below).
- **Vision analysis of every attached/screenshot image (backend + contract) — NOT built here,
  scoped as Phase 7 below.** Sending the image data to the backend, a vision-capable model call,
  folding the analysis into the answer, and rendering the sent image + its analysis in
  `message-list.tsx` (with the same click-to-zoom there) all touch `packages/contracts`,
  `apps/automation`'s `AnswerService`/`llm_client.py`, and the security control set — none of that
  is frontend-only, so per the scoping rule above it does not get implemented ad hoc here. This
  supersedes `docs/future-ideas/IDEAS.md` #3 ("Screenshot-grounded guidance"), which raised the
  same gap in the abstract; that entry now points at Phase 7 instead of sitting unscoped.

**Shipped:** `apps/web/src/features/chat/ui/image-lightbox.tsx` (new); `attachment-strip.tsx`
(thumbnail click wired to it). Tests: `attachment-strip.test.tsx` +2 (opens on click + closes on
Escape with both the thumbnail and lightbox `alt` present; closes via its own close button without
triggering `onRemove`) → 4/4 in that file. `tsc --noEmit`: zero new errors (the two pre-existing
`language-menu.test.tsx` errors are the same disclosed 4.7 test-suite gap above, untouched by this
sub-step). Full `pnpm --filter web test` run: the new/touched files (`attachment-strip.test.tsx`,
`chat-session-provider.test.tsx`, `chat-widget.test.tsx`, etc.) all pass; confirmed by running
`attachment-strip.test.tsx` standalone (4/4) and by re-running the suite at the pre-this-session
commit (`aae90e5`, 113/113 clean) to establish that today's other 25 failures across
`composer.test.tsx`/`chat-launcher.test.tsx`/`language-menu.test.tsx`/`panel-header.test.tsx`/
`teaser-popup.test.tsx`/`message-list.test.tsx` are the pre-existing, already-disclosed "Known
gaps / debt" gap above (uncommitted prop/provider drift from earlier in this phase) — not something
this sub-step introduced. That gap is still open and still gates trusting Phase 4.7 as fully closed
by this repo's normal bar; fixing it is not in this sub-step's scope.

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

## Phase 7 — Vision-grounded image analysis (attachments + screenshot capture) ⬜ todo

**Scoped, not started, 2026-08-11.** Raised by the user after observing (elsewhere, not in this
repo) that an attached or screenshotted image can be clicked for a full-size preview *and* gets
analyzed for context by the assistant. On inspection neither piece existed here — see Phase 4.7.8
above for the click-to-zoom half, which **is** frontend-only and was built immediately per the
user's own scoping rule. This phase is everything left: the half that touches the backend,
contracts, and the security control set, so it doesn't get built ad hoc inside a frontend sub-step.
**Supersedes `docs/future-ideas/IDEAS.md` #3** ("Screenshot-grounded guidance"), which raised the
same gap in the abstract with no design; that entry now points here.

**Goal.** Every image added to the widget — a file-picker/clipboard-paste attachment *or* the
header's "screenshot this page" capture (`html-to-image`, PLAN 4.7.7, real capture already) — is
sent through a vision-capable model call, and the resulting understanding of what's in the image
is folded into the answer, so a question like "what's on this screenshot?" or "what should I click
next here?" can actually be answered instead of the image being silently dropped (today's stub,
per Phase 4.7's product-decisions table). The chat surface this lands in is the **existing, single**
Obi widget (composer placeholder "Ask about your Confluence workspace…") — there is no second chat
surface to build or choose between; the widget already is the one integration point for both the
RAG-over-Confluence pipeline and this new image modality. Note this is orthogonal to why *text*
questions about the real Confluence workspace don't yet return useful answers — that's the
already-tracked Confluence-token/no-real-corpus blocker (§0), not something this phase fixes.

**Not scoped or designed yet — this section records the requirement and the known seams, not a
plan.** Per this repo's own process (`docs/future-ideas/IDEAS.md`'s header), a real design pass
(and an ADR if it changes a durable architecture decision) must happen before implementation,
same as any other phase. Known seams from inspecting the current code:

1. **Contract gap.** `ChatRequestBody`/`chat.yaml` (`packages/contracts`) is text-only — no field
   carries image data. Needs a shape decision (inline base64 on the existing `POST /chat` history
   turns, vs. a separate upload endpoint returning a reference the chat call points at) before any
   code changes.
2. **Backend gap.** `AnswerService`/`llm_client.py` (`apps/automation`) is text-in/text-out.
   Anthropic's multimodal message format (image content blocks) is a real, supported capability of
   the same `AnthropicMessagesClient` already in use — see the `claude-api` skill/reference before
   wiring it — but nothing in this pipeline calls it today.
3. **Security review required before shipping, per `securing-http-and-llm-endpoints`** — this is a
   new, genuinely sensitive input class the existing control set was never designed for:
   image-borne prompt injection (text rendered *inside* an image, or a UI screenshot crafted to
   look like a system message), a real image-size/vision-token cost cap (no number exists yet —
   don't invent one, measure against real usage once this is scoped), and PII exposure — the
   current `redact_pii` (`rag_agent/domain/pii.py`) is a text regex pass over the prompt string; it
   does not and cannot inspect image bytes, so a screenshot containing visible PII (an email in a
   support ticket, a customer name in a dashboard) reaches the model unredacted unless a new control
   is added. Idea #3's own note ("privacy/consent implications — this is genuinely sensitive
   input") still applies in full.
4. **Frontend follow-on.** Once the backend accepts and returns something for an image turn,
   `message-list.tsx` needs to actually render the sent image (it doesn't today — attachments are
   dropped before `onSend`, per Phase 4.7's stub) with the same `image-lightbox.tsx` click-to-zoom
   4.7.8 already built for the composer, plus whatever UI communicates "Obi looked at your image."

**Sequencing.** Independent of Phase 5/6 — no shared files, no shared risk. Should be planned as
its own phase (design → ADR-if-needed → tasks → acceptance) once picked up, not folded into 4.7 or
5 ad hoc, matching how Supabase got its own Phase 6 rather than being folded into 4.2.

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
