# Omniboost RAG — Final Design

> The definitive as-built design of the Omniboost RAG system ("Obi"): an accuracy-first,
> Confluence-native, multi-platform retrieval-augmented chat assistant. This folder is written
> against the running code (Aug–Sep 2026) and cross-checked against the ADRs, `docs/rag/DESIGN.md`,
> `docs/rag/PLAN.md`'s status ledger, and the two phase folders. Where a claim is load-bearing it is
> anchored `file:line` so it can be checked against the tree.

---

## The 60-second picture

Omniboost RAG answers questions about Confluence documentation without hallucinating. It is built
around **two independent flows that share one Postgres + pgvector corpus**:

- **Ingestion (the write path)** — a Confluence webhook (or a reconciliation sweep) feeds a
  crash-safe job queue; a worker turns each changed page into **parent + child chunks**, writes a
  short LLM-authored situating context per child, embeds children with OpenAI `text-embedding-3-large`
  (3072-dim, stored as `halfvec` for the HNSW index), builds a keyword `tsvector`, stages an
  **immutable `document_version`**, and activates it with a single-transaction pointer swap
  (instant rollback, GC of old versions).
- **Retrieval + answer (the read path)** — a user question is rewritten to a standalone query,
  embedded, and searched two ways in parallel: **dense** (HNSW cosine) ∥ **keyword** (GIN tsvector),
  fused with **Reciprocal Rank Fusion**, filtered by three security layers (source-level Postgres
  RLS, page-level principal ACL, knowledge-scope tag filter), **cross-encoder reranked** (Cohere
  `rerank-v3.5`), abstained on if the top score is weak, expanded to parent context, and turned into
  a **grounded answer with forced numbered citations** — streamed to the browser widget over
  `POST /chat` (SSE).

The design's whole thesis: **accuracy is enforced in code, not merely prompted** — uncited claims
are stripped, a hard refusal threshold routes weak matches to a human, and a database-enforced
default-deny boundary means the failure mode is "no results," never "another tenant's results."

## What is shipped vs. planned

Shipped and verified (backend suite: 481 passing as of PLAN 10.7):

- Phases 0, 3, 3.5, 4, 4.6, 4.7 (Obi widget), 5.1–5.3, 7 (vision image analysis), 9 (ambiguity
  clarification), and Phase 10 sub-steps 10.1–10.7 (knowledge-scope tagging + filter, flag flipped on
  in the live deployment).

In flight / planned (see `docs/rag/PLAN.md` §0 for the live ledger):

- Phase 10.8 (widget scope switcher + live self-test) — **build half done, uncommitted**.
- Phase 6 (Supabase-on-AWS vector-store migration + deploy) — **specced, not built; the chosen next
  work**; needs an operator-provided connection string (blocker #8) and a small `FORCE`-RLS fix
  (see `05-security-isolation.md`).
- Phase 11 (separation-of-concerns + a **critical** customer-isolation security backstop, 11.1a) and
  Phase 12 (renumber) — **scoped, not built**.

Two honest, recorded caveats: pgvector was affirmed positively but never benchmarked head-to-head
against other vector stores, and **no scale/latency/QPS/SLA target exists anywhere** in the repo
(corpus today ≈ 9 pages / 85 chunks; latency unmeasured until Phase 5.4). This design does not invent
those numbers — where none exists it says so.

## Reading order

| # | File | What it covers |
|---|---|---|
| 1 | [`01-system-overview.md`](./01-system-overview.md) | The product, fixed product decisions, the two flows, the tech stack, and the verified storage decision |
| 2 | [`02-ingestion.md`](./02-ingestion.md) | The full write path, step by step, with the files/functions for each stage |
| 3 | [`03-retrieval.md`](./03-retrieval.md) | The full read/answer path, step by step |
| 4 | [`04-data-model.md`](./04-data-model.md) | Every table, key columns, relationships, the two search indexes, ER diagram |
| 5 | [`05-security-isolation.md`](./05-security-isolation.md) | The three-layer isolation model + the two known open issues |
| 6 | [`06-system-visualization.md`](./06-system-visualization.md) | The whole system as a set of Mermaid diagrams (architecture, ER, ingestion, retrieval, security, deployment) |

## Source-of-truth documents this folder is derived from

- **ADRs** — `docs/adr/0001`–`0011` (accepted decisions of record).
- **`docs/rag/DESIGN.md`** — the normative design of record.
- **`docs/rag/PLAN.md`** — the execution plan and the authoritative **status ledger** (§0).
- **`docs/rag/how_this_works.md`** and the per-phase maps in `docs/rag/ingestion/` and
  `docs/rag/retrieval/`.
- **`docs/rag/OBI-WIDGET-DESIGN.md`** — the frontend widget as built.

Where this folder and any of the above disagree, treat the running code as truth and file the drift.
