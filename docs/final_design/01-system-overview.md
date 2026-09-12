# 01 — System Overview

## What Obi is

Omniboost RAG (the assistant is branded **"Obi"**) is an **accuracy-first, Confluence-native,
multi-platform retrieval-augmented chat widget**. One backend and one knowledge corpus power a
floating chat widget that can be embedded across multiple third-party hospitality platforms (Mews,
Opera Cloud, Toast POS) plus a general standalone deployment, without forking per platform and
without one platform's documentation leaking into another's answers.

The product's defining constraint is **accuracy over coverage**: it would rather refuse and route a
user to a human than answer from thin evidence. That constraint is enforced in code — not merely
requested in a prompt — at three points:

1. **Forced citations** — every claim in an answer must cite a retrieved chunk; uncited sentences
   are stripped before the answer is returned (`rag_agent/domain/citations.py::enforce_citations`).
   If nothing survives, the answer degrades to a refusal rather than an empty or ungrounded reply.
2. **A hard refusal threshold** — if the top reranked score is below `refusal_min_rerank_score`
   (default `0.10`, settings.py:99) the runtime abstains and offers a human hand-off instead of
   guessing.
3. **Database-enforced isolation** — both the source axis and the customer/platform axis are
   **default-deny Postgres Row-Level Security** (source RLS, ADR-0004; a `RESTRICTIVE` scope-GUC policy,
   ADR-0014), so a retrieval that forgets to scope returns *zero* rows, never another tenant's rows.

## Fixed product decisions

These are settled decisions of record (from `docs/rag/PLAN.md` §1 and the ADRs). They are not
open for casual re-litigation; changing one requires a new ADR.

| Decision | Source | Note |
|---|---|---|
| Confluence is the (only, for now) knowledge source | ADR-0002, ADR-0004 | Canonical identity = the Confluence **page id**; all sync is idempotent + version-aware |
| Versioned store with **atomic activation** | ADR-0002 | An index update is immutable and all-or-nothing; the live corpus is never half-rebuilt; rollback is instant |
| **Hybrid** retrieval (dense + keyword), fused by **RRF** | ADR-0002 | `score = Σ 1/(60 + rank)`; cross-encoder reranked; never the answer model as reranker |
| **Cross-encoder rerankers only** — no general-LLM reranker | ADR-0005 | Cheaper per candidate, deterministic enough to eval |
| The answer runtime is a **fixed workflow, not an agent loop** | ADR-0005 | Bounded latency, stage-by-stage testable, auditable refusal + citation enforcement |
| **One CRAG corrective retry** maximum | ADR-0005 | Bounded to protect p95; not an unbounded agent loop |
| **Three layered security controls**, all applied on every read | ADR-0004, ADR-0011, ADR-0014 | Source RLS + customer-axis `RESTRICTIVE` scope-GUC RLS (+ app predicate) + page-principal ACL |
| Deterministic **SQL filtering**, never LLM filters | ADR-0002, DESIGN §8 | Keeps recall honest |
| **Postgres + pgvector** is the stack; switching is ruled out | ADR-0001/0002, PLAN §0 | See "Storage decision" below |
| Frontend/backend stay one monorepo for now | ADR-0006, ADR-0010 | Repo split re-deferred until a real second consumer exists |

## The two independent flows

The system is best understood as two flows that share one Postgres corpus and otherwise run
independently:

- **Ingestion (write path)** — `app/features/confluence_sync` → `app/features/ingestion`. Turns a
  Confluence page into searchable rows. Runs as the **writer** DB role (owner, exempt from RLS by
  ownership + `NO FORCE`). See [`02-ingestion.md`](./02-ingestion.md).
- **Retrieval + answer (read path)** — `app/features/retrieval` → `app/features/rag_agent` →
  `POST /chat`. Turns a question into a grounded, cited, streamed answer. Runs the search as the
  non-owner **reader** DB role (RLS enforced). See [`03-retrieval.md`](./03-retrieval.md).

The only seam between them is the shared corpus and one ingestion activation point that stamps
`source_id`/`source_type`/`tags` onto each chunk.

## Tech stack (as built)

| Layer | Technology | Anchor |
|---|---|---|
| Frontend | Next.js + React + TypeScript + Tailwind + semantic design tokens (`apps/web`) | ADR-0001 |
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic (`apps/automation`) | ADR-0001 |
| Package mgmt | `pnpm` workspace for JS/TS; `uv` + Hatchling for Python (never mixed) | root `CLAUDE.md` |
| Contracts | `packages/contracts` — OpenAPI source of truth (`chat.yaml`) → generated TS + hand-authored Pydantic | ADR-0001 |
| Database | **PostgreSQL 16 + pgvector + Postgres full-text search (tsvector)** | ADR-0001 |
| Dense index | pgvector **HNSW** (cosine); `m=16, ef_construction=200` (models.py:64) | ADR-0002 |
| Keyword index | Postgres **GIN** over `tsvector` (models.py:315) | ADR-0002 |
| Fusion | Reciprocal Rank Fusion, constant `k=60` | ADR-0002, fusion.py |
| Reranker | **Cohere `rerank-v3.5`** cross-encoder (reranker_model, settings.py:83); `FakeReranker` offline | ADR-0005 |
| Answer model | Anthropic **`claude-sonnet-5`** (answer_model, settings.py:58) | ADR-0009 |
| Routing/rewrite model | Anthropic **`claude-haiku-4-5-20251001`** (routing_model, settings.py:57) | ADR-0009 |
| Embeddings | See the discrepancy note below | ADR-0002 |

