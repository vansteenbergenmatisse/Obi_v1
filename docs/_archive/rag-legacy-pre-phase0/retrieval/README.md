# Retrieval — the read/answer path, phase by phase

> Scope: the **read path** only — `app/features/retrieval/` (hybrid search: dense ∥ keyword → RRF →
> permission filter → rerank) and `app/features/rag_agent/` (the answer runtime + `POST /chat`), plus
> `app/features/evaluation/` where a phase added retrieval/answer-quality metrics. For the **write
> path** (Confluence sync, chunking, contextualization, versioning), see
> [`../ingestion/README.md`](../ingestion/README.md).
>
> Each file below explains what a project phase changed **on this side**, which files/folders it
> touches, and links to the ingestion-side counterpart when a phase touched both. For the full,
> unabridged narrative (data model, worked example, end-to-end diagrams) see
> [`../how_this_works.md`](../how_this_works.md); for the authoritative task-by-task plan and status
> ledger see [`../PLAN.md`](../PLAN.md).

**Deliberately out of scope here:**

- **Phase 4.7 — Obi widget** (`apps/web`, the chat UI itself). It consumes this path over `POST
  /chat` but owns no retrieval/answer logic. See [`../OBI-WIDGET-DESIGN.md`](../OBI-WIDGET-DESIGN.md).
- **Phase 4.8 — Frontend/backend repository separation.** Moved out of the plan entirely; see
  [`../../future-ideas/IDEAS.md`](../../future-ideas/IDEAS.md) idea #5 and
  `docs/adr/0010-Redefer-Repository-Separation.md`.

## Phases

| Phase | What it did, on the read/answer side | Status | File |
|---|---|---|---|
| 0 | Design docs + ADR-0005 (reranking + answer-pipeline decisions) that govern everything below | ✅ done | [phase-0.md](./phase-0.md) |
| 3 | Original hybrid retriever: dense (HNSW) ∥ keyword (`tsvector`) → RRF → baseline permission filter | ✅ done (pre-PLAN.md) | [phase-3.md](./phase-3.md) |
| 3.5 | pgvector 0.8 + iterative scan, cross-encoder reranker, `rag_reader`/RLS enforcement at query time, `query_trace`, rerank-lift measurement | ✅ done | [phase-3.5.md](./phase-3.5.md) |
| 4 | `rag_agent` answer runtime (rewrite → retrieve/rerank → CRAG → refuse → expand → generate → cite) + `POST /chat` SSE | ✅ done | [phase-4.md](./phase-4.md) |
| 4.6 | Fixes-backlog remediation, retrieval/chat-relevant sub-steps (idempotency leak, rate-limiter, scope-classification bug, RLS fail-closed, refusal-reason observability) | ✅ done | [phase-4.6.md](./phase-4.6.md) |
| 5 | `CHAT_API_KEY` rotation, exact-match answer caching, prompt-injection/isolation red-team; 5.4 (live-LLM red-team, embedder bake-off, adaptive routing) still planned | 5.1–5.3 ✅ done, 5.4 ⬜ planned | [phase-5.md](./phase-5.md) |
| 7 | Vision-grounded image analysis: a turn's images get a second, independent generation call folded into `Answer.image_analysis` | ✅ done | [phase-7.md](./phase-7.md) |
| 9 | Unanswerable/vague-query fallback: ambiguity classifier + clarifying question, 3-value refusal-reason taxonomy, human hand-off stub, fallback-quality eval metrics | ✅ done | [phase-9.md](./phase-9.md) |
| 10 | Knowledge-scope tagging (retrieval-side half): `tags`-based hard filter behind a dark-by-default flag, request-level `knowledge_scope` threading, always-present curated knowledge | 10.1–10.6 ✅ done, 10.7–10.9 ⬜ not started | [phase-10.md](./phase-10.md) |

Phases 1, 2, and 3.5.6 (Confluence sync, chunking/contextualization/versioning, source scoping) are
write-path only and are documented in [`../ingestion/`](../ingestion/) instead.

## Keeping this current

Per the root [`CLAUDE.md`](../../../CLAUDE.md), this folder documents the current architecture — when
retrieval or answer-runtime behavior changes, update the relevant phase file (or add a new one) in the
same change, not as separate follow-up work.
