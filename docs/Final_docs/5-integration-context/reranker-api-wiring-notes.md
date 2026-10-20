# Research · the reranker API as actually wired (feeds §D.6) — 2026-10-05

> **Status: research notes, read-only findings.** Produced by a read-only inspection pass
> (owner-ordered parallel batch, 2026-10-05) so the §D.6 context-aware-reranking build starts
> from facts. Nothing here changed code. Line numbers are anchors as of writing; trust symbol
> names over numbers.

## 1. What is wired

- **Provider/model:** Cohere **`rerank-v3.5`** via the **v2 `/rerank`** endpoint over raw
  `httpx` — no vendor SDK. Client: `backend/app/platform/clients/reranker_client.py`
  (`CohereReranker._URL = "https://api.cohere.com/v2/rerank"`, line 74).
- Three backends behind the `Reranker` Protocol (lines 44–52): `FakeReranker` (identity,
  order-preserving, offline/CI default), `CohereReranker`, `LocalReranker`
  (sentence-transformers CrossEncoder, optional). Factory `build_reranker` (lines 180–200).
- Settings (`backend/app/platform/config/settings.py:125–138`): `reranker_provider=""`
  (→ fake offline), `reranker_model="rerank-v3.5"`, `rerank_candidate_k=75`, `rerank_depth=75`,
  `rerank_top_k=5`, `rerank_timeout_seconds=30`, `rerank_max_retries=3`,
  `rerank_breaker_threshold=5`, `rerank_max_docs=1000` (C10 cap).
- **ADR-rerank-then-verify-cited-answers boundary:** cross-encoder rerankers only — never a chat model asked to reorder.
  There is no "system prompt" to give; the tool class doesn't have one.

## 2. The exact request body sent today

`CohereReranker._post_with_retry` (reranker_client.py:114–127) sends **only**:

```json
{ "model": "rerank-v3.5", "query": "<rewritten question>", "documents": ["<text>", ...], "top_n": 5 }
```

No `rank_fields`, `max_tokens_per_doc`, `return_documents`, instruction or context field.

Each document string is built by `fetch_rerank_texts`
(`backend/app/features/retrieval/infrastructure/search_repo.py:191–226`): one representative
child chunk per page (`DISTINCT ON (page_id) … ORDER BY page_id, seq`), text =
**`left(title || ' ' || retrieval_content, 4000)`** — a raw blob, chars not tokens, no
metadata. The query is the bare rewritten question (`retriever.py:181–184`). This is exactly
the gap §D.6 closes.

## 3. What Cohere's API actually supports (official docs, checked 2026-10-05)

- **v2 (what we call):** `model`, `query`, `documents` (**documented as strings only**),
  `top_n`, `max_tokens_per_doc` (default 4096, auto-truncates long docs). **No instruction /
  context / system-prompt field exists in any version.** v2 replaced `max_chunks_per_doc`.
- **v1 only:** documents as JSON objects + **`rank_fields`** (ordered, non-commutative; default
  `text`). Cohere's guidance for structured data: YAML-formatted strings perform best.
- Limits: query capped at **2,048 tokens** on v3.x (16,384 on `rerank-v4.0-pro`); ≤1,000 docs
  recommended per request. We send ≤75 — far inside.
- Sources: docs.cohere.com/reference/rerank (v2) · /v1/reference/rerank ·
  /v1/docs/reranking-best-practices · /changelog/rerank-v3.5.

## 4. The load-bearing invariant

**Eligibility is enforced before rerank; rerank only reorders.** Pipeline order in
`HybridRetriever._search` (`retriever.py:119–196`): SQL-filtered dense ∥ keyword search
(active/current/source/scope filters + RLS GUCs in-txn) → RRF fusion → page ACL
(`PrincipalPermissionPolicy`) → `to_rerank = allowed[:rerank_depth]` →
`fetch_rerank_texts` **in the same txn under the same scope** → rerank. Locked by
`backend/app/features/retrieval/tests/test_torerank_handoff.py`. Any §D.6 enrichment must
build from the already-eligible candidate set only.

Downstream couplings that move if rerank inputs change:
- **Refusal thresholds** (`refusal_min_rerank_score=0.05`, `offtopic_max_rerank_score=0.035`,
  settings.py:140–162; `decide_refusal` in `answer_service.py:269–311`) are tuned to today's
  score distribution — enrichment shifts it → **re-tune on the gold set, rule-11 before/after
  numbers mandatory**.
- CRAG weak-score retry (`_apply_crag_retry`, answer_service.py:385–409) keys on the same
  threshold; never widens scope.
- Trace writes `rerank_scores` + `reranker_model` per query.

## 5. Options for §D.6, ranked

1. **(a) Prepend verified context to the `query` string — recommended, lowest risk.** Works on
   v2 as-is. Keep the preamble tight (2,048-token query cap on v3.5), or move to
   `rerank-v4.0-pro` if it grows.
2. **(b) Embed applicability metadata into each document string — recommended, complements
   (a).** Short YAML block ahead of `title + retrieval_content` in `fetch_rerank_texts`.
   Watch the 4000-char SQL truncation (metadata competes with body for the budget; consider
   metadata-first and/or sending `max_tokens_per_doc` explicitly).
3. **(c) `rank_fields` + JSON documents — escalation only.** v1-documented, v2 support
   undocumented; means switching endpoint or empirically proving v2 acceptance; large blast
   radius (body, `_parse`, every fake, the contract test).
4. **(d) Model swap (`rerank-v4.0-pro`)** — only buys query-token headroom for (a); still
   instruction-less; ADR-rerank-then-verify-cited-answers forbids an LLM reranker regardless.

**Recommended combination: (a) + (b)**, keep the v2 string contract, re-tune thresholds,
record gold-set before/after.

## 6. What the §D.6 substep must touch besides code

- **`docs/Final_docs/retrieval/rerank.md` does not exist yet** — per the retrieval README rule
  it must be written from current code *before* the component is touched, updated in the same
  change.
- Test seams that change: `FakeReranker` + the `Reranker` Protocol (if the signature grows);
  `_SpyReranker` (`confluence_sync/tests/test_retrieval_eval.py:209–219`) is the seam to assert
  enriched text reaches the reranker; the exact-body contract test
  `test_cohere_sends_v2_shape_and_maps_indices_back_to_page_ids`
  (`platform/clients/tests/test_reranker_client.py:69–98`) **will intentionally break** and
  must be updated; `test_torerank_handoff.py` must keep passing; the eval-lift fixtures assume
  the fake yields zero lift (before == after) — preserve that property.
