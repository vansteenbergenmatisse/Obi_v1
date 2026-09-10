# 03 — Retrieval and Answer (the read path)

The read path turns a user question into a grounded, cited, streamed answer. It is a **fixed
workflow, not an agent loop** (ADR-0005): every stage is a plain function, so refusal and citation
enforcement are auditable and latency is bounded. Two features own it:
`app/features/retrieval` (hybrid search + rerank + permission) and `app/features/rag_agent` (the
answer runtime + `POST /chat`). The search runs as the non-owner **reader** role, so RLS is actually
enforced (see [`05-security-isolation.md`](./05-security-isolation.md)).

The stage order **as it actually runs** (`AnswerService.answer`, answer_service.py:165-332):

```
POST /chat → auth + rate-limit + validate → [small-talk?] → [clarification?] → rewrite
  → embed → dense ∥ keyword (RLS + knowledge-scope scoped) → RRF → principal ACL filter
  → cross-encoder rerank (≤75 → k) → CRAG retry (if weak) → refusal check
  → parent-context expansion → grounded generation → enforce citations → (+ image analysis)
  → SSE stream + write query_trace
```

Note on ordering: DESIGN.md lists refusal *before* CRAG, but the runtime runs CRAG *before* the
refusal decision — refusing before attempting the corrective retry would defeat its purpose. This doc
reflects the runtime order.

## 1. `POST /chat` — the HTTP + LLM surface

Handler `post_chat` (`router.py:428-450`), `@router.post("/chat")`, returns a
`StreamingResponse(media_type="text/event-stream")` (router.py:447-450). Both an HTTP and an LLM
surface, so it carries the full `securing-http-and-llm-endpoints` control set (ADR-0005 decision 10):

| Control | Mechanism | Anchor |
|---|---|---|
| C1 Auth | `_verify_api_key`: Bearer token; **fail-closed 503** if `chat_api_key` unset; constant-time `hmac.compare_digest` vs current **and** previous key (both compares always run, for rotation overlap); 401 on mismatch | router.py:254-267, 435 |
| C2 Rate limit | `SlidingWindowRateLimiter(chat_rate_limit_per_minute=20, max_tracked_keys=1000)`; **key is client-IP only, never the principal**; 429 over limit | router.py:232-240, 270-276, 437-439 |
| C3 Input validation | `ChatRequestBody` (`extra="forbid"`): history ≥1 turn, must end on a `user` turn; per-turn `content` ≤ `chat_max_message_chars` (4000); turn count ≤ `chat_max_history_turns` (20); numeric-principal rejected; `knowledge_scope` slug-validated (`^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$`); per-turn image count ≤ 4, per-image bytes ≤ 5 MB | router.py:164-199, 279-307 |
| C4 Timeout/retry/breaker | Anthropic client `answer_timeout_seconds=30`, `answer_max_retries=2`, `answer_breaker_threshold=5` | settings.py:115-117 |
| C5 Output cap | Answer text capped at `chat_output_max_answer_chars` (8000) before streaming | router.py:392 |
| C6 PII redaction | `redact_pii` over the assembled prompt on every LLM call (text only — **not** image bytes) | pii.py:39-45; llm_client.py:111,136,146,164 |
| C7 Idempotency | optional `Idempotency-Key` header → `TTLCache`; key = `sha256(key | history | principal | knowledge_scope)` | router.py:243-251, 310-331 |
| C9 Audit logging | structured `chat_request` log incl. `refusal_reason`; secret never logged | answer_service.py:245-268 |
| C10 Cost/abuse caps | per-call `max_tokens` (rewrite 200, answer 800, small-talk 150, image 500); Anthropic abuse cap on `user_text` | llm_client.py:45-52 |

**SSE lifecycle** (`_stream_answer`, router.py:345-425): `start` → `token` deltas → `citations` →
`done`. Each event is `data: {json}\n\n` (router.py:334-335). Answer is **chunked-replay** of the
fully citation-enforced text (not per-model-token streaming): sliced by `chat_token_chunk_chars`
(40), paced `chat_stream_interval_ms` (15 ms). A generation failure after the 200 is committed
surfaces as an SSE `error` event, not a 5xx (router.py:373-377). `imageAnalysis` rides only on `done`.

