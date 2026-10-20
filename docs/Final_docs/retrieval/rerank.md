# Reranking (the cross-encoder stage)

- **Workflow:** retrieval
- **Owning code:**
  `backend/app/platform/clients/reranker_client.py` (the `Reranker` protocol +
  `FakeReranker` / `CohereReranker` / `LocalReranker` backends and the `build_reranker`
  factory — the hosted v2 `/rerank` call);
  `backend/app/features/retrieval/infrastructure/search_repo.py`
  (`fetch_rerank_texts` — the one representative child chunk per permitted page that the
  reranker scores);
  `backend/app/features/retrieval/application/retriever.py`
  (`HybridRetriever._search` / `_build_rerank_inputs` — slices the permitted candidates to
  `rerank_depth`, fetches their text in the same transaction and under the same scope, builds
  the 8.3.2 enrichment, and calls the reranker);
  `backend/app/features/retrieval/domain/rerank_enrichment.py` (the pure 8.3.2
  request-construction helpers: `context_preamble`, `build_rerank_query`,
  `applicability_yaml`, `build_rerank_document`).
- **Design panel:** `mi-rerank` (section 05.2 · Multi-integration context)
- **Status:** Unverified (context-aware reranking is coded and unit/eval-proven; no live
  customer token carries slots yet, so the enrichment has never run in production — Phase A
  validates live. The single-integration reranker underneath is Implemented.)

## What it does

After hybrid search, RRF fusion and the locks (source-scope RLS and page ACL, plus the
routing-label RLS/filter that replaced the retired knowledge-scope lock — ADR-routing-labels-sole-content-axis) have produced a
permitted, de-duplicated page ranking, the retriever slices the top `rerank_depth` pages (default
75) and asks `fetch_rerank_texts` for one representative child chunk per page — the earliest active
child under the exact same pre-model filters as search (active / child / current, source list,
routing-label overlap, and since 8.3.1 the applicability predicate), so a page the filters would
exclude can never be reranked back in.
Each page's document string is `left(title || ' ' || retrieval_content, 4000)` — title plus
the matched child's content, truncated to 4000 characters in SQL.

The retriever then hands `(query, [(page_id, text), ...], top_k)` to the injected reranker.
The reranker returns `(page_id, relevance_score)` best-first, capped at `top_k`. Three
backends sit behind one `Reranker` protocol: `FakeReranker` (identity — preserves input
order, scores by descending input rank; the offline/CI default and the zero-lift baseline),
`CohereReranker` (the hosted `rerank-v3.5` cross-encoder over the Cohere v2 `/rerank`
endpoint, raw `httpx`, no vendor SDK), and `LocalReranker` (an optional
sentence-transformers CrossEncoder). The v2 request body carries only
`{model, query, documents, top_n}` — the v2 API has no instruction, context or system-prompt
field in any version (see `docs/Final_docs/5-integration-context/research-rerank-api.md`).
The reranked order feeds the refusal thresholds (`refusal_min_rerank_score`,
`offtopic_max_rerank_score`) and the CRAG weak-score retry in `rag_agent`'s
`answer_service`, and the per-query trace records `rerank_scores` and `reranker_model`.

### Context-aware enrichment (substep 8.3.2, panel mi-rerank)

Because the v2 API has no instruction field, the only way to tell the cross-encoder *who is
asking* is through the two string inputs it accepts (research options a+b). When a request
carries a verified `CustomerContext`, `_build_rerank_inputs` enriches both:

- **(a) the query** — a one-line verified-context preamble is prepended, e.g.
  `Customer setup: POS=toast; PMS=mews; platform=datahub.` ahead of the rewritten question.
  The preamble names only the filled §D.13 slot product ids and the host platform key (public
  catalog vocabulary — never a company id, token or secret, rule 10). The user question is
  **never** truncated: the query cap is 2,048 tokens, and if the combined string ever
  approached it the preamble yields first.
- **(b) each document** — a short YAML applicability block leads, ahead of the title+content
  body, e.g.

  ```
  applies-to:
  - level: platform-interface
    product: toast
    platform: datahub
  matched-rule: platform-interface:pos
  ```

  The block derives from the chunk's stamped applicability payload (the page-authored
  "Applies to" table) plus the matched eligibility reason from the §D.4 matcher
  (`match_applicability`) — no new vocabulary. A label-only chunk (no applicability record)
  carries no block. The YAML is **metadata-first** so it survives the 4,000-char document cap;
  only the body tail is truncated after it.

