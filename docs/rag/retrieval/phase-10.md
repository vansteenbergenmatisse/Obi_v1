# Phase 10 — Knowledge-scope tagging (retrieval-side half)

**Status:** §§10.3–10.6 done and committed (2026-08-24 — 10.3 `daecb58` migration; 10.4 `d347dc8`
retrieval-time filtering, behind `enable_knowledge_scope_filtering`, default off; 10.5 chat request/
contract threading + 10.6 always-present curated knowledge in `a663a95`). **§10.7 done (2026-08-24):**
the live corpus was labeled + migrated (all 9 pages → `['base', 'general']`), the readiness gate
reported READY, and `enable_knowledge_scope_filtering` was flipped **`true`** — the filter is now
live. Confirmed end-to-end after the flip: a `mews`-scoped request (`resolve_allowed_scopes` →
`['general','mews']`) returns grounded hits, while a `['mews']`-only filter returns none. The
migration/flip half is ingestion-side ([`../ingestion/phase-10.md`](../ingestion/phase-10.md)'s §10.7).
`docs/rag/PLAN.md` Phase 10 §§10.3–10.7. Design doc:
[`docs/adr/0011-Knowledge-Scope-Tagging-And-Retrieval-Filtering.md`](../../adr/0011-Knowledge-Scope-Tagging-And-Retrieval-Filtering.md).
The writer/tagging half — deriving tags from Confluence labels — is in
[`../ingestion/phase-10.md`](../ingestion/phase-10.md).

Promotes [`../../future-ideas/IDEAS.md`](../../future-ideas/IDEAS.md) idea #8's "knowledge/RAG
separation" concern. The concrete gap this closes, confirmed by direct code read (idea #2, then
ADR-0011's Context): `app/features/retrieval/infrastructure/search_repo.py::_base_filters()` filters
`is_active`/`kind`/`page_status`/`space_id`/`source_id` — `tags` is written at every ingestion
activation ([phase-3.5.md](./phase-3.5.md), ADR-0004) and read by nothing at query time.

**Terminology note:** "knowledge scope," never "provider" — see ADR-0011's Context. **Currently
recognized scopes: `general`, `mews`, `opera-cloud`, `toast`** (the `toast` value means Toast POS, not
this repo's own codename — disclosed and deliberate, see ADR-0011's Context).

**Operator: adding a new knowledge scope.** The recognized set lives in
[`config/knowledge_scopes.json`](../../../config/knowledge_scopes.json) — at the true **repo
root**, not nested under `apps/automation` or `apps/web`, not `.env`, not buried in
`settings.py`. No code anywhere hardcodes
`mews`/`opera-cloud`/`toast`; both this file's filtering and the ingestion-side tagging
(`../ingestion/phase-10.md`) just match against whatever's in that JSON file
(`Settings.knowledge_scope_set` loads it via
`platform/config/knowledge_scopes.py::load_recognized_knowledge_scopes`). To recognize a new
provider: add an entry to that JSON file, then label the matching Confluence pages with that
exact tag — nothing in `app/` needs to change. `.env`'s `DEFAULT_KNOWLEDGE_SCOPE`/
`ENABLE_KNOWLEDGE_SCOPE_FILTERING` are separate runtime toggles, not the scope list itself.

## What's new here

- **`retrieval/domain/knowledge_scope.py::resolve_allowed_scopes`** (§10.4, consumed by §10.5) —
  co-located with `permission.py::classify_scope`, which already plays the same "interpret an
  incoming request-shaped value" role for `principal`. Resolves the final scope allow-list (always
  includes `general`) from a request's `knowledge_scope`, falling back to a deployment-level
  default, then to `general` alone. An unrecognized requested value degrades silently rather than
  erroring the request; the caller (§10.5) is responsible for logging the degradation, since this
  function is pure and takes no logger. Exported from `retrieval/__init__.py`'s public root.
