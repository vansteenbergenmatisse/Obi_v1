# Phase 10 — Knowledge-scope tagging (retrieval-side half)

**Status:** §§10.3–10.4 done (2026-08-24 — 10.3 `daecb58` migration; 10.4 retrieval-time filtering,
behind `enable_knowledge_scope_filtering`, default off); §§10.5–10.6 not started. `docs/rag/PLAN.md`
Phase 10 §§10.3–10.6. Design doc:
[`docs/adr/0011-Knowledge-Scope-Tagging-And-Retrieval-Filtering.md`](../../adr/0011-Knowledge-Scope-Tagging-And-Retrieval-Filtering.md).
The writer/tagging half — deriving tags from Confluence labels — is in
[`../ingestion/phase-10.md`](../ingestion/phase-10.md).

Promotes [`../../future-ideas/IDEAS.md`](../../future-ideas/IDEAS.md) idea #8's "knowledge/RAG
separation" concern. The concrete gap this closes, confirmed by direct code read (idea #2, then
ADR-0011's Context): `app/features/retrieval/infrastructure/search_repo.py::_base_filters()` filters
`is_active`/`kind`/`page_status`/`space_id`/`source_id` — `tags` is written at every ingestion
activation ([phase-3.5.md](./phase-3.5.md), ADR-0004) and read by nothing at query time.

**Terminology note:** "knowledge scope," never "provider" — see ADR-0011's Context. **Confirmed
recognized scopes: `general`, `mews`, `opera-cloud`, `toast`** (the `toast` value means Toast POS, not
this repo's own codename — disclosed and deliberate, see ADR-0011's Context).

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
- **Not yet wired (§10.5):** no production caller passes a real per-request `knowledge_scopes` value
  yet — `HybridRetriever.retrieve()`/`retrieve_with_context()` accept it as an optional call-time
  argument, but `AnswerService`/`ChatRequestBody` don't have a `knowledge_scope` field to resolve one
  from. §10.5 threads that end to end, including through the CRAG retry path in
  `answer_service.py::_apply_crag_retry` (not `retriever.py` — corrected from this doc's earlier,
  pre-implementation file-location guess).
- **`ChatRequestBody.knowledge_scope`** (§10.5) — new field on `POST /chat`, threaded through
  `AnswerService.answer()` → `HybridRetriever.retrieve_with_context()` → every retrieval attempt in
  the request (initial search **and** the CRAG retry) exactly the way `principal` already threads
  through today, resolved once per request. `packages/contracts`' `ChatRequest` and
  `apps/web/src/features/chat/server/route-handlers.ts::toBackendChatBody()` gain the matching field,
  forwarded unmodified. The widget/embed configuration gains a `knowledgeScope` value — genuinely new
  plumbing; nothing resembling "which platform is this chatbot embedded on" existed anywhere in
  `apps/web` before this phase (confirmed by direct read of `chat-session-provider.tsx` and
  `OBI-WIDGET-DESIGN.md`).
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

The filter ships behind `enable_knowledge_scope_filtering` (default off) specifically because the live
corpus (9 pages, `source_scope`-tagged `base` only, per `PLAN.md` §0 2026-08-21) has no recognized
knowledge-scope label yet — flipping the filter on before that corpus is relabeled would make it
silently disappear from every scoped query, which is correct behavior per this phase's own rules but
must be a deliberate, verified operator action, not an accidental regression.

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

-- not yet built (§10.5/§10.6) --
apps/automation/app/features/rag_agent/
├── domain/curated_knowledge.py (new)    fetch_curated_entries, scope filtering, entry cap
├── server/router.py                     ChatRequestBody.knowledge_scope
├── application/answer_service.py        resolves scopes once; composes curated + retrieved evidence
apps/automation/app/platform/db/models.py                                      CuratedKnowledgeEntry, ix_chunk_tags_gin, QueryTrace.allowed_knowledge_scopes column (§10.3, done)
apps/automation/alembic/versions/0007_knowledge_scope.py (§10.3, done)
apps/automation/app/platform/db/tests/test_migration_0007_knowledge_scope.py (§10.3, done)   real alembic head/-1/head round trip
apps/automation/scripts/seed_curated_knowledge.py (new)
packages/contracts/src/index.ts                                                ChatRequest.knowledgeScope
apps/web/src/features/chat/server/route-handlers.ts                            forwards knowledgeScope
apps/web/src/features/chat/ui/chat-session-provider.tsx                        widget-level knowledgeScope config
```

## Not this file

Label-driven tag derivation and the ingestion-side corpus migration — see
[`../ingestion/phase-10.md`](../ingestion/phase-10.md).
