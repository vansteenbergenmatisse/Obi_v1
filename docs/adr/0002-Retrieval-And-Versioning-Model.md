# 0002 — Retrieval and Versioning Model

Status: Accepted
Date: 2026-07-28
Governs: apps/automation (ingestion, retrieval, versioning)

## Decision

1. **Canonical identity** is the Confluence page ID. All sync operations are idempotent and
   version-aware to tolerate duplicated / delayed / out-of-order events.
2. **Versioned store with atomic activation.** A page's indexed content is an immutable
   `document_version` (staging → active → superseded). Activation is a single-transaction pointer
   swap (`page_source.active_doc_version_id` + `chunk.is_active` flip). Obsolete chunks are
   deleted only after a successful activation; N superseded versions are retained for rollback.
3. **Stable section/chunk identity** derived from `(page_id, heading_path, structural position,
   normalized content)` so editing one section reuses unchanged embeddings.
4. **Hybrid retrieval**: dense (pgvector HNSW) + keyword (tsvector GIN), fused by Reciprocal Rank
   Fusion `score = Σ 1/(60 + rank)`, cross-encoder reranked (never the answer model), then
   parent-child context expansion under an evidence-token budget.
5. **Mandatory pre-model filters** on every retrieval: active version, scope, page status,
   retrieval-schema version, embedding model, and caller access scope.
6. **Full re-embedding** only on embedding-model/dim, retrieval-content, contextualization,
   chunking, parser, metadata-representation, or index-schema changes — built into a separate
   index version, eval-gated, atomically activated, with rollback.

## Reason

Accuracy and recall are the top priorities; correctness of the versioned store (no mixed
versions, no silent re-embedding, safe recovery) underpins knowledge freshness and reliability.

## Paths governed

`apps/automation/app/features/{ingestion,retrieval}/**`, `alembic/**`.

## Amendment (Phase 3): high-dimension embedding index

`chunk.embedding` is `vector(EMBEDDING_DIM)`. pgvector caps a `vector` HNSW index at 2000
dimensions, but the chosen model (OpenAI `text-embedding-3-large`) emits 3072. Rather than
reduce the embedding, the HNSW index is built on a half-precision cast —
`(embedding::halfvec(DIM)) halfvec_cosine_ops` — which pgvector supports up to 4000 dimensions.
Full-precision vectors remain stored in the column; only the ANN index uses half precision
(negligible recall impact). For models ≤2000 dims the index stays a plain `vector_cosine_ops`
HNSW. Retrieval's dense query mirrors the cast so the index is used. Point 4 above is refined
accordingly; cross-encoder reranking (point 4) lands in Phase 4.
