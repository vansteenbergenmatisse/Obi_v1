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
``policy`` constructor argument's ``space_of``/``restrictions`` data is no longer consulted for
the ``allowed()`` decision — that decision runs against a request-scoped policy built from live DB
data instead.

PLAN 4.6.6: the raw ``scope`` string is classified into an explicit ``(space_id, principal)`` pair
exactly once per search, via ``permission.classify_scope`` — never re-derived from string shape
again once split.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.features.retrieval.domain.applicability_match import (
    AttributionValue,
    CustomerContext,
    EligibilityParams,
    attribution_for_reason,
    eligibility_params,
    match_applicability,
)
from app.features.retrieval.domain.fusion import reciprocal_rank_fusion
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy, classify_scope
from app.features.retrieval.domain.rerank_enrichment import (
    applicability_yaml,
    build_rerank_document,
    build_rerank_query,
    context_preamble,
)
from app.features.retrieval.infrastructure.search_repo import (
    RerankCandidate,
    apply_allowed_labels,
    apply_hnsw_gucs,
    apply_knowledge_scope,
    apply_source_scope,
    dense_search,
    fetch_page_scopes,
    fetch_parent_context,
    fetch_rerank_texts,
    keyword_search,
)
from app.features.retrieval.infrastructure.trace_repo import write_query_trace
from app.platform.clients import EmbeddingProvider, Reranker
from app.platform.config.product_catalog import ProductCatalog, load_product_catalog


@lru_cache(maxsize=1)
def _catalog() -> ProductCatalog:
    """The committed product catalog, loaded once per process for eligibility derivation
    (substep 8.3.1, panel mi-filter). `Settings` already fail-fasts a malformed file at boot;
    the cache keeps the search path from re-reading the JSON per request (the same posture as
    the gate's `_default_catalog`)."""
    return load_product_catalog()


