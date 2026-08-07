# 0005 — Reranking and the Answer Pipeline

Status: Accepted
Date: 2026-08-07
Governs: apps/automation (retrieval, rag_agent, platform/clients), and the answer HTTP surface

## Context

Reranking is the user's called-out accuracy priority and is essential for Confluence docs, yet no reranker
exists today: the `reranker_provider` / `reranker_api_key` / `reranker_local_model` settings
(`settings.py:62-65`, commented "used from Phase 4") are dead — there is no client. Beyond reranking, the
system has no answer runtime at all: no query rewrite, generation, citations, refusal, or corrective
retrieval, and `POST /chat` is absent (the web route is a 501 stub). This ADR fixes how retrieved
candidates are reranked and how a grounded answer is produced. The source-isolation model is ADR-0004.

## Decision

1. **Cross-encoder rerankers only — no general-LLM rerankers.** Reranking uses a purpose-built cross-encoder
   (Cohere `rerank-v3.5`, or a local cross-encoder), never a general chat model asked to reorder. Cross-
   encoders are cheaper per candidate, deterministic enough to eval, and built for the query-document
   relevance task.

2. **The reranker client mirrors the embeddings abstraction exactly.** New
   `app/platform/clients/reranker_client.py`: `RerankError(RuntimeError)`; a `@runtime_checkable`
   `Reranker` Protocol (`model: str`; `rerank(query, docs: Sequence[tuple[int, str]], top_k) ->
   list[tuple[int, float]]`, `(page_id, score)` sorted desc); `CohereReranker` (raw `httpx`,
   `POST https://api.cohere.com/v2/rerank`) reusing the exact timeout / bounded retry+backoff / circuit
   breaker / abuse-cap discipline of `_HttpEmbeddingProvider` and `anthropic_client`; `FakeReranker`
   (identity — input order, scores by descending input rank; deterministic, for tests and offline dev);
   and `build_reranker(settings, client=None)` with **offline fallback**: empty key **or** provider ∈
   {`""`, `fake`} **or** offline env → `FakeReranker`. Exported from `platform/clients/__init__.py`; the
   retriever imports it from that root, never a deep path.

3. **Rerank runs after the permission filter, before the top-`k` slice** (`retriever.py`). Never rerank a
   document the principal cannot see. `candidate_k` rises 40→75 (`rerank_candidate_k`); the top
   `rerank_depth` allowed pages are reranked to `rerank_top_k`. Because the retriever holds page ids only,
   a `fetch_rerank_texts` refactor in `search_repo.py` (DISTINCT ON `page_id`, `left(title || ' ' ||
   retrieval_content, 4000)` over active child chunks, subject to the same `_base_filters` + source scope)
   supplies the text; this refactor precedes the wiring. The reranker is injected via the constructor, like
   `embedder` and `policy`.

4. **Tests force `reranker_provider=fake`.** `.env` carries a live Cohere key with `env=local`; the offline
   fallback only fires on an *empty* key, so the hermetic settings fixture must force `fake` or CI would hit
   Cohere non-deterministically.

5. **The answer runtime is a fixed workflow, not an agent loop.** A new `rag_agent` feature (own public
   root, own `FEATURES.md`) runs a fixed ordered pipeline, each stage a plain function:
   (1) conversational query rewrite (one cheap `routing_model` call, `rewrite_enabled`, store
   `rewritten_query`); (2) RLS-scoped retrieve → RRF → rerank (reuse `HybridRetriever` on the reader
   engine); (3) parent-context expansion (join `parent_chunk_id`, feed the *parent* text to the generator);
   (4) grounded generation with forced numbered citations; (5) refusal threshold; (6) at most one CRAG
   corrective retry.

6. **Forced citations.** Every claim cites a retrieved chunk; **uncited claims are stripped** before the
   answer is returned. Groundedness is enforced in code, not merely prompted.

7. **Refusal threshold.** If the top rerank score < `refusal_min_rerank_score`, the runtime refuses ("not
   in the docs") and routes to a human instead of hallucinating. The threshold is tuned from the Phase 3.5.5
   rerank-lift numbers, not guessed.

8. **One CRAG retry.** On a weak result, exactly one corrective retrieval (`crag_max_retries=1`). The cap is
   a p95 protection: unbounded corrective loops trade latency for marginal recall.

9. **Two enforced security layers on the answer path.** Source-level RLS (ADR-0004) and page-level principal
   ACL both apply. Phase 4 replaces the fixture-fed `PrincipalPermissionPolicy` with persisted, queryable
   principal lists enforced **pre-search**, alongside RLS.

10. **The chat surface is both an HTTP and an LLM surface.** `POST /chat` (SSE: `start`/`token`/`citations`/
    `done`, reader engine) and `PATCH /chat/{trace_id}/feedback` (writer engine) apply the full
    `securing-http-and-llm-endpoints` control set: auth, rate limit, input validation,
    timeout/retry/breaker, output rate limit, PII redaction, idempotency, audit logging, cost/abuse caps.
    `POST /chat` must not be wired before ADR-0004's reader engine + RLS exist.

## Reason

A cross-encoder reranker is the highest-leverage accuracy layer for terse Confluence snippets, and mirroring
the embeddings client keeps its failure discipline (timeout, retry, breaker, abuse cap) identical to the
rest of the platform. A fixed workflow — rather than an agent loop — is testable stage by stage, bounds
latency deterministically, and makes refusal and citation enforcement auditable. Enforcing groundedness in
code (strip uncited claims, refuse below threshold) is what turns retrieval quality into answer
trustworthiness.

## Alternatives considered

- **General-LLM reranking.** Rejected: costlier per candidate, less deterministic, and not what the model is
  optimized for. Cross-encoder only.
- **An agentic RAG loop (Self-RAG / tool-calling planner).** Rejected: unbounded latency, harder to eval,
  and unnecessary for a Confluence Q&A corpus. A fixed pipeline with one CRAG retry captures the corrective
  benefit within a p95 budget.
- **Config-flip the dead reranker settings without the text refactor.** Rejected: the retriever has no text
  to rerank — it holds page ids. `fetch_rerank_texts` is a prerequisite, not optional.
- **Prompt-only groundedness (no code enforcement).** Rejected: prompts drift; stripping uncited claims and
  a hard refusal threshold enforce the contract.

## Consequences

- The retriever gains a constructor dependency (`reranker`) and a post-filter rerank stage; `candidate_k`
  rises to 75, so dense/keyword fetch a wider candidate set.
- Offline and CI runs are deterministic via `FakeReranker`; a live Cohere key changes only the production
  ranking, not the harness.
- `refusal_min_rerank_score` is a tuned constant owned by the eval numbers; changing the reranker model
  requires re-tuning it.
- The answer runtime depends on ADR-0004 being live (reader engine + RLS) before `POST /chat` is wired.

## Paths governed

`apps/automation/app/platform/clients/reranker_client.py` (+ `clients/__init__.py`),
`apps/automation/app/features/retrieval/**`, `apps/automation/app/features/rag_agent/**` (Phase 4),
`apps/automation/app/main.py` (`POST /chat`, `PATCH /chat/{id}/feedback`),
`apps/automation/app/platform/config/settings.py`, and the web chat surface
(`apps/web/src/features/chat/**`, `apps/web/src/app/api/chat/route.ts`, `packages/contracts`).
