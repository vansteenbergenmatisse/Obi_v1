This file documents every feature in apps/automation/app/features. Each block below maps to one folder in that directory. A feature without a block here is undocumented and incomplete.

## confluence_sync

- **What it does:** Keeps the local knowledge store in sync with Confluence — ingests webhook events, enqueues idempotent version-guarded jobs, runs them on a crash-safe worker, and reconciles drift the webhook stream missed. Reconciliation scope narrows to the `source_scope` table (PLAN 3.5.6): a `space` root reproduces whole-space sync, a `page` root restricts + tags a page-subtree, and removing/deactivating a root purges what it used to cover.
- **Path / owner:** apps/automation/app/features/confluence_sync — owned by the `automation` application.
- **Language / framework / runtime:** Python 3.12; FastAPI (webhook router), SQLAlchemy 2, APScheduler; runs inside the automation service.
- **Deployment unit:** ships in the single `apps/automation` deployment (infra/automation).
- **Public surface (`__init__.py`, enforced):** `router` (POST /confluence/events), `run_reconciliation`, `drain`, `reap`, `KIND_LIGHTWEIGHT`, `KIND_COMPLETE`, `resolve_scope_roots`, `resolve_space_scope`, `ScopeResolution`, `ROOT_TYPE_SPACE`, `ROOT_TYPE_PAGE`. Everything else (event_service, sync_service handlers, per-job worker internals, reconcile_space) stays internal and is deep-imported only within the feature. Consumers import via `app.features.confluence_sync`; the boundary is checked by `tools/check_feature_boundaries.py` (ADR-0003). (`SlidingWindowRateLimiter` moved to `app.shared.rate_limiter` in PLAN 4.4 — the chat endpoint became its second consumer, and it has no confluence-specific behavior.)
- **Allowed importers:** `app/main.py` (wiring). It imports downward into `ingestion` (shared domain) and `platform`; nothing imports back into it except `main`.
- **Contracts / external systems:** consumes the Confluence event-envelope contract (packages/contracts); calls Confluence Cloud REST v2 (`HttpConfluenceClient`) and receives Confluence webhooks. Offline runs/tests use `FixtureConfluenceGateway`.
- **Database tables owned:** `event_ledger`, `job`, `reconciliation_run`, `source_scope`. (It drives, but does not own, the `page_source`/`document`/`document_version`/`chunk`/`page_restriction` tables owned by `ingestion`.) `source_scope` rows are seeded one-off via `scripts/seed_source_scope.py` — no CRUD API yet. `handle_sync_page` (PLAN 4.3) writes `page_restriction` directly — a full delete+insert replace of a page's principal list whenever its access-scope hash changes (or on first index), same convention as the existing direct `page_source`/`chunk` metadata writes in `_apply_metadata_only`.
- **Untrusted input validation:** `server/webhook.py` (HMAC signature, body-size cap, rate limit) and `schemas/events.py::parse_webhook_payload` → Pydantic `EventEnvelope`; unsubscribed event types dropped in `event_service`.
- **Shared components used:** None (backend feature).
- **Tests / risky paths:** `app/features/confluence_sync/tests/` — first-index, atomic re-index (exactly one active version), version-guard drops stale deliveries, permission change = metadata-only (no re-embed) + persists the real principal list to `page_restriction` (full replace, not append; clearing restrictions leaves zero rows), delete/deactivate, job queue (SKIP LOCKED, backoff → dead-letter, lease reaping), rollback, event dedup, webhook security (auth/size/rate/dedup/self-event), and source_scope (pure resolver unit tests + DB-backed subtree-narrowing/tag-propagation/purge-on-removal).
- **Run / test:** `make test` or `pytest app/features/confluence_sync/tests`; serve with `uvicorn app.main:app` (set `enable_background_jobs=true` to run the scheduler + in-process worker).

## ingestion