@dataclass(frozen=True)
class RetrievedHit:
    """One ranked, permitted, reranked page — with the extra fields Phase 4 needs.

    ``attribution`` (substep 8.3.4, panel mi-attrib) is why this result was eligible for THIS
    customer — ``general`` / a named slot (``pos`` / ``pms`` / ``accounting``) / ``pair`` —
    assembled in the backend from the §D.4 matcher reason the rerank step already computed.
    ``None`` on the no-context / eval path and for a label-only (unstamped) page, so the pre-8.3.4
    shape is unchanged. It carries nothing beyond the customer's own context (rule 10)."""

    page_id: str
    chunk_id: int
    score: float
    title: str
    url: str
    attribution: AttributionValue | None = None


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

    def _search(
        self,
        query: str,
        scope: str | None,
        k: int,
        knowledge_scopes: Sequence[str] | None = None,
        customer_context: CustomerContext | None = None,
        session_labels: Sequence[str] | None = None,
    ) -> tuple[list[RetrievedHit], list[str] | None]:
        space_id, principal = classify_scope(scope)
        query_vec = self._embedder.embed([query])[0]
        sources = self._allowed_sources
        # ADR-0021: the knowledge-scope axis is retired. No app-layer scope predicate is ever
        # applied (the scope GUC is opted out to wildcard below); `knowledge_scopes` is accepted
        # for call-shape compatibility but intentionally ignored. Content is routed by the labels.
        effective_scopes = None
        # Option A Stage 6 / 9.4.1 (panel mi-hardfilter, ADR-0020 D1/D2): the directed-connection
        # label list this chat is bound to. A directed chat carries its four routing boxes; a
        # legacy/slot/tokenless chat carries None, so the hard filter is a no-op (the label axis is
        # relevance, not the access fence). Passed as a kwarg only when present so every existing
        # call shape (and the repo-function test doubles) stays byte-identical to pre-9.4.1.
        label_filter = list(session_labels) if session_labels is not None else None
        # 8.3.1 (panel mi-filter): one eligibility derivation per search, applied inside the
        # SQL of BOTH candidate queries and the rerank-text fetch below — applicability narrows
        # within what access (RLS + scope + permissions) already allows, before the limit. No
        # context (the internal/eval path) means no applicability predicate — unchanged SQL.
        eligibility: EligibilityParams | None = (
            eligibility_params(customer_context, _catalog())
            if customer_context is not None
            else None
        )
        # Both the eligibility predicate (8.3.1) and the directed-connection label filter (9.4.1)
        # ride along as kwargs ONLY when present, so the no-context / no-connection call shape — and
        # every repo-function test double that fakes a narrower signature — stays byte-identical to
        # its earlier shape. Typed `dict[str, Any]` so the one `**` expansion type-checks cleanly.
        search_kwargs: dict[str, Any] = {}
        if eligibility is not None:
            search_kwargs["eligibility"] = eligibility
        if label_filter is not None:
            search_kwargs["session_labels"] = label_filter
        with self._session_factory() as session:
            # Per-txn knobs, same transaction as the searches below:
            #  - HNSW iterative_scan keeps recall honest once a narrow scope prunes rows (3.5.1)
            #  - the source-scope GUC drives RLS default-deny on the reader role (ADR-0004) —
            #    this is the source/company isolation axis and is UNCHANGED.
            #  - the knowledge-scope axis is RETIRED (ADR-0021): always opt out (wildcard None) so
            #    the scope GUC never restricts, independent of whether migration 0018 has dropped
            #    the chunk_scope_read policy yet. Content is routed by the label axis below.
            apply_hnsw_gucs(
                session,
                ef_search=self._hnsw_ef_search,
                iterative_scan=self._hnsw_iterative_scan,
            )
            apply_source_scope(session, sources)
            apply_knowledge_scope(session, None)
            # 9.4.1 (ADR-0020 D1): the labels GUC is set in the SAME txn/path as the scope GUC, so
            # the RESTRICTIVE chunk_labels_read policy and the app-layer `labels && :session_labels`
            # predicate agree (rules 1 and 3). None -> '*' opt-out (legacy/slot chats route none).
            apply_allowed_labels(session, label_filter)
            kw = keyword_search(
                session,
                query,
                space_id,
                self._candidate_k,
                sources,
                effective_scopes,
                **search_kwargs,
            )
            dense = dense_search(
                session,
                query_vec,
                space_id,
                self._candidate_k,
                self._embedder.dim,
                sources,
                effective_scopes,
                **search_kwargs,
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
            allowed = [
                p for p in ranked if live_policy.allowed(p, space_id=space_id, principal=principal)
            ]

            # Cross-encoder rerank the permitted candidates (never a doc the scope can't see).
            # FakeReranker is order-preserving, so offline this is exactly the pre-rerank ranking.
            to_rerank = allowed[: self._rerank_depth]
            candidates = fetch_rerank_texts(
                session,
                to_rerank,
                space_id,
                sources,
                effective_scopes,
                **search_kwargs,
            )

        # 8.3.2 (panel mi-rerank): tell the reranker who is asking. With a verified context the
        # query carries the context preamble and each document leads with a short YAML
        # applicability block (metadata-first so it survives the 4000-char cap), the matched
        # reason derived from the already-fetched stamped payload via the §D.4 matcher. The
        # candidate set is unchanged — eligibility ran in the SQL above (rule: enforced before
        # rerank, never widened by it). No context -> the bare query and body, byte-identical to
        # pre-8.3.2, so the fake reranker keeps zero lift and the context-free gold set is unmoved.
        rerank_query, docs, attributions = self._build_rerank_inputs(
            query, to_rerank, candidates, customer_context
        )
        reranked = self._reranker.rerank(rerank_query, docs, top_k=k)
        # 8.3.4 (panel mi-attrib): carry each hit's backend-assembled attribution (the §D.4
        # matcher reason, collapsed to the citation enum) through to the answer layer, which
        # copies it straight onto the Citation. No context -> every attribution is None.
        hits = [
            RetrievedHit(
                page_id=str(pid),
                chunk_id=candidates[pid].chunk_id,
                score=score,
                title=candidates[pid].title,
                url=candidates[pid].source_url,
                attribution=attributions.get(pid),
            )
            for pid, score in reranked
            if pid in candidates
        ]
        return hits, effective_scopes

    def _build_rerank_inputs(
        self,
        query: str,
        to_rerank: Sequence[int],
        candidates: dict[int, RerankCandidate],
        customer_context: CustomerContext | None,
    ) -> tuple[str, list[tuple[int, str]], dict[int, AttributionValue | None]]:
        """Build the ``(query, docs, attributions)`` for the cross-encoder (panel mi-rerank, 8.3.2;
        panel mi-attrib, 8.3.4).

        No verified context -> the bare query and each candidate's body text, byte-for-byte the
        pre-8.3.2 shape, and no attribution (every value None). With a context -> the context
        preamble prepended to the query, a YAML applicability block (its matched reason from the
        §D.4 matcher) ahead of each candidate's body, and that SAME matched reason collapsed to the
        citation attribution enum per candidate — one matcher call, reused for both the rerank
        YAML and the attribution (no recomputation). Only the already-eligible candidate set is
        used — never widened."""
        if customer_context is None:
            docs = [(pid, candidates[pid].text) for pid in to_rerank if pid in candidates]
            return query, docs, {}
        catalog = _catalog()
        rerank_query = build_rerank_query(context_preamble(customer_context), query)
        docs = []
        attributions: dict[int, AttributionValue | None] = {}
        for pid in to_rerank:
            candidate = candidates.get(pid)
            if candidate is None:
                continue
            payload = candidate.applicability
            reason = (
                match_applicability(customer_context, payload, catalog).reason if payload else None
            )
            attributions[pid] = attribution_for_reason(reason)
            yaml_block = applicability_yaml(payload, reason)
            docs.append((pid, build_rerank_document(yaml_block, candidate.text)))
        return rerank_query, docs, attributions

    def _trace(
        self,
        query: str,
        hits: Sequence[RetrievedHit],
        started: float,
        allowed_knowledge_scopes: Sequence[str] | None,
    ) -> int | None:
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
                allowed_knowledge_scopes=allowed_knowledge_scopes,
            )

    def retrieve(
        self,
        query: str,
        scope: str | None,
        k: int = 5,
        knowledge_scopes: Sequence[str] | None = None,
        customer_context: CustomerContext | None = None,
        session_labels: Sequence[str] | None = None,
    ) -> list[str]:
        started = time.perf_counter()
        hits, effective_scopes = self._search(
            query, scope, k, knowledge_scopes, customer_context, session_labels
        )
        self._trace(query, hits, started, effective_scopes)
        return [h.page_id for h in hits]

    def retrieve_with_context(
        self,
        query: str,
        scope: str | None,
        k: int = 5,
        knowledge_scopes: Sequence[str] | None = None,
        customer_context: CustomerContext | None = None,
        trace_query: str | None = None,
        session_labels: Sequence[str] | None = None,
    ) -> RetrievalResult:
        """Phase 4.2 entry point: hits carry chunk id + score + title/url, plus the trace row id.

        ``trace_query`` (substep 3.6.7, panel r5-image · C6): the value written to the
        ``query_trace`` row's ``raw_query``, when it must differ from the ``query`` actually
        searched. The search embeds/keyword-matches on ``query``; the trace records
        ``trace_query`` when given, else ``query`` (byte-identical to every pre-3.6.7 caller).
        The answer workflow uses this so an image turn can fold the vision transcription into
        ``query`` to DRIVE retrieval while the trace records only the text-only question — the
        transcription is memory-only and never persisted (never-bend rule 10, ADR-0009 C6)."""
        started = time.perf_counter()
        hits, effective_scopes = self._search(
            query, scope, k, knowledge_scopes, customer_context, session_labels
        )
        traced_query = trace_query if trace_query is not None else query
        trace_id = self._trace(traced_query, hits, started, effective_scopes)
        return RetrievalResult(hits=hits, trace_id=trace_id)

    def fetch_parent_texts(self, chunk_ids: Sequence[int]) -> dict[int, str]:
        """Each retrieved child chunk's parent text, keyed by chunk id (children retrieve, parents
        ground). Re-applies the source-scope GUC on this fresh session — a new transaction starts
        with no GUC set, and the chunk table is RLS-protected regardless of parent/child kind. The
        knowledge-scope GUC is set to the ``'*'`` wildcard: these ids already came from a scoped,
        permitted search (ADR-0014), so re-filtering by scope would risk dropping a legitimately
        authorized parent — but the GUC must still be set, else the RESTRICTIVE policy denies."""
        if not chunk_ids:
            return {}
        with self._session_factory() as session:
            apply_source_scope(session, self._allowed_sources)
            apply_knowledge_scope(session, None)  # '*': ids already authorized by the scoped search
            # 9.4.1 (panel mi-hardfilter): parent expansion is label-EXEMPT — the matched child
            # already passed the hard filter, and its parent shares the same page. Set the labels
            # GUC to the '*' opt-out so the RESTRICTIVE chunk_labels_read policy admits the parent
            # on this fresh txn (an unset GUC also opts out, but set it explicitly for safety).
            apply_allowed_labels(session, None)
            return fetch_parent_context(session, chunk_ids)
