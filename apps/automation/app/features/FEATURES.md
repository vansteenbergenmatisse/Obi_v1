This file documents every feature in apps/automation/app/features. Each block below maps to one folder in that directory. A feature without a block here is undocumented and incomplete.

## confluence_sync

- **What it does:** Keeps the local knowledge store in sync with Confluence — ingests webhook events, enqueues idempotent version-guarded jobs, runs them on a crash-safe worker, and reconciles drift the webhook stream missed.
- **Path / owner:** apps/automation/app/features/confluence_sync — owned by the `automation` application.
- **Language / framework / runtime:** Python 3.12; FastAPI (webhook router), SQLAlchemy 2, APScheduler; runs inside the automation service.
- **Deployment unit:** ships in the single `apps/automation` deployment (infra/automation).
- **Public surface (`__init__.py`, enforced):** `router` (POST /confluence/events), `run_reconciliation`, `drain`, `reap`, `KIND_LIGHTWEIGHT`, `KIND_COMPLETE`, `SlidingWindowRateLimiter`. Everything else (event_service, sync_service handlers, per-job worker internals, reconcile_space) stays internal and is deep-imported only within the feature. Consumers import via `app.features.confluence_sync`; the boundary is checked by `tools/check_feature_boundaries.py` (ADR-0003).
- **Allowed importers:** `app/main.py` (wiring). It imports downward into `ingestion` (shared domain) and `platform`; nothing imports back into it except `main`.
- **Contracts / external systems:** consumes the Confluence event-envelope contract (packages/contracts); calls Confluence Cloud REST v2 (`HttpConfluenceClient`) and receives Confluence webhooks. Offline runs/tests use `FixtureConfluenceGateway`.
- **Database tables owned:** `event_ledger`, `job`, `reconciliation_run`. (It drives, but does not own, the `page_source`/`document`/`document_version`/`chunk` tables owned by `ingestion`.)
- **Untrusted input validation:** `server/webhook.py` (HMAC signature, body-size cap, rate limit) and `schemas/events.py::parse_webhook_payload` → Pydantic `EventEnvelope`; unsubscribed event types dropped in `event_service`.
- **Shared components used:** None (backend feature).
- **Tests / risky paths:** `app/features/confluence_sync/tests/` — first-index, atomic re-index (exactly one active version), version-guard drops stale deliveries, permission change = metadata-only (no re-embed), delete/deactivate, job queue (SKIP LOCKED, backoff → dead-letter, lease reaping), rollback, event dedup, and webhook security (auth/size/rate/dedup/self-event).
- **Run / test:** `make test` or `pytest app/features/confluence_sync/tests`; serve with `uvicorn app.main:app` (set `enable_background_jobs=true` to run the scheduler + in-process worker).

## ingestion