- **What it does:** Turns fetched Confluence content into immutable, atomically-activated indexed versions. Phase 3 builds token-aware parent/child chunks, writes contextual `retrieval_content` (Anthropic contextual retrieval, with a deterministic metadata fallback), embeds children (dense `embedding` + keyword `tsv`), reuses embeddings for unchanged chunks via a 3-pass diff, and routes any embedding-model/dim/schema change through a full re-embed release gate. Change detection/classification, staging → activation → rollback carry over from Phase 2.
- **Path / owner:** apps/automation/app/features/ingestion — owned by the `automation` application.
- **Language / framework / runtime:** Python 3.12; SQLAlchemy 2; runs inside the automation service.
- **Deployment unit:** ships in `apps/automation`.
- **Public surface (`__init__.py`, enforced):** `build_ingestion_services`, `stage_and_activate`, `deactivate_page`, `rollback_to`, `reusable_active_children`, `get_local_state`, `classify`, `decide_body_fetch`, `map_page_status`, `ChangeClass`, `PageHashes`, `TargetVersions`, and the `normalization` module (re-exported whole — call sites use `norm.Block` / `norm.normalize_body`, ADR-0003 D4). Tokenization, chunking, chunk_diff, and the contextualizer stay internal. Consumers import via `app.features.ingestion`.
- **Allowed importers:** `confluence_sync` (sync/reconciliation) and `retrieval` (reads the chunk index).
- **Contracts / external systems:** OpenAI embeddings and Anthropic messages (contextualization) via `platform.clients.{embeddings_client,anthropic_client}` — both LLM-CALL surfaces (see `security_baseline` below). Optional attachment parsers (pypdf/python-docx/openpyxl) and `tiktoken` are lazily imported and degrade gracefully when absent.
- **Database tables owned:** `page_source`, `document`, `document_version`, `chunk`, `page_restriction` (ORM in `app/platform/db/models.py`). `chunk.embedding` is `vector(EMBEDDING_DIM)`; its HNSW index casts to `halfvec` for >2000-dim models (pgvector's `vector` HNSW cap is 2000 — see ADR-0002). `page_restriction` (PLAN 4.3) is the persisted per-page principal ACL, FK'd to `page_source.page_id` ON DELETE CASCADE — presence of a row restricts, absence means unrestricted; written directly by `confluence_sync`'s `sync_service.py` (same pattern as `page_source`/`chunk`: this feature owns the table, `confluence_sync` drives writes to it).
- **Untrusted input validation:** None at this layer — inputs arrive already validated at the `confluence_sync` boundary; attachment bytes are parsed defensively (never raise).
- **Shared components used:** None.
- **Tests / risky paths:** `app/features/ingestion/tests/` — token-window invariants, parent/child sizing + stable-key stability, 3-pass diff reuse/re-embed/delete sets, embedding-reuse counts (spy embedder), contextualizer fallback vs LLM path, attachment extraction + OCR gating. DB-level embedding/tsv population, atomic version swap, and the re-embed release gate are covered by `confluence_sync/tests/test_ingestion_pipeline.py`.
- **Run / test:** `pytest app/features/ingestion/tests` (plus the confluence_sync suite, which drives this feature end-to-end).

### security_baseline (ingestion LLM-CALL surfaces)

```yaml
security_baseline:
  applies: true
  surfaces:
    - id: openai.embeddings.create (chunk embedding, ingestion worker)
      tier: LLM-CALL
      controls:
        C1_auth:        { status: covered, mechanism: "OPENAI_API_KEY; offline dev falls back to a Fake provider" }
        C2_rate_limit:  { status: covered, mechanism: "fixed batch size (embedding_max_batch), single-flight per job" }
        C3_input:       { status: covered, mechanism: "first-party corpus text; per-call abuse cap embedding_max_texts_per_call" }
        C4_timeout:     { status: covered, mechanism: "embedding_timeout_seconds, bounded retry w/ backoff, consecutive-failure breaker" }
        C5_output_rate: { status: opted_out, justification: "response is fixed-width vectors, not a stream" }
        C6_redaction:   { status: opted_out, justification: "input is the first-party wiki corpus being indexed, not third-party user PII" }
        C9_audit:       { status: covered, mechanism: "structured job logs (job_id, page_id, counts) via worker" }
        C10_abuse:      { status: covered, mechanism: "batch cap + embedding_max_texts_per_call + breaker; runs only in the background worker" }
    - id: anthropic.messages.create (chunk contextualization, ingestion worker)
      tier: LLM-CALL
      controls:
        C1_auth:        { status: covered, mechanism: "ANTHROPIC_API_KEY; absent/ disabled -> deterministic metadata-only prefix" }
        C2_rate_limit:  { status: covered, mechanism: "runs only for new/edited children; document context is prompt-cached (billed once/page)" }
        C3_input:       { status: covered, mechanism: "first-party content; document context capped by contextualization_max_doc_chars" }
        C4_timeout:     { status: covered, mechanism: "contextualization_timeout_seconds, bounded retry; failure degrades to metadata prefix (never blocks ingestion)" }
        C5_output_rate: { status: covered, mechanism: "max_tokens=128 per chunk context" }
        C6_redaction:   { status: opted_out, justification: "first-party corpus; no third-party user PII on this path" }
        C9_audit:       { status: covered, mechanism: "structured warn logs on contextualization failure" }
        C10_abuse:      { status: covered, mechanism: "reuse skips unchanged chunks; doc-char cap; disableable via contextualization_enabled" }
```

## retrieval

- **What it does:** Permission-aware hybrid retrieval over the active chunk index — concurrent dense (pgvector, halfvec-aware) and keyword (tsvector, OR-of-terms ranked by ts_rank) candidate search, fused with Reciprocal Rank Fusion, filtered by an access-scope permission policy, returning relevance-ranked page ids. Status is enforced by the index (only current pages have active chunks); permission is enforced at query time — source-level RLS (Phase 3.5) plus, as of PLAN 4.3, a persisted page-level principal ACL, both layered.
- **Path / owner:** apps/automation/app/features/retrieval — owned by the `automation` application.
- **Language / framework / runtime:** Python 3.12; SQLAlchemy 2 (raw SQL for the vector/tsvector operators); runs inside the automation service.
- **Deployment unit:** ships in `apps/automation`.
- **Public surface (`__init__.py`, enforced):** `HybridRetriever` (the entry point; `retrieve()` for the eval-harness page-id shape, `retrieve_with_context()` for Phase 4.2's chunk id + score + title/url shape, `fetch_parent_texts()` for parent-context expansion), `PrincipalPermissionPolicy` (the pure decision function; its constructor-injected instance now only supplies `space_id()` parsing — PLAN 4.3 builds a fresh, DB-backed instance per search for the `allowed()` check), the `RetrievedHit`/`RetrievalResult` DTOs, and `update_query_trace_answer`/`update_query_trace_feedback` (the Phase 4/4.4 `query_trace` UPDATE writers). Fusion and the low-level search functions stay internal. Consumers import via `app.features.retrieval`.
- **Allowed importers:** the `rag_agent` answer workflow (Phase 4.2) and the evaluation harness. Imports downward into `ingestion` data (the `chunk`/`page_source`/`page_restriction` tables) and `platform`.
- **Contracts / external systems:** the embedding provider (query embedding) via `platform.clients.embeddings_client`.
- **Database tables owned:** none — reads `chunk`/`page_source`/`page_restriction` (owned by `ingestion`; PLAN 4.3's `search_repo.fetch_page_scopes` queries the latter two, scoped to the current candidate page set, never the whole corpus); owns the retrieval-write and answer-update paths on `query_trace` (schema owned by the 3.5.4 migration).
- **Untrusted input validation:** query text is passed to Postgres text-search via bound parameters (Postgres lexemizes it; no string interpolation of user input into SQL).
- **Shared components used:** None.
- **Tests / risky paths:** `app/features/retrieval/tests/` (RRF fusion, permission policy) and `confluence_sync/tests/test_retrieval_eval.py` — the end-to-end eval over the indexed fixture corpus: retrieval_smoke recall@5 held at 1.000 while mrr 0.75→1.00 and ndcg 0.82→1.00 beat baseline, permission proves no cross-scope leak with authorized access preserved, (PLAN 4.2) `retrieve_with_context`/`fetch_parent_texts`/the trace answer+feedback UPDATE writers are exercised against the real indexed corpus, and (PLAN 4.3) `test_permission_enforcement_is_db_backed_not_fixture_fed` proves enforcement holds even with an intentionally empty injected policy — the acceptance proof that the ACL is truly DB-backed, not fixture-fed.
- **Run / test:** `pytest app/features/retrieval/tests app/features/confluence_sync/tests/test_retrieval_eval.py`.

## evaluation

- **What it does:** DB-free RAG evaluation harness — retrieval/latency metrics, a fixture-backed dataset, a runner, and a baseline report generator.
- **Path / owner:** apps/automation/app/features/evaluation — owned by the `automation` application.
- **Language / framework / runtime:** Python 3.12; pure Python (no DB, no network); runs inside the automation service or standalone.
- **Deployment unit:** ships in `apps/automation` (dev/CI utility; not on the request path).
- **Public surface (`__init__.py`, enforced):** `evaluate`, `load_dataset`, `load_corpus_loader`, `datasets_dir`, `confluence_fixtures_dir`, `RankFn`, and the `EvalCase` / `EvalDataset` / `EvalResult` / `EvalReport` types. `run_baseline` remains a runnable module (`python -m app.features.evaluation.run_baseline`). Consumers import via `app.features.evaluation`.
- **Allowed importers:** standalone tooling; no runtime feature depends on it.
- **Contracts / external systems:** None; reads the Confluence fixture corpus under `tests/fixtures/confluence`.
- **Database tables owned:** None.
- **Untrusted input validation:** None (operates on trusted fixtures).
- **Shared components used:** None.
- **Tests / risky paths:** `app/features/evaluation/tests/` — metrics correctness, fixture loader, baseline runner.
- **Run / test:** `make eval` or `python -m app.features.evaluation.run_baseline`; `pytest app/features/evaluation/tests`.

## rag_agent

- **What it does:** The grounded answer runtime over the Phase 3.5 retrieval spine (ADR-0005), now wired to a real HTTP surface. A fixed, testable workflow — conversational rewrite → RLS-scoped retrieve → RRF → cross-encoder rerank → **one CRAG corrective retry if weak** → refusal threshold → parent-context expansion → grounded generation with forced numbered citations → citation enforcement → SSE — **not** an agent loop. **Status: Phase 4.2 + 4.3 + 4.4 + 4.5 shipped; Phase 5 caching shipped.** `AnswerService` implements the full pipeline and is unit-tested with fake LLM/retriever collaborators plus DB-integration-tested against the real fixture corpus. `POST /chat` (SSE: `start`/`token`/`citations`/`done`/`error`) and `PATCH /chat/{trace_id}/feedback` are live in `app/main.py`, with the full `securing-http-and-llm-endpoints` control set applied (see `server/router.py`'s `security_baseline` docstring) — PII redaction on every rewrite/generation call, a circuit breaker + abuse cap added to `AnthropicMessagesClient`, and the webhook's `SlidingWindowRateLimiter` promoted to `app.shared.rate_limiter` as its second consumer. **PLAN 5:** `main.create_app` now wraps `AnswerService` in `CachingAnswerService` (`application/answer_cache.py`) — an in-process exact-match TTL cache keyed on `(full history, principal)` that skips retrieval + generation entirely on a byte-for-byte repeat; the pre-existing `Idempotency-Key` replay cache in `server/router.py` was refactored onto the same extracted `app.shared.ttl_cache.TTLCache` primitive. Semantic caching is explicitly not built — see `answer_cache.py`'s docstring for the accuracy-risk rationale.
- **Path / owner:** apps/automation/app/features/rag_agent — owned by the `automation` application.
- **Language / framework / runtime:** Python 3.12; FastAPI (chat router), Pydantic v2 (DTOs), pure-Python domain (prompt assembly, refusal, citation enforcement, PII redaction), SQLAlchemy 2 only indirectly via `retrieval`. Runs inside the automation service.
- **Deployment unit:** ships in `apps/automation`.
- **Public surface (`__init__.py`, enforced):** the answer contract DTOs (`Answer`, `Citation`, `ChatMessage`); `AnswerService` (the Phase 4.2 orchestrator) and the `AnswerProvider` protocol it satisfies; `CachingAnswerService` (Phase 5, wraps any `AnswerProvider`); the `QueryRewriter`/`AnswerGenerator` collaborator protocols and their `AnthropicQueryRewriter`/`AnthropicAnswerGenerator` implementations; and, as of Phase 4.4, `router` (the `POST /chat` + `PATCH /chat/{trace_id}/feedback` APIRouter `app.main` includes). Prompt assembly / refusal / citation / PII-redaction domain logic and the router's dependency helpers stay internal. Consumers import via `app.features.rag_agent`.
- **Allowed importers:** `app/main.py` (builds the `AnswerService` singleton via `build_answer_service`, wraps it in `CachingAnswerService`, and includes `router`). Imports downward into `retrieval` (`HybridRetriever.retrieve_with_context`/`fetch_parent_texts`, `update_query_trace_answer`/`update_query_trace_feedback`), `platform` (`AnthropicMessagesClient`), and `shared` (`rate_limiter`, `ttl_cache`); nothing imports back into it except `main` and (for one DB-integration test file only, importing at this feature's public root) `confluence_sync/tests`.
- **Contracts / external systems:** Anthropic messages (query rewrite via `routing_model`, grounded generation via `answer_model`) through `AnthropicQueryRewriter`/`AnthropicAnswerGenerator` — an LLM-CALL surface using `AnthropicMessagesClient`'s timeout/retry/**breaker** discipline (breaker + abuse cap added PLAN 4.4); the rewriter fails open to the verbatim query on an `AnthropicError`, the generator lets it propagate (surfaced as an SSE `error` event, not a 5xx, since the stream has already committed to a 200 response by then). `POST /chat` + `PATCH /chat/{trace_id}/feedback` are the HTTP surface, secured per the `security_baseline` in `server/router.py`. The web chat contract (`packages/contracts`) still needs extending for this shape (Phase 4.5): the caller sends full turn `history` per request (no server-side conversation store), and `ChatDoneEvent` needs a `traceId` + `refused` field this endpoint already emits.
- **Database tables owned:** none — reads the `chunk` index (owned by `ingestion`) via `retrieval`, and updates `query_trace` (owned by `retrieval`) with the rewritten query, grounded answer, citations, and (Phase 4.4) feedback once generation/feedback complete.
- **Untrusted input validation:** `server/router.py` — Pydantic body (`extra=forbid`), history non-empty and ends on a user turn, per-turn and per-history length caps, shared-secret auth, sliding-window rate limiting. `AnswerService.answer` also validates its own precondition (raises `ValueError` if `history` is empty or does not end on a user turn) as a second, defense-in-depth check. `enforce_citations` defensively strips any claim citing a page that was not retrieved; a generated answer with zero surviving citations degrades to a refusal rather than returning an empty response.
- **Shared components used:** `app.shared.rate_limiter.SlidingWindowRateLimiter` (PLAN 4.4 — extracted from `confluence_sync`'s webhook once this feature became its second consumer); `app.shared.ttl_cache.TTLCache` (PLAN 5 — extracted from `server/router.py`'s `Idempotency-Key` cache once `answer_cache.py` became its second consumer).
- **Tests / risky paths:** `app/features/rag_agent/tests/` — refusal below/at/above threshold and the no-candidates case; citation enforcement; pure prompt assembly; PII redaction (`test_pii.py`); the Anthropic-backed collaborators redacting the outbound payload and the rewriter's fail-open policy (`test_llm_client.py`); `AnswerService` orchestration with fakes; `test_answer_cache.py` — cache hit/miss on identical vs. differing history/principal, TTL expiry, max-entries eviction, all against a fake `AnswerProvider` (call-count assertions, not just returned values). `app/shared/tests/test_ttl_cache.py` — the extracted primitive's expiry/eviction behavior directly. `confluence_sync/tests/test_answer_workflow.py` — the same service end-to-end against the real indexed corpus. `confluence_sync/tests/test_chat_endpoint.py` — the HTTP surface end-to-end: auth (missing/wrong/unconfigured key), rate limiting, input validation (history length/turn-role/message length), the real SSE stream (start→token→citations→done against the real corpus, reassembled tokens matching the done answer), refusal surfacing `refused: true`, `Idempotency-Key` replay skipping a second pipeline run, the feedback PATCH persisting to `query_trace`, the PLAN 5 answer cache replaying without rerunning retrieval and never crossing a principal boundary, and `main.create_app` actually wiring `CachingAnswerService` by default. `platform/clients/tests/test_anthropic_client.py` — the breaker/abuse-cap behavior.
- **Run / test:** `pytest app/features/rag_agent/tests app/shared/tests/test_ttl_cache.py app/features/confluence_sync/tests/test_answer_workflow.py app/features/confluence_sync/tests/test_chat_endpoint.py app/platform/clients/tests/test_anthropic_client.py`.

### security_baseline (PLAN 4.4 — see `server/router.py` for the full per-control mechanism text)

```yaml
security_baseline:
  applies: true
  surfaces:
    - id: POST /chat
      tier: STATE-MUTATING + LLM-CALL
      controls:
        C1_auth:        { status: covered, mechanism: "shared-secret chat_api_key via Authorization: Bearer, constant-time compare, fail-closed (503) when unset" }
        C2_rate_limit:  { status: covered, mechanism: "SlidingWindowRateLimiter keyed by client IP only (never the caller-reported principal — PLAN 4.6.4 fix), chat_rate_limit_per_minute, bounded to chat_rate_limiter_max_tracked_keys tracked IPs" }
        C3_input:       { status: covered, mechanism: "Pydantic body (extra=forbid); history non-empty + ends on a user turn; chat_max_history_turns / chat_max_message_chars; all-digit principal rejected (PLAN 5.3 red-team finding)" }
        C4_timeout:     { status: covered, mechanism: "AnthropicMessagesClient timeout/retry/breaker (answer_timeout_seconds/max_retries/breaker_threshold); retrieval's embedder/reranker already covered (3.5.2/3)" }
        C5_output_rate: { status: covered, mechanism: "generation token cap + chat_output_max_answer_chars defensive re-cap + paced SSE chunks (chat_token_chunk_chars/chat_stream_interval_ms)" }
        C6_redaction:   { status: covered, mechanism: "redact_pii scrubs the assembled prompt before every rewrite/generation call" }
        C7_idempotency: { status: covered, mechanism: "optional Idempotency-Key header hashed with (principal, history) into an in-process TTL cache bounded by chat_idempotency_cache_max_entries (PLAN 4.6.3/4.6.4), replays the cached Answer" }
        C8_concurrency: { status: opted_out, justification: "each request creates its own query_trace row; no shared-resource read-modify-write" }
        C9_audit:       { status: covered, mechanism: "structured chat_request/chat_request_replayed log lines (conversation id, trace id, refused, refusal reason, citation count, latency) — never the raw message or answer text" }
        C10_abuse:      { status: covered, mechanism: "rate limit + history/message-length caps + AnthropicMessagesClient abuse cap (answer_max_input_chars) + breaker" }
    - id: PATCH /chat/{trace_id}/feedback
      tier: STATE-MUTATING
      controls:
        C1_auth:        { status: covered, mechanism: "same shared-secret check as POST /chat" }
        C2_rate_limit:  { status: covered, mechanism: "same limiter/key as POST /chat" }
        C3_input:       { status: covered, mechanism: "feedback constrained to Literal[-1, 1]" }
        C4_timeout:     { status: covered, mechanism: "one bound UPDATE statement, no fan-out" }
        C7_idempotency: { status: covered, mechanism: "UPDATE is naturally idempotent — replaying the same value produces the same row state" }
        C8_concurrency: { status: opted_out, justification: "single UPDATE by primary key; last-write-wins is correct for a thumbs up/down toggle" }
        C9_audit:       { status: covered, mechanism: "structured chat_feedback log line (trace id, value)" }
        C10_abuse:      { status: covered, mechanism: "same rate limiter as POST /chat" }
```

Known, documented limitation (not a bug): there is no end-user login system yet, so `principal` is
caller-self-reported, trusted only as far as C1 trusts the calling web proxy. Per ADR-0004's
default-deny model, an absent/unverified principal can only ever see *unrestricted* pages — never a
blanket-access bypass. Real per-user identity is a later phase; the endpoint is already safe in its
absence.

**PLAN 5.3 red-team finding, fixed.** The claim above was not quite true before 5.3: an all-digit
`principal` is read by `PrincipalPermissionPolicy.allowed` as **space-level trust**, granting every
page in that space regardless of `page_restriction` — a real feature, needed by the eval harness's
numeric space-scoping, but never meant to be reachable from an untrusted HTTP `principal`. Closed at
the boundary with a `ChatRequestBody` validator rejecting all-digit `principal` values (422), not by
changing the shared domain policy. See `server/router.py`'s docstring and PLAN.md §0's 5.3 entry.
