"""Permission-aware hybrid retriever: dense ∥ keyword → RRF → permission filter → rerank → pages.

Returns page ids (as strings, to match the eval id space) ranked by fused-then-reranked relevance,
after removing any page the caller scope may not see. Status is already enforced by the index (only
current pages have active chunks); permission is enforced here, and the cross-encoder rerank runs
*after* the permission filter so a doc the principal can't see is never scored. Keyword rank breaks
RRF ties so lexical relevance wins when the dense signal is weak (e.g. the offline Fake embedder).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from app.features.retrieval.domain.fusion import reciprocal_rank_fusion
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.features.retrieval.infrastructure.search_repo import (
    apply_hnsw_gucs,
    apply_source_scope,
    dense_search,
    fetch_rerank_texts,
    keyword_search,
)
from app.features.retrieval.infrastructure.trace_repo import write_query_trace
from app.platform.clients import EmbeddingProvider, Reranker


def _dedupe(pairs: Sequence[tuple[int, float]]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for page_id, _ in pairs:
        if page_id not in seen:
            seen.add(page_id)
            out.append(page_id)
    return out


class HybridRetriever:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        embedder: EmbeddingProvider,
        policy: PrincipalPermissionPolicy,
        reranker: Reranker,
        *,
        candidate_k: int = 75,
        rerank_depth: int = 75,
        allowed_sources: Sequence[str] = ("confluence:default",),
        hnsw_ef_search: int = 100,
        hnsw_iterative_scan: str = "relaxed_order",
        trace_sessionmaker: Callable[[], Session] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder
        self._policy = policy
        self._reranker = reranker
        self._candidate_k = candidate_k
        self._rerank_depth = rerank_depth
        self._allowed_sources = tuple(allowed_sources)
        self._hnsw_ef_search = hnsw_ef_search
        self._hnsw_iterative_scan = hnsw_iterative_scan
        # optional WRITER sessionmaker: when set, each retrieve writes one query_trace row (3.5.4)
        self._trace_sessionmaker = trace_sessionmaker

    def retrieve(self, query: str, scope: str | None, k: int = 5) -> list[str]:
        started = time.perf_counter()
        space_id = self._policy.space_id(scope)
        query_vec = self._embedder.embed([query])[0]
        sources = self._allowed_sources
        with self._session_factory() as session:
            # Per-txn knobs, same transaction as the searches below:
            #  - HNSW iterative_scan keeps recall honest once a narrow scope prunes rows (3.5.1)
            #  - the source-scope GUC drives RLS default-deny on the reader role (ADR-0004)
            apply_hnsw_gucs(
                session,
                ef_search=self._hnsw_ef_search,
                iterative_scan=self._hnsw_iterative_scan,
            )
            apply_source_scope(session, sources)
            kw = keyword_search(session, query, space_id, self._candidate_k, sources)
            dense = dense_search(
                session, query_vec, space_id, self._candidate_k, self._embedder.dim, sources
            )

            kw_pages = _dedupe(kw)
            dense_pages = _dedupe(dense)
            fused = reciprocal_rank_fusion([kw_pages, dense_pages])
            kw_pos = {pid: i for i, pid in enumerate(kw_pages)}

            # tie-break by keyword rank so lexical relevance decides when RRF scores tie
            ranked = sorted(fused, key=lambda p: (-fused[p], kw_pos.get(p, 1_000_000), p))
            allowed = [p for p in ranked if self._policy.allowed(p, scope)]

            # Cross-encoder rerank the permitted candidates (never a doc the scope can't see).
            # FakeReranker is order-preserving, so offline this is exactly the pre-rerank ranking.
            to_rerank = allowed[: self._rerank_depth]
            texts = fetch_rerank_texts(session, to_rerank, space_id, sources)
            docs = [(pid, texts[pid]) for pid in to_rerank if pid in texts]

        reranked = self._reranker.rerank(query, docs, top_k=k)
        page_ids = [pid for pid, _score in reranked]

        if self._trace_sessionmaker is not None:
            latency_ms = int((time.perf_counter() - started) * 1000)
            with self._trace_sessionmaker() as trace_session:
                write_query_trace(
                    trace_session,
                    raw_query=query,
                    retrieved_page_ids=page_ids,
                    allowed_sources=sources,
                    embedding_model=self._embedder.model,
                    reranker_model=self._reranker.model,
                    latency_ms=latency_ms,
                )

        return [str(pid) for pid in page_ids]
