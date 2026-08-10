"""Permission-aware hybrid retriever: dense ∥ keyword → RRF → permission filter → rerank → pages.

Returns page ids (as strings, to match the eval id space) ranked by fused-then-reranked relevance,
after removing any page the caller scope may not see. Status is already enforced by the index (only
current pages have active chunks); permission is enforced here, and the cross-encoder rerank runs
*after* the permission filter so a doc the principal can't see is never scored. Keyword rank breaks
RRF ties so lexical relevance wins when the dense signal is weak (e.g. the offline Fake embedder).

``retrieve()`` is the original, eval-harness-facing shape (page ids only) and stays unchanged so the
`RankFn` seam and its existing assertions keep working. ``retrieve_with_context()`` is the Phase 4.2
answer-workflow entry point: same ranking, but it also surfaces each hit's chunk id (for parent
expansion), rerank score (for the refusal threshold), and title/url (for citations) — the data
``retrieve()`` computed all along but discarded. Both share one internal search core, and both
write the same ``query_trace`` row shape when tracing is enabled.

PLAN 4.3: the page-level permission check is now backed by the persisted ``page_restriction``
table, queried fresh per search for the current candidate set (never the whole corpus). The
``policy`` constructor argument is kept only for its stateless ``space_id()`` scope parsing; its
``space_of``/``restrictions`` data is no longer consulted for the ``allowed()`` decision — that
decision runs against a request-scoped policy built from live DB data instead.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.features.retrieval.domain.fusion import reciprocal_rank_fusion
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.features.retrieval.infrastructure.search_repo import (
    apply_hnsw_gucs,
    apply_source_scope,
    dense_search,
    fetch_page_scopes,
    fetch_parent_context,
    fetch_rerank_texts,
    keyword_search,
)
from app.features.retrieval.infrastructure.trace_repo import write_query_trace
from app.platform.clients import EmbeddingProvider, Reranker


@dataclass(frozen=True)
class RetrievedHit:
    """One ranked, permitted, reranked page — with the extra fields Phase 4 needs."""

    page_id: str
    chunk_id: int
    score: float
    title: str
    url: str


@dataclass(frozen=True)
class RetrievalResult:
    """The answer workflow's view of a retrieval: hits plus the trace row they were logged under."""

    hits: list[RetrievedHit] = field(default_factory=list)
    trace_id: int | None = None

    @property
    def page_ids(self) -> list[str]:
        return [h.page_id for h in self.hits]

    @property
    def top_score(self) -> float | None:
        return self.hits[0].score if self.hits else None


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

    def _search(self, query: str, scope: str | None, k: int) -> list[RetrievedHit]:
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

            # PLAN 4.3: page-level ACL, loaded fresh for this candidate set (never the whole
            # corpus — the injected `self._policy` no longer carries real data; it is queried
            # live from page_source/page_restriction, alongside source-level RLS above).
            space_of, restrictions = fetch_page_scopes(session, ranked)
            live_policy = PrincipalPermissionPolicy(space_of=space_of, restrictions=restrictions)
            allowed = [p for p in ranked if live_policy.allowed(p, scope)]

            # Cross-encoder rerank the permitted candidates (never a doc the scope can't see).
            # FakeReranker is order-preserving, so offline this is exactly the pre-rerank ranking.
            to_rerank = allowed[: self._rerank_depth]
            candidates = fetch_rerank_texts(session, to_rerank, space_id, sources)
            docs = [(pid, candidates[pid].text) for pid in to_rerank if pid in candidates]

        reranked = self._reranker.rerank(query, docs, top_k=k)
        return [
            RetrievedHit(
                page_id=str(pid),
                chunk_id=candidates[pid].chunk_id,
                score=score,
                title=candidates[pid].title,
                url=candidates[pid].source_url,
            )
            for pid, score in reranked
            if pid in candidates
        ]

    def _trace(self, query: str, hits: Sequence[RetrievedHit], started: float) -> int | None:
        if self._trace_sessionmaker is None:
            return None
        latency_ms = int((time.perf_counter() - started) * 1000)
        with self._trace_sessionmaker() as trace_session:
            return write_query_trace(
                trace_session,
                raw_query=query,
                retrieved_page_ids=[int(h.page_id) for h in hits],
                retrieved_chunk_ids=[h.chunk_id for h in hits],
                rerank_scores=[h.score for h in hits],
                allowed_sources=self._allowed_sources,
                embedding_model=self._embedder.model,
                reranker_model=self._reranker.model,
                latency_ms=latency_ms,
            )

    def retrieve(self, query: str, scope: str | None, k: int = 5) -> list[str]:
        started = time.perf_counter()
        hits = self._search(query, scope, k)
        self._trace(query, hits, started)
        return [h.page_id for h in hits]

    def retrieve_with_context(self, query: str, scope: str | None, k: int = 5) -> RetrievalResult:
        """Phase 4.2 entry point: hits carry chunk id + score + title/url, plus the trace row id."""
        started = time.perf_counter()
        hits = self._search(query, scope, k)
        trace_id = self._trace(query, hits, started)
        return RetrievalResult(hits=hits, trace_id=trace_id)

    def fetch_parent_texts(self, chunk_ids: Sequence[int]) -> dict[int, str]:
        """Each retrieved child chunk's parent text, keyed by chunk id (children retrieve, parents
        ground). Re-applies the source-scope GUC on this fresh session — a new transaction starts
        with no GUC set, and the chunk table is RLS-protected regardless of parent/child kind."""
        if not chunk_ids:
            return {}
        with self._session_factory() as session:
            apply_source_scope(session, self._allowed_sources)
            return fetch_parent_context(session, chunk_ids)