This is **request construction, not a prompt** — no model is asked to reason or generate here
(ADR-rerank-then-verify-cited-answers keeps the reranker a cross-encoder), so the helpers live in the retrieval domain and
no prompt text leaves `rag_agent`. Eligibility is enforced in the search SQL before this point
(8.3.1); the enrichment only changes how the already-eligible candidates are scored and
ordered — it is built from that exact candidate set and never widens it. With no context the
query and documents are byte-identical to the pre-8.3.2 shape, so the fake reranker keeps zero
lift and the context-free gold set is unmoved; the refusal thresholds and CRAG trigger
therefore needed no re-tuning (the only gold set available carries no context — context-
carrying cases land in Step 6). Page-authored values are treated as untrusted when they enter
the document string: validated against the catalog vocabulary at stamp time (8.2.1) and
additionally sanitized (newlines/control characters stripped, length bounded) so a hostile
value cannot introduce a second YAML line; the block is only ever a cross-encoder document
string — never executed, never interpolated into SQL.

The hosted call is wrapped in the same security discipline as the embeddings client: a C4
timeout, a bounded retry with exponential backoff, a consecutive-failure circuit breaker,
and a C10 per-call document-count abuse cap. `build_reranker` falls back to `FakeReranker`
when the provider is empty/`fake`, or when the key is missing in an offline env, so CI stays
deterministic even with a live key in `.env`; in a non-offline env a missing key raises.

## Why it does it

Children retrieve, parents ground: the cross-encoder scores the exact child chunk that
matched (rule 6 — the matched chunk is what the reranker scores and what expands to a
parent), never a stand-in. Rerank runs *after* the locks, in the application layer, on
the fused candidate set — a document the routing-label filter or ACL excludes is never scored
(ADR-rerank-then-verify-cited-answers),
and `fetch_rerank_texts` carries the same filters in the same transaction so the reranked set
is a strict subset of what access and eligibility already permit. ADR-rerank-then-verify-cited-answers also fixes the
tool class: a cross-encoder reranker only — never a general chat model asked to reorder —
which is why there is no prompt here and why the v2 string contract (no instruction field) is
the researched path rather than a workaround.

The `FakeReranker` identity backend exists so retrieval is reproducible offline and so the
eval harness's rerank-lift measurement has an honest zero-lift floor (before == after when
the fake scores). The depth cap (`rerank_depth`, owner-confirmed 75 in
`docs/plan/decisions.md`) and the document-count abuse cap bound cost and blast radius.

## How we know it works

- **Unit** (`backend/app/platform/clients/tests/test_reranker_client.py`): the fake is
  deterministic and order-preserving (`test_fake_is_deterministic_order_preserving_and_truncates`),
  satisfies the protocol, and the Cohere backend sends the exact v2 body and maps result
  indices back to page ids (`test_cohere_sends_v2_shape_and_maps_indices_back_to_page_ids`),
  opens the breaker after the threshold, retries a retryable status, enforces the abuse cap,
  and the factory selects the right backend per provider/key/env.
- **Unit** (`backend/app/features/retrieval/tests/test_torerank_handoff.py`, panel
  r3-torerank): only candidates that survived all three locks are sliced to `rerank_depth`,
  and their text is fetched in the same transaction and under the same scope as the searches
  that produced them — a page-ACL-restricted candidate never reaches the reranker.
- **Unit** (`backend/app/features/confluence_sync/tests/test_retrieval_eval.py`): the page
  ACL filter runs before rerank in the application layer (`_SpyReranker` proves the
  restricted page's text never enters the reranker's input).
- **Unit** (`backend/app/features/retrieval/tests/test_rerank_enrichment.py`, panel
  mi-rerank, 8.3.2): the context preamble prepends and the user question is never truncated
  (the preamble yields at the 2,048-token cap); an empty context yields a bare query and no
  YAML (byte-identical to pre-8.3.2); the YAML block leads and survives the 4,000-char cap
  (body tail truncated after it); the YAML derives from the stamped payload + matched reason,
  and a hostile page-authored value is sanitized (no injected second YAML line).
- **Unit** (`backend/app/features/retrieval/tests/test_rerank_context_wiring.py`, panel
  mi-rerank, 8.3.2): with a verified context the spy reranker sees the enriched query and
  YAML-prefixed documents (a label-only chunk carries no YAML), the candidate set is never
  widened; with no context it sees the bare query and bare bodies.
- **Unit** (`backend/app/platform/clients/tests/test_reranker_client.py::test_cohere_sends_v2_shape_and_maps_indices_back_to_page_ids`):
  the enriched body reaches the v2 wire verbatim — preamble-first query, YAML-leading
  documents — and the v2 string contract is still exactly `{model, query, documents, top_n}`
  (no instruction field).
- **Eval** (`make eval`, rule 11): the rerank-lift report records precision@5 and ndcg@10
  before vs after the cross-encoder; CI's `FakeReranker` yields zero lift (the honest floor
  in `docs/plan/baseline.md`). After 8.3.2 every gold-set number is identical to the floor —
  the bundled runner carries no customer context, so the enrichment is invisible to it and the
  thresholds needed no re-tuning.
- Not yet proven: no live token carries slots yet (platforms don't mint the structured
  context), so the enrichment has never shifted a real score distribution; context-carrying
  gold cases (Step 6) and Phase A (8.5.2) provide the live evidence.