**Feedback:** `patch_chat_feedback` (`@router.patch("/chat/{trace_id}/feedback")`, router.py:453-469),
body `feedback: Literal[-1, 1]`, same auth + rate limit, updates the same trace row via the writer
engine.

## 2. Pre-pipeline short-circuits

Before any retrieval, `AnswerService.answer` checks two branches (both skip retrieval and write no
`query_trace` row):

- **Small talk** (`is_small_talk`, small_talk.py:24-94) — a closed exact-match frozenset over the
  whole normalized message (trailing `!.?` stripped, whitespace collapsed). A match returns a
  `generate_small_talk` reply (answer_service.py:177-179). A real question that merely happens to be
  short does **not** match (whole-message exact match, not substring). Small talk runs **first**, so a
  message that is arguably both small talk and ambiguous resolves as small talk (ADR-0008 tie-break).
- **Clarification** (`decide_clarification`, clarification.py:100-116) — gated behind
  `enable_clarification_branch` (default off, ADR-0008). Heuristic first: empty ⇒ not ambiguous;
  ≥12 words ⇒ not ambiguous; otherwise one cheap LLM classifier call. If ambiguous, returns
  `Answer(needs_clarification=True, refused=False)` with a clarifying question — an open conversation
  turn, deliberately **not** a refusal. Both classifier and generator fail *open* to non-ambiguous /
  a static fallback on `AnthropicError`.

## 3. Query rewrite

When the last turn has non-empty text and `rewrite_enabled` (default true), `AnthropicQueryRewriter.rewrite`
turns multi-turn history into a standalone query — one cheap `routing_model`
(`claude-haiku-4-5-20251001`) call, `max_tokens=200` (llm_client.py:45, 103-117). Single-turn history
skips the call; an `AnthropicError` fails **open** to the verbatim last turn. The rewritten query is
stored on the trace.

## 4. Embed + hybrid search

`HybridRetriever._search` (retriever.py:120-190) runs inside one reader-role transaction:

1. **Embed the query** — `self._embedder.embed([query])[0]` (retriever.py:126). Same provider as
   ingestion. An empty text-only turn never embeds (the provider rejects empty strings) — the
   pipeline builds an empty result instead (answer_service.py:230-237).
2. **Set per-transaction GUCs** — `apply_hnsw_gucs` sets `SET LOCAL hnsw.ef_search=100` and
   `hnsw.iterative_scan='relaxed_order'` (whitelisted mode, search_repo.py:21-35); `apply_source_scope`
   runs `SELECT set_config('app.allowed_sources', :s, true)` with the **bound** comma-joined source
   list (search_repo.py:38-49). An empty source list ⇒ default-deny (zero rows).
