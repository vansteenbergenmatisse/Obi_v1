# Omniboost RAG — Final Design

> The **target design** of the Omniboost RAG system ("Obi"): an accuracy-first, Confluence-native,
> multi-platform retrieval-augmented chat assistant. This folder describes the system as it is meant to
> be built — the design of record, in the present tense — so it is the reference you check work against.
> **Build status lives elsewhere:** `docs/rag/PLAN.md` §0 is the authoritative ledger of what is live on
> which host. Claims here are cross-checked against the ADRs and `docs/rag/DESIGN.md`; where one is
> load-bearing it is anchored `file:line` so it can be checked against the tree.

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
  RLS, customer-axis `RESTRICTIVE` scope-GUC RLS, page-level principal ACL), **cross-encoder reranked**
  (Cohere `rerank-v3.5`), abstained on if the top score is weak, expanded to parent context, and turned
  into a **grounded answer with forced numbered citations** — streamed to the browser widget over
  `POST /chat` (SSE).

The design's whole thesis: **accuracy is enforced in code, not merely prompted** — uncited claims
are stripped, a hard refusal threshold routes weak matches to a human, and a database-enforced
default-deny boundary means the failure mode is "no results," never "another tenant's results."

## Build status lives in PLAN §0

This folder is the *target* — what the system is meant to be. It deliberately does **not** track which
phases are built, committed, or live; that is the job of `docs/rag/PLAN.md` §0, the authoritative status
ledger. Read the design here, then diff it against PLAN §0 to see what remains to do.

Two honest, recorded caveats that are part of the design's posture, not its status: pgvector was
affirmed positively but never benchmarked head-to-head against other vector stores, and **no
scale/latency/QPS/SLA target exists anywhere** in the repo (the corpus is small; latency is measured in
the Phase 5.4 eval). This design does not invent those numbers — where none exists it says so.

## Reading order

| # | File | What it covers |
|---|---|---|
| 1 | [`01-system-overview.md`](./01-system-overview.md) | The product, fixed product decisions, the two flows, the tech stack, and the verified storage decision |
| 2 | [`02-ingestion.md`](./02-ingestion.md) | The full write path, step by step, with the files/functions for each stage |
| 3 | [`03-retrieval.md`](./03-retrieval.md) | The full read/answer path, step by step |
| 4 | [`04-data-model.md`](./04-data-model.md) | Every table, key columns, relationships, the two search indexes, ER diagram |
| 5 | [`05-security-isolation.md`](./05-security-isolation.md) | The three-layer isolation model + the writer/reader split and its ADR-0013/0014 rationale |
| 6 | [`06-system-visualization.md`](./06-system-visualization.md) | The whole system as a set of Mermaid diagrams (architecture, ER, ingestion, retrieval, security, deployment) |

## Source-of-truth documents this folder is derived from

- **ADRs** — `docs/adr/0001`–`0014` (accepted decisions of record).
- **`docs/rag/DESIGN.md`** — the normative design of record.
- **`docs/rag/PLAN.md`** — the execution plan and the authoritative **status ledger** (§0).
- **`docs/rag/how_this_works.md`** and the per-phase maps in `docs/rag/ingestion/` and
  `docs/rag/retrieval/`.
- **`docs/rag/OBI-WIDGET-DESIGN.md`** — the frontend widget as built.

Where this folder and any of the above disagree, treat the running code as truth and file the drift.