- **`_base_filters()`'s new `AND tags && :knowledge_scopes` predicate** (§10.4, shipped) — a bound
  Postgres array-overlap filter (never interpolated, same discipline as the existing `sources`
  predicate), backed by the partial GIN index `ix_chunk_tags_gin` (§10.3). Threaded through
  `keyword_search`/`dense_search`/`fetch_rerank_texts`. **Double-gated, not just flag-gated:**
  `HybridRetriever` takes `enable_knowledge_scope_filtering` at construction (wired from
  `Settings.enable_knowledge_scope_filtering`, default `false` — ships dark, exactly like
  `enable_clarification_branch`) and only forwards a caller's `knowledge_scopes` argument to the
  search layer when that flag is `True`; with the flag off the predicate is never added regardless
  of what any caller passes, so a premature/mistaken caller can't accidentally leak the filter live
  before an operator deliberately flips it on. A chunk with an empty `tags` array (the live
  `base`-only pages, pre-relabel) matches no non-empty scope filter — proven live against the real
  DB, not just asserted (ADR-0011 Decision 1). `QueryTrace.allowed_knowledge_scopes` (§10.3's
  column) is populated with whatever the retriever actually applied (`None` when the flag is off or
  no scopes were requested), mirroring `allowed_sources`. `EXPLAIN` against a forced plan (competing
  `is_active`-partial indexes dropped inside an uncommitted test transaction, `enable_seqscan` off)
  confirms `ix_chunk_tags_gin` is plan-usable for the real query shape — closes 10.3's own deferred
  acceptance criterion; the live fixture corpus is far too small for the planner to prefer it on
  cost alone, so this proves usability, not real-cardinality cost-preference. Only after the
  ingestion-side corpus migration ([`../ingestion/phase-10.md`](../ingestion/phase-10.md)'s §10.7)
  is done should an operator flip the flag on.
- **`ChatRequestBody.knowledge_scope`** (§10.5, shipped) — new optional field on `POST /chat`,
  shape-validated (short lowercase slug, `_KNOWLEDGE_SCOPE_PATTERN`) but not whitelisted — an
  unrecognized-but-well-shaped value still reaches `AnswerService`, which degrades it, never a 422
  for that case; only a value that could not possibly be a real scope (spaces, punctuation, >64
  chars) is rejected at the HTTP boundary. `AnswerService.answer()` gains a `recognized_knowledge_scopes`/
  `default_knowledge_scope` constructor pair (wired from `Settings.knowledge_scope_set`/
  `Settings.default_knowledge_scope` in `main.py::build_answer_service`) and resolves
  `resolve_allowed_scopes(...)` exactly **once per request** — the CRAG retry
  (`answer_service.py::_apply_crag_retry`, not `retriever.py` — corrected from this doc's earlier,
  pre-implementation file-location guess) reuses that same resolved list, it never re-resolves.
  An unrecognized requested value is logged (`knowledge_scope_unrecognized`, `requested` +
  `resolved_scopes`) — `resolve_allowed_scopes`'s own docstring: "the caller logs the degradation."
  `packages/contracts`' `ChatRequest.knowledgeScope` and
  `apps/web/src/features/chat/server/{validation.ts,route-handlers.ts}` gain the matching field,
  forwarded unmodified (`toBackendChatBody`). `ChatSessionProvider` gains an optional
  `knowledgeScope` prop, threaded once into every `streamChat()` call — genuinely new plumbing;
  nothing resembling "which platform is this chatbot embedded on" existed anywhere in `apps/web`
  before this phase. **No visible way to set that prop to a real value yet** — that UI switcher is
  §10.8, not this sub-step; `layout.tsx` is deliberately untouched here.
  **Two corrections beyond the plan's own file list, both required for correctness, not named in
  ADR-0011's Decision 6 text:** (1) `CachingAnswerService`'s exact-match cache key
  (`answer_cache.py::_cache_key`) now also binds `knowledge_scope`, mirroring the pre-existing
  `scope`/principal binding — without it, two requests with identical history/principal but
  different `knowledge_scope` would collide on the same cache entry and replay evidence scoped to
  the wrong provider. (2) The `Idempotency-Key` replay cache's binding
  (`router.py::_idempotency_cache_key`) is extended from `(principal, history)` to
  `(principal, history, knowledge_scope)` for the identical reason (PLAN 4.6.3's original fix,
  extended here).
- **`CuratedKnowledgeEntry`** (§10.3/10.6) — a new table for always-present, admin-maintained
  knowledge (Layer B in the mega-prompt's four-layer framing: System → Always-present → RAG evidence
  → conversation). At answer time, active entries matching the resolved allowed scopes are rendered
  as synthetic leading hits and **prepended to real retrieved hits before `build_evidence_block`/
  `enforce_citations` run** — they get citation markers `[1..k]` exactly like retrieved evidence, so
  the existing grounding/citation-enforcement guarantee covers them too, with zero changes to
  `rag_agent/domain/citations.py` or `prompt.py`'s signatures. Seeded via a new one-off
  `scripts/seed_curated_knowledge.py` (no CRUD API yet, mirrors `seed_source_scope.py`'s ownership
  decision).
- **`QueryTrace.allowed_knowledge_scopes`** (§10.3) — new nullable audit column, mirrors the existing
  `allowed_sources` column exactly; no new tracing pipeline.

## Why a hard filter, and why it's gated

ADR-0011 Decision 5 chose a **hard** SQL filter (not a soft rerank bias) because this phase's scope is
*declared* by the deployment/embed context, not *inferred* about a customer — unlike
`docs/future-ideas/IDEAS.md` idea #2's client-integration case, which explicitly needs a soft bias so
switching/comparison questions ("we're on Mews, does this also work on Opera?") stay answerable. That
soft-scoping need, and any explicit "search all scopes" mode, are deliberately deferred (ADR-0011
Decision 8) — see idea #8's updated notes in `IDEAS.md`.

The filter ships behind `enable_knowledge_scope_filtering` — the code default is `false` (ships dark)
specifically because a live corpus with no recognized knowledge-scope label would silently disappear
from every scoped query the moment the filter turned on, which is correct behavior per this phase's
own rules but must be a deliberate, verified operator action, not an accidental regression. §10.7's
`scripts/verify_knowledge_scope_backfill.py` is the machine gate for exactly that action: it exits
non-zero (and names the offending `page_id`s) while any live chunk still lacks a recognized scope
tag, and exits 0 only once the corpus is fully labeled — see
[`../ingestion/phase-10.md`](../ingestion/phase-10.md)'s §10.7 for the check itself. **As of 2026-08-24
that gate passed and the deployment `.env` flag is now `true`** — the corpus was relabeled (all 9
pages → `['base', 'general']`) and the flip verified end-to-end, so the filter is live in this
deployment while the code default stays dark for any fresh environment.

## Files & folders used

```
apps/automation/app/features/retrieval/
├── domain/knowledge_scope.py (new, §10.4)         resolve_allowed_scopes
├── infrastructure/search_repo.py (§10.4)          AND tags && :knowledge_scopes, ix_chunk_tags_gin
├── infrastructure/trace_repo.py (§10.4)           allowed_knowledge_scopes param
├── application/retriever.py (§10.4)               enable_knowledge_scope_filtering ctor flag;
│                                                   knowledge_scopes call-time param on
│                                                   retrieve()/retrieve_with_context()
├── __init__.py (§10.4)                            exports resolve_allowed_scopes
├── tests/test_knowledge_scope.py (new, §10.4)
├── tests/test_search_repo_knowledge_scope.py (new, §10.4)   SQL-shape/binding spy-session tests
apps/automation/app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py (new, §10.4)
│                                                   real-DB cross-scope leakage + GIN EXPLAIN proof
apps/automation/app/main.py (§10.4)                wires settings.enable_knowledge_scope_filtering
apps/automation/app/platform/config/settings.py (§10.4)     enable_knowledge_scope_filtering flag

apps/automation/app/features/rag_agent/
├── server/router.py (§10.5)                       ChatRequestBody.knowledge_scope + shape
│                                                   validator; idempotency key binds knowledge_scope
├── application/answer_service.py (§10.5)          resolves allowed_scopes once/request; threads
│                                                   through retrieve_with_context + CRAG retry
├── application/answer_cache.py (§10.5)            cache key binds knowledge_scope (correctness
│                                                   fix beyond the plan's own file list)
├── tests/test_answer_service.py (§10.5)           resolution/degradation/CRAG-reuse cases
├── tests/test_answer_cache.py (§10.5)             cross-scope cache-leak regression cases
apps/automation/app/features/confluence_sync/tests/test_chat_endpoint.py (§10.5)
│                                                   forwarding, malformed-shape 422, idempotency
│                                                   cross-scope regression, end-to-end SSE
apps/automation/app/main.py (§10.5)                wires knowledge_scope_set/default_knowledge_scope
apps/automation/app/platform/db/models.py                                      CuratedKnowledgeEntry, ix_chunk_tags_gin, QueryTrace.allowed_knowledge_scopes column (§10.3, done)
apps/automation/alembic/versions/0007_knowledge_scope.py (§10.3, done)
apps/automation/app/platform/db/tests/test_migration_0007_knowledge_scope.py (§10.3, done)   real alembic head/-1/head round trip
packages/contracts/src/index.ts (§10.5)                                        ChatRequest.knowledgeScope
packages/contracts/src/openapi/chat.yaml (§10.5)                               ChatRequest.knowledgeScope (source of truth)
apps/web/src/features/chat/server/validation.ts (§10.5)                        parses knowledgeScope
apps/web/src/features/chat/server/route-handlers.ts (§10.5)                    forwards knowledgeScope -> knowledge_scope
apps/web/src/features/chat/ui/chat-session-provider.tsx (§10.5)                ChatSessionProviderProps.knowledgeScope

apps/automation/app/features/rag_agent/ (§10.6, done, uncommitted)
├── domain/curated_knowledge.py (new)              CuratedEntry, CuratedHit, curated_entry_to_hit
│                                                   (pure — the query itself lives in
│                                                   infrastructure/, a correction from the plan's
│                                                   single-file text: every other domain/ module in
│                                                   this repo is I/O-free, mirroring retrieval's own
│                                                   domain/infrastructure split for §10.4)
├── infrastructure/curated_knowledge_repo.py (new) fetch_curated_entries — bound `tags && :scopes`
│                                                   param, never interpolated
├── application/answer_service.py                  allowed_scopes resolution hoisted above the
│                                                   query/no-query split (curated entries reach the
│                                                   text-empty/image-only path too); composes
│                                                   evidence_hits = curated_hits + result.hits before
│                                                   build_evidence_block/enforce_citations; citation
│                                                   construction now indexes evidence_hits, not
│                                                   result.hits
├── __init__.py                                    exports fetch_curated_entries, CuratedEntry
├── tests/test_curated_knowledge.py (new)          pure adapter + spy-session SQL-shape/injection
│                                                   safety tests
├── tests/test_answer_service.py                   end-to-end composition, numbering, no-op when no
│                                                   reader configured, image-only-path coverage
apps/automation/app/features/confluence_sync/tests/test_curated_knowledge_repo.py (new)
│                                                   real-DB scope filtering, cap, is_active, ordering
apps/automation/app/features/confluence_sync/tests/conftest.py                 curated_knowledge_entry
│                                                   added to the truncate-between-tests table list
apps/automation/app/main.py                        wires reader_sessionmaker + curated_knowledge_max_entries
apps/automation/app/platform/config/settings.py    curated_knowledge_max_entries (default 5)
apps/automation/scripts/seed_curated_knowledge.py (new)   one-off CLI, mirrors seed_source_scope.py
```

**§10.6 deliberately left unresolved, per the plan's own explicit flag not to guess it:** a curated
citation's `url` is empty (`packages/contracts`' `Citation.url` already documents empty as
"unavailable") — there is no distinct "Source: curated knowledge" visual treatment yet. That is a
UI/contract decision for a future sub-step once the widget side is designed, not a gap in this one.

## Not this file

Label-driven tag derivation and the ingestion-side corpus migration — see
[`../ingestion/phase-10.md`](../ingestion/phase-10.md).