- **What it does:** Turns fetched Confluence content into immutable, atomically-activated indexed versions. Phase 3 builds token-aware parent/child chunks, writes contextual `retrieval_content` (Anthropic contextual retrieval, with a deterministic metadata fallback), embeds children (dense `embedding` + keyword `tsv`), reuses embeddings for unchanged chunks via a 3-pass diff, and routes any embedding-model/dim/schema change through a full re-embed release gate. Change detection/classification, staging → activation → rollback carry over from Phase 2.
- **Path / owner:** apps/automation/app/features/ingestion — owned by the `automation` application.
- **Language / framework / runtime:** Python 3.12; SQLAlchemy 2; runs inside the automation service.
- **Deployment unit:** ships in `apps/automation`.
- **Public surface (`__init__.py`, enforced):** `build_ingestion_services`, `stage_and_activate`, `deactivate_page`, `rollback_to`, `reusable_active_children`, `get_local_state`, `classify`, `decide_body_fetch`, `map_page_status`, `ChangeClass`, `PageHashes`, `TargetVersions`, and the `normalization` module (re-exported whole — call sites use `norm.Block` / `norm.normalize_body`, ADR-0003 D4). Tokenization, chunking, chunk_diff, and the contextualizer stay internal. Consumers import via `app.features.ingestion`.
- **Allowed importers:** `confluence_sync` (sync/reconciliation) and `retrieval` (reads the chunk index).
- **Contracts / external systems:** OpenAI embeddings and Anthropic messages (contextualization) via `platform.clients.{embeddings_client,anthropic_client}` — both LLM-CALL surfaces (see `security_baseline` below). Optional attachment parsers (pypdf/python-docx/openpyxl) and `tiktoken` are lazily imported and degrade gracefully when absent.
- **Database tables owned:** `page_source`, `document`, `document_version`, `chunk` (ORM in `app/platform/db/models.py`). `chunk.embedding` is `vector(EMBEDDING_DIM)`; its HNSW index casts to `halfvec` for >2000-dim models (pgvector's `vector` HNSW cap is 2000 — see ADR-0002).
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

- **What it does:** Permission-aware hybrid retrieval over the active chunk index — concurrent dense (pgvector, halfvec-aware) and keyword (tsvector, OR-of-terms ranked by ts_rank) candidate search, fused with Reciprocal Rank Fusion, filtered by an access-scope permission policy, returning relevance-ranked page ids. Status is enforced by the index (only current pages have active chunks); permission is enforced at query time.
- **Path / owner:** apps/automation/app/features/retrieval — owned by the `automation` application.
- **Language / framework / runtime:** Python 3.12; SQLAlchemy 2 (raw SQL for the vector/tsvector operators); runs inside the automation service.
- **Deployment unit:** ships in `apps/automation`.
- **Public surface (`__init__.py`, enforced):** `HybridRetriever` (the entry point) and `PrincipalPermissionPolicy` (the policy callers construct). Fusion and the low-level search functions stay internal until a real external consumer needs them. Consumers import via `app.features.retrieval`.
- **Allowed importers:** the RAG agent (Phase 4) and the evaluation harness. Imports downward into `ingestion` data (the `chunk` table) and `platform`.
- **Contracts / external systems:** the embedding provider (query embedding) via `platform.clients.embeddings_client`.
- **Database tables owned:** none — reads the `chunk` table owned by `ingestion`.
- **Untrusted input validation:** query text is passed to Postgres text-search via bound parameters (Postgres lexemizes it; no string interpolation of user input into SQL).
- **Shared components used:** None.
- **Tests / risky paths:** `app/features/retrieval/tests/` (RRF fusion, permission policy) and `confluence_sync/tests/test_retrieval_eval.py` — the end-to-end eval over the indexed fixture corpus: retrieval_smoke recall@5 held at 1.000 while mrr 0.75→1.00 and ndcg 0.82→1.00 beat baseline, and permission proves no cross-scope leak with authorized access preserved.
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

- **What it does:** The grounded answer runtime over the Phase 3.5 retrieval spine (ADR-0005). A fixed, testable workflow — conversational rewrite → RLS-scoped retrieve → RRF → cross-encoder rerank → parent-context expansion → grounded generation with forced numbered citations → refusal threshold → at most one CRAG retry → SSE — **not** an agent loop. **Status: Phase 4.1 scaffold** — the DTO contract plus the pure domain core (refusal decision, citation enforcement) with unit tests. The answer service, prompt assembly, principal-ACL store, and the `POST /chat` surface are Phase 4.2–4.4.
- **Path / owner:** apps/automation/app/features/rag_agent — owned by the `automation` application.
- **Language / framework / runtime:** Python 3.12; Pydantic v2 (DTOs), pure-Python domain; will use SQLAlchemy 2 + `platform.clients` (Anthropic, reranker) once the workflow lands. Runs inside the automation service.
- **Deployment unit:** ships in `apps/automation`.
- **Public surface (`__init__.py`, enforced):** the answer contract DTOs — `Answer`, `Citation`, `ChatMessage`. The answer service is added to this root in Phase 4.2 once its pipeline exists; refusal / citation domain logic stays internal (deep-imported within the feature only). Consumers import via `app.features.rag_agent`.
- **Allowed importers:** `app/main.py` (Phase 4.4 wiring of `POST /chat`). It will import downward into `retrieval` (reader engine, RLS scope) and `platform`; nothing imports back into it except `main`.
- **Contracts / external systems:** none yet. Planned (Phase 4.2/4.4): Anthropic messages (query rewrite + grounded generation) and the Cohere reranker via `platform.clients` — both LLM-CALL surfaces; `POST /chat` + `PATCH /chat/{trace_id}/feedback` are an HTTP surface. The full `securing-http-and-llm-endpoints` control set applies then (ADR-0005 §10); the chat contract will be published in `packages/contracts`.
- **Database tables owned:** none — reads the `chunk` index (owned by `ingestion`) via `retrieval`, and reads/updates `query_trace` (owned by `retrieval`) for answer + feedback fields.
- **Untrusted input validation:** none at this layer yet — the Phase 4.4 endpoint owns request validation, rate limiting, and PII redaction. The pure domain core operates on already-retrieved, trusted data; `enforce_citations` defensively strips any claim citing a page that was not retrieved.
- **Shared components used:** None (backend feature).
- **Tests / risky paths:** `app/features/rag_agent/tests/` — refusal below/at/above threshold and the no-candidates case; citation enforcement (keeps cited claims, strips uncited and hallucinated-source claims, drops invalid markers, dedupes used markers).
- **Run / test:** `pytest app/features/rag_agent/tests`.
