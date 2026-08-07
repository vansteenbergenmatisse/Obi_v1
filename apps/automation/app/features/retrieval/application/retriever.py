"""Permission-aware hybrid retriever: dense ∥ keyword → RRF → permission filter → ranked pages.

Returns page ids (as strings, to match the eval id space) ranked by fused relevance, after removing
any page the caller scope may not see. Status is already enforced by the index (only current pages
have active chunks); permission is enforced here. Keyword rank breaks RRF ties so lexical relevance
wins when the dense signal is weak (e.g. the offline Fake embedder).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from app.features.retrieval.domain.fusion import reciprocal_rank_fusion
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.features.retrieval.infrastructure.search_repo import dense_search, keyword_search
from app.platform.clients import EmbeddingProvider


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
        *,
        candidate_k: int = 40,
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder
        self._policy = policy
        self._candidate_k = candidate_k

    def retrieve(self, query: str, scope: str | None, k: int = 5) -> list[str]:
        space_id = self._policy.space_id(scope)
        query_vec = self._embedder.embed([query])[0]
        with self._session_factory() as session:
            kw = keyword_search(session, query, space_id, self._candidate_k)
            dense = dense_search(
                session, query_vec, space_id, self._candidate_k, self._embedder.dim
            )

        kw_pages = _dedupe(kw)
        dense_pages = _dedupe(dense)
        fused = reciprocal_rank_fusion([kw_pages, dense_pages])
        kw_pos = {pid: i for i, pid in enumerate(kw_pages)}

        # tie-break by keyword rank so lexical relevance decides when RRF scores tie
        ranked = sorted(fused, key=lambda p: (-fused[p], kw_pos.get(p, 1_000_000), p))
        allowed = [p for p in ranked if self._policy.allowed(p, scope)]
        return [str(p) for p in allowed[:k]]