3. **Dense ∥ keyword** — the `∥` is *conceptual*: the two are independent ranking signals, but they
   run **sequentially** in the one synchronous transaction (keyword first, then dense,
   retriever.py:143-154 — the module docstring's "parallel" is aspirational).
   - **Dense** (`dense_search`, search_repo.py:107-136): cosine `<=>` over the HNSW index, `ORDER BY
     dist ASC, page_id ASC LIMIT candidate_k`. Casts both sides to `halfvec(dim)` when
     `dim >= 2001` (`_HALFVEC_MIN_DIM`, search_repo.py:17) — **the deployed path, since `.env` sets
     `EMBEDDING_DIM=3072`**; at the `settings.py` default of 1024 it would use plain `vector` (see
     `01-system-overview.md`).
   - **Keyword** (`keyword_search`, search_repo.py:79-100): `ts_rank(tsv, …)` over the GIN index with
     an OR-converted `plainto_tsquery` (`&` rewritten to `|`, search_repo.py:76, 88-90), `ORDER BY
     score DESC, page_id ASC`.
   - Both carry `_base_filters` (search_repo.py:52-70): `is_active AND kind=1 AND page_status='current'`,
     plus `space_id = :space_id`, `source_id = ANY(:sources)` (explicit predicate alongside RLS), and
     the knowledge-scope `tags && :knowledge_scopes` overlap.
   - `candidate_k` default **75** (retriever.py:95).

## 5. RRF fusion

`reciprocal_rank_fusion` (fusion.py:14-28): `score = Σ weight / (k0 + rank)`, 1-based rank,
**`k0 = 60`** (fusion.py:18, 27). Called as `[kw_pages, dense_pages]` (keyword list first,
retriever.py:158). Ties broken by keyword rank then page id
(`sorted(..., key=lambda p: (-fused[p], kw_pos.get(p, 1e6), p))`, retriever.py:159-162).

## 6. The three security filters (order)

1. **Source RLS** — applied up front via the `app.allowed_sources` GUC + the explicit
   `source_id = ANY(:sources)` predicate (retriever.py:142; search_repo.py:38-49, 63). Isolates whole
   source systems. Default-deny.
2. **Knowledge-scope tag filter** — in-SQL during search via `tags && :knowledge_scopes`
   (search_repo.py:64-69), backed by `ix_chunk_tags_gin`. **Double-gated:** only applied when the
   `enable_knowledge_scope_filtering` construction flag is on AND the caller passed scopes; with the
   flag off, no predicate regardless of caller input (retriever.py:116, 128-132). A chunk with empty
   `tags` overlaps nothing and drops out.
3. **Page-principal ACL** — after fusion, on the candidate set only: `fetch_page_scopes(session,
   ranked)` loads each page's `space_id` + `page_restriction` principals fresh (search_repo.py:187-212),
   builds a request-scoped `PrincipalPermissionPolicy`, and filters (retriever.py:167-171).
   `classify_scope` (permission.py:30-37) interprets the incoming scope once: all-digits ⇒ space-level
   trust `(space_id, None)`; otherwise `(None, principal)`. `allowed` (permission.py:46-52): if a
   space is set, the page must be in it; if principal is `None`, only unrestricted pages; else
   unrestricted OR the principal is in the page's restriction set.

**Security-critical invariant:** permission filtering runs **before** rerank — the cross-encoder never
scores a document the principal cannot see (retriever.py:173-176; ADR-0005 decision 3).

**Recall note — the page-principal ACL is a *post-fusion* filter.** Source RLS is correctly
*pre-filtered* (in-SQL during search, §6.1), but the principal ACL runs *after* fusion and before
rerank (ADR-0005), on the already-fused candidate set. The implication: a heavily-restricted principal
can be left with **fewer than k candidates** if most of the top-fused pages are filtered out. This is
accepted today — measure before changing; over-fetch `candidate_k` only if thin results are actually
observed.

## 7. Cross-encoder rerank

`to_rerank = allowed[: rerank_depth]` (default 75, retriever.py:175); rerank texts come from
`fetch_rerank_texts` — one representative child per page, `left(title || ' ' || retrieval_content,
4000)` (search_repo.py:149-184). `self._reranker.rerank(query, docs, top_k=k)` with `k` from the
caller (default `retrieve_k=5`, answer_service.py:139). Provider: **Cohere `rerank-v3.5`**
(`CohereReranker` → `POST https://api.cohere.com/v2/rerank`, reranker_client.py:74, 114-127) with
timeout/retry/breaker and an abuse cap of `rerank_max_docs=1000`; retryable on `{408,409,429}` and
≥500 with backoff `min(0.3·2^n, 4)`. `FakeReranker` (order-preserving) fires offline / on an empty key,
making CI deterministic (before == after ⇒ zero rerank lift).

**`rerank-v3.5` is prior-generation as of 2026.** Cohere's current line is `rerank-v4.0-pro` /
`-fast`, with billing moved to per-token; other 2026 rerank leaders include Voyage rerank-2.5 and
Zerank-2. We still run **v3.5** — this doc does not claim a migration. Moving is **pending
corpus-specific eval validation** and is coupled to re-tuning the refusal threshold (§8): a new
reranker emits a different score distribution, and the `0.10` cut is calibrated to v3.5's — so the
model swap and the threshold retune must land together, both gated on the Phase 5.4 gold set.

## 8. Refusal threshold

`decide_refusal(top_score, refusal_min_rerank_score=0.10, has_image)` (answer_service.py:243;
refusal.py:41-58): if `has_image` ⇒ never refuse (the image alone may answer); if `top_score is None`
⇒ refuse `no_candidates`; if `top_score < threshold` ⇒ refuse `weak_score`; else proceed. `top_score`
is the top reranked hit's score (retriever.py:73-74). A refusal skips generation entirely, logs a
`human_handoff` record, and renders **distinct copy per reason** (the three-value taxonomy
`no_candidates | weak_score | no_citations`, refusal.py:30; ADR-0008). The `0.10` threshold is a
**conservative provisional** set from the Phase 3.5.5 fixture and explicitly flagged for re-tuning on
a real Phase-5 gold set (DESIGN §5).

## 9. One CRAG corrective retry

`_apply_crag_retry` (answer_service.py:334-358), `crag_max_retries=1`. It runs **between retrieval and
the refusal check**. No-op if retries ≤ 0, if the rewrite equalled the original query, or if the first
result already scored ≥ threshold. Otherwise it retries once with the **user's verbatim
`original_query`** (in case the rewrite hurt retrieval), same scope, same `k`, same already-resolved
knowledge-scope allow-list, and keeps whichever result scored higher (answer_service.py:347-357). Not
an agent loop — a fixed, bounded workflow (ADR-0005 decision 8).

## 10. Parent-context expansion

Children retrieve; **parents ground**. `fetch_parent_texts([h.chunk_id …])` (answer_service.py:279 →
retriever.py:242-250) re-applies the source-scope GUC on a fresh session and joins `chunk c JOIN chunk
p ON p.id = c.parent_chunk_id`, returning each parent's **`display_content`** keyed by child id
(search_repo.py:215-232). The parent text — not the matched child — is what feeds the generator, so
the model has enough surrounding context.

## 11. Grounded generation + forced citations

`build_evidence_block(evidence_hits, parent_texts)` renders `[marker] title\n<parent text>` blocks,
markers = 1-based hit position (prompt.py:161-167). `AnthropicAnswerGenerator.generate` calls
`answer_model` (`claude-sonnet-5`), `max_tokens=800`, with a **prompt-cached** system block
(`ANSWER_SYSTEM_PROMPT`, prompt.py:37-78) instructing "answer ONLY from the numbered evidence" and
"cite every factual claim with its marker." Generation errors **propagate** (no fail-open here — an
ungrounded answer is worse than an error).

**Enforcement is in code, not prompt-trust:** `enforce_citations(raw_answer, valid_markers)`
(citations.py:27-43) splits into sentences and keeps a sentence only if it cites ≥1 valid numbered
marker; invalid/hallucinated markers are stripped from survivors. If **no** markers survive, the
answer degrades to a `no_citations` refusal rather than returning ungrounded text
(answer_service.py:293-314). Surviving markers build the `Citation` list.

**Limitation — marker validity, not entailment.** Enforcement verifies that each surviving sentence
cites a *valid numbered marker*; it does **not** verify that the cited parent text actually supports the
claim. A well-formed citation on an unsupported sentence still passes. The 2026 best-practice upgrade is
a **sampled semantic-entailment / groundedness check** over `(claim, cited_passage)` pairs — this is
the planned/considered next step. It can run **sampled or async-for-monitoring** rather than inline, so
the streamed hot path stays fast while groundedness is tracked over time.

## 12. Curated-knowledge layer (always-present)

`_fetch_curated_entries(allowed_scopes)` (answer_service.py:360-369) — no-op if no reader session.
`fetch_curated_entries` (curated_knowledge_repo.py:19-32): `SELECT … FROM curated_knowledge_entry
WHERE is_active AND (tags = '{}' OR tags && :allowed_scopes) ORDER BY id LIMIT
:curated_knowledge_max_entries` (default 5). Empty `tags` ⇒ applies to every scope. Curated hits are
**prepended** to retrieved hits (`evidence_hits = [*curated_hits, *result.hits]`,
answer_service.py:276-278) so they get markers `[1..k]` and retrieved hits `[k+1..n]`. Each curated hit
gets a synthetic `page_id="curated:<id>"` and a **negative** `chunk_id = -entry.id` so it never
collides with real ids (curated_knowledge.py:33-54), and its body is injected into `parent_texts`
under that negative id. It rides through the identical evidence/citation machinery — so curated
knowledge is grounded and citation-enforced exactly like retrieved evidence, with zero new citation
logic (ADR-0011 decision 7). **Note:** `curated_knowledge_entry` has no RLS; tag filtering is its only
access control.

## 13. Vision / image analysis (ADR-0009)

`has_image = bool(history[-1].images)` (answer_service.py:174). An image-bearing turn still runs the
full text-retrieval path; what changes is (a) `decide_refusal` will not refuse on `weak_score`/
`no_candidates` when `has_image` (refusal.py:52-53), and (b) a **second, independent** generation call
`generate_image_analysis(original_query, images)` runs (answer_service.py:239-241). That call
(`llm_client.py:154-171`) sends the image content blocks with `IMAGE_ANALYSIS_SYSTEM_PROMPT` (which
includes a prompt-injection defensive instruction, prompt.py:92-99), `max_tokens=500`, and fails
**open** to a short notice on error. Its output is **never** passed through `enforce_citations` and
never carries a citation marker — so an image can never forge a fake Confluence citation. It rides on
`Answer.image_analysis` and streams over `token` events, delivered on `done`. Image bytes are **not**
PII-redacted (a disclosed, accepted gap — llm_client.py:154-159, pii.py:15-19). Small-talk and
clarification branches silently drop any attached images.

## 14. Tracing

`HybridRetriever._trace` (retriever.py:193-215) writes one `query_trace` row on a separate **writer**
session (`trace_sessionmaker`) so RLS never blocks the insert (trace_repo.py:1-8). It records
`raw_query`, `retrieved_page_ids`, `retrieved_chunk_ids`, `rerank_scores`, `allowed_sources`,
`embedding_model`, `reranker_model`, `latency_ms`, and `allowed_knowledge_scopes` (the isolation audit
trail). The answer runtime then updates the same row with `rewritten_query`, `answer`, `citations`
(`update_query_trace_answer`, trace_repo.py:51-66); feedback updates it later. Small-talk and
clarification write no trace row.

## 15. Answer caching (PLAN 5.2)

`CachingAnswerService` decorates `AnswerService` with exact-match caching only (semantic caching
deliberately deferred — no traffic to tune a threshold). Cache key = `sha256(history | scope |
knowledge_scope)` (answer_cache.py:46-57) — both `scope` (principal) and `knowledge_scope` are bound
into the key to prevent cross-principal / cross-scope replay leaks. `TTLCache(chat_answer_cache_ttl_seconds=300,
chat_answer_cache_max_entries=500)`.

## 16. Evaluation & monitoring (2026 posture)

**Component-level eval is the 2026 consensus** — score retrieval and generation *separately* rather
than end-to-end only:

- **Retrieval metrics** — recall@k, context relevance (did the right passages come back?).
- **Generation metrics** — groundedness/faithfulness and answer relevance (did the answer stay on the
  evidence and address the question?).

Together these are the "RAG triad" (context relevance + groundedness + answer relevance). **The gold
set does not exist yet** (Phase 5.4), and it is the shared unblocker: the *same* gold set tunes the
embedder bake-off (§7 of `02-ingestion.md`), the reranker migration (§7 above), and the refusal-threshold
retune (§8). **LLM-as-judge caveats** apply when we build it: use a *different* judge model than the
generator, run each judgment 2–3× to measure variance, and validate any machine-generated test cases
before trusting them. Finally, wire **index-freshness / held-out recall telemetry** as ongoing
monitoring — it is the mitigation for the #1 warned 2026 RAG failure: silent staleness and silent
recall loss under filtering (a corpus that quietly stops covering the questions, or filters that quietly
starve recall).

## 17. Considered and rejected

**Adaptive / query-complexity routing** and **MMR / contextual-compression** were evaluated and are
**not** adopted. They are 2026-emerging techniques aimed at large, noisy, high-variance-traffic corpora;
our design is the opposite — a fixed, auditable workflow (ADR-0005) plus CRAG (§9) over a curated,
deduplicated, modest-scale corpus with an accuracy-first posture. The complexity they add is not
justified until an eval shows retrieval quality or diversity is actually the bottleneck.