### Embedding provider — code default vs deployed `.env` override

The ADRs and `docs/rag/DESIGN.md` describe embeddings as **OpenAI `text-embedding-3-large` at 3072
dimensions**, stored full-precision and indexed via a **`halfvec(3072)` cast** because pgvector caps a
plain-`vector` HNSW index at 2000 dimensions (ADR-0002 amendment; DESIGN §1).

There are **two layers** to reconcile — the code default and the deployed override:

- **Code default** (`settings.py:61-63`): `embedding_provider = "voyage"`, `embedding_model =
  "voyage-3-large"`, `embedding_dim = 1024`. At 1024 ≤ 2000 dims the HNSW index would be built with
  plain `vector_cosine_ops` (models.py:63, 77-84); the halfvec cast fires only when `embedding_dim >
  2000` (models.py:68-76).
- **Deployed reality** (the gitignored root `.env`, verified 2026-09-07): `EMBEDDING_PROVIDER=openai`,
  `EMBEDDING_MODEL=text-embedding-3-large`, `EMBEDDING_DIM=3072`. **The `.env` overrides the code
  default**, so the *actual running/prod configuration is OpenAI 3072-dim → the `halfvec(3072)` HNSW
  path** — matching the ADR-0002 amendment and DESIGN §1, not the settings.py default.

So the ADR/DESIGN description (OpenAI-3072/halfvec) is what the deployment runs; the Voyage/1024 values
are the *fallback* baked into `settings.py` for when no `.env` override is present. **The target prod
embedder is OpenAI `text-embedding-3-large` @ 3072 → `halfvec(3072)` HNSW.** Phase 5.4's "embedder
bake-off" (`VOYAGE_API_KEY` provisioned) is where any provider change would be settled — Voyage
`voyage-3-large` is 1024-dim vs the live `halfvec(3072)`, so a fair comparison re-embeds the corpus into
a separate 1024-dim index before scoring — and the `settings.py` default reconciled with the `.env`.
Whichever provider is active, ingestion and retrieval always use the **same** embedder, and a change of
embedding model/dim forces a full re-embed via the version-stamp gate (ADR-0002 point 6).

## Storage decision (VERIFIED)

Cross-checked against every doc in `docs/rag`, all 14 ADRs, and the code (PLAN §0):

- **Engine = Postgres + pgvector — ratified.** ADR-0001 declares the stack, ADR-0002 builds the
  retrieval core on pgvector HNSW + tsvector GIN + RRF, ADR-0004 makes Postgres RLS the isolation
  spine, and the docs explicitly rule out switching (DESIGN.md:498 / PLAN.md:4317: *"No new vector
  store or search engine. Postgres+pgvector+Cohere stays the stack (ADR-0001/0002)."*). Everything
  — dense, keyword, RLS, ACL, versioning, tags, the job queue, `query_trace`, curated knowledge —
  lives in one Postgres store.
- **Production host = Supabase Cloud on AWS — FINAL** (user decision 2026-09-07). Supabase Cloud runs
  on AWS (you pick an AWS region at project creation) and is reached by plain connection string, so it
  satisfies the "on AWS infra, reachable" requirement with the least work and **zero lock-in** — the
  app is plain-Postgres-over-`psycopg` (a DSN only; no Supabase REST/JS SDK, no `ANON_KEY`).
- **AWS RDS/Aurora = a documented, reversible fallback**, not the primary. Supabase → RDS is a
  connection-string swap + role/RLS re-apply, not a rewrite. This becomes relevant only if an
  in-our-own-VPC requirement ever hardens.
- **Recorded in ADR-0013.** The managed-Postgres cutover — Supabase on AWS, `NO FORCE` RLS, separate
  writer/reader DSNs, pgvector ≥ 0.8 — is a durable decision of record. Live cutover progress (which
  migrations are applied to the Supabase head) is tracked in `docs/rag/PLAN.md` §0.

**Two honest caveats (recorded, not smoothed over):** (1) pgvector was affirmed *positively* but never
benchmarked head-to-head against Pinecone/Weaviate/Qdrant — those names appear nowhere in the repo;
(2) **no scale/latency/QPS/SLA target exists anywhere** (corpus today ≈ 9 pages / 85 chunks; latency
unmeasured until Phase 5.4). The storage choice is not validated against a future scale requirement
because no such requirement has been written down. If one lands, it is a new decision, not a silent
one.
