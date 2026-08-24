# Phase 0 — Design docs & ADRs (retrieval/answer side)

**Status:** ✅ done. Documentation only, no code (`docs/rag/PLAN.md` lines 1839–1868, "gate: user
reviews `DESIGN.md` before Phase 3.5 code begins").

## What happened

Before any Phase 3.5+ code was written, this phase locked the two decisions that govern the entire
read/answer path:

- **`docs/rag/DESIGN.md`** — the design of record. Section 2 (target pipeline), section 5 (the
  accuracy stack: rerank, parent expansion, citations, refusal, CRAG), and section 6 (eval + tracing
  scoreboard) are the retrieval-relevant sections.
- **`docs/adr/0005-Reranking-And-Answer-Pipeline.md`** — the ADR that governs everything documented in
  [phase-3.5.md](./phase-3.5.md) and [phase-4.md](./phase-4.md). Its ten numbered decisions, in brief:
  1. Cross-encoder rerankers only (Cohere `rerank-v3.5`), never a general chat model asked to reorder.
  2. The reranker client mirrors the embeddings-client abstraction exactly (`Reranker` protocol,
     `CohereReranker` / `FakeReranker`, same timeout/retry/breaker/abuse-cap discipline).
  3. Rerank runs **after** the permission filter, before the top-`k` slice — a document the principal
     can't see is never scored.
  4. Tests force `reranker_provider=fake` so CI stays deterministic even with a live Cohere key in
     `.env`.
  5. The answer runtime (`rag_agent`) is a **fixed function pipeline, not an agent loop** — every
     stage is deterministic and unit-testable, latency is bounded.
  6. **Forced citations** — uncited claims are stripped in code, not merely discouraged by prompt.
  7. **Refusal threshold** — below `refusal_min_rerank_score`, refuse rather than hallucinate.
  8. **One CRAG retry** — a p95 latency cap on corrective retrieval.
  9. Two enforced security layers on the answer path: source-level RLS (ADR-0004) and page-level
     principal ACL, both always apply.
  10. `POST /chat` is both an HTTP and an LLM surface — the full `securing-http-and-llm-endpoints`
      control set applies (see [phase-4.md](./phase-4.md) §4.4 and [phase-4.6.md](./phase-4.6.md)).

ADR-0004 (multi-source provider tagging + RLS) is the companion decision that governs the
storage/isolation layer shared by both paths — its writer/ingestion half is documented in
[`../ingestion/phase-0.md`](../ingestion/phase-0.md); its reader-side enforcement (the `rag_reader`
role, default-deny GUC) is documented in [phase-3.5.md](./phase-3.5.md).

## Files & folders used

- `docs/rag/DESIGN.md` — design of record.
- `docs/adr/0005-Reranking-And-Answer-Pipeline.md` — reranking + answer-pipeline ADR.
- `docs/adr/0004-Multi-Source-Provider-Tagging-And-RLS.md` — isolation model ADR (shared with
  ingestion).

No application code changed in this phase.
