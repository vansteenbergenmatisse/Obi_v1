# Phase 5 — Optimization & proof

**Status:** 5.1–5.3 ✅ done; 5.4+ ⬜ planned, blocked on API-spend go-ahead (`docs/rag/PLAN.md` lines
993–1200, 3121–3153).

## 5.1 — `CHAT_API_KEY` rotation mechanism ✅ done

`app/platform/config/settings.py` gained `chat_api_key_previous: str = ""`. `_verify_api_key`
(`app/features/rag_agent/server/router.py`) compares the caller's token against **both**
`chat_api_key` and `chat_api_key_previous` — both `hmac.compare_digest` calls always run, never
short-circuited, so a caller can't time-distinguish which one matched. `apps/automation/scripts/
rotate_chat_api_key.py` (`--apply` / `--finish` / preview-only default) drives the rotation;
`docs/runbooks/chat-api-key-rotation.md` documents the overlap-window procedure.

## 5.2 — Exact-match answer caching ✅ done

`app/features/rag_agent/application/answer_cache.py::CachingAnswerService` wraps any
`AnswerProvider` (normally `AnswerService`) with an in-process `TTLCache` (`app/shared/ttl_cache.py`,
extracted here from the pre-existing idempotency-cache pattern). Cache key is `sha256(json(full
history) + "|" + (principal or ""))` — the **full** history, not just the final turn, because rewrite
can use earlier turns as context; `principal` is part of the key so a hit can never leak one
principal's answer to another. Deliberately exact-match only — no semantic/similarity cache: a
threshold match risks serving a plausible-but-wrong cached answer, which conflicts with this project's
accuracy-first mandate, and there's no production traffic yet to tune a safe threshold against.

## 5.3 — Prompt-injection + permission/isolation red-team ✅ done

Deliberately **deterministic** — fake rewriter/generator collaborators, proving what the fixed
pipeline structurally cannot leak regardless of what an LLM is talked into producing (not a live-model
jailbreak test — that's 5.4). Four new `test_answer_service.py` tests confirm: a hostile query never
changes the `scope` passed to retrieval; a generator citing a marker beyond the retrieved-hit range is
stripped end-to-end; a generator that drops every citation degrades to refusal rather than leaking raw
text; the evidence block is built strictly from what retrieval returned, never from
query/rewritten-query text.

**A real finding, fixed:** `ChatRequestBody.principal` (`server/router.py`) was unvalidated free text
flowing into `PrincipalPermissionPolicy.allowed()`'s `scope` parameter — an all-digit `principal`
(e.g. `"100"`) was read as space-level trust, granting every page in that space regardless of
`page_restriction`. Fixed with a Pydantic `field_validator` rejecting all-digit `principal` values
(422) at the HTTP boundary — the domain-layer root cause was later closed properly at 4.6.6 (see
[phase-4.6.md](./phase-4.6.md)).

## 5.4 — ⬜ planned, blocked on go-ahead

Not yet built; gated by Phase 4.6's exit gate (met) and, separately, by an explicit API-spend
go-ahead not yet given. Scope, per `PLAN.md` and `evaluation/metrics/latency_metrics.py`'s already-
written (unwired) target constants:

- **Live-LLM adversarial matrix** — retrieved-content injection (a Confluence page whose text
  contains an embedded instruction), system-prompt exfiltration, multi-turn injection smuggled across
  history turns, and reranker relevance-poisoning (a real Cohere call scoring adversarially-crafted
  content) — all deferred from 5.3's deterministic pass because they need a real model call.
- **Latency/cost proof** — `evaluation/metrics/latency_metrics.py` already carries the targets
  (`TTFT_P50_TARGET_S=1.5`, `TTFT_P95_TARGET_S=2.5`, `END_TO_END_P95_TARGET_S=10.0`) as an unwired
  scaffold; 5.4 wires it against the real SSE endpoint.
- **Embedder bake-off** — OpenAI-3072 (incumbent) vs Voyage-3.x vs Qwen3-8B vs bge-m3, on a real gold
  set (not yet built). This is a **retrieval-and-ingestion** change: a new embedder changes what
  `HybridRetriever` embeds queries with here, and also requires the whole corpus to re-embed via the
  version-stamp gate documented in [`../ingestion/phase-2.md`](../ingestion/phase-2.md)'s incremental
  re-embedding section. Blocked on `VOYAGE_API_KEY` not being in `.env`.
- **Adaptive routing** (last) — classify query difficulty, route simple vs. decomposed queries, with
  optional HyDE/multi-query for hard queries only.
- `refusal_min_rerank_score` (0.10, set provisionally at 3.5.5) gets re-tuned here against real
  rerank-lift numbers.

## Files & folders used

- `app/platform/config/settings.py` — `chat_api_key_previous`.
- `app/features/rag_agent/server/router.py` — `_verify_api_key`.
- `apps/automation/scripts/rotate_chat_api_key.py`, `docs/runbooks/chat-api-key-rotation.md`.
- `app/features/rag_agent/application/answer_cache.py` — `CachingAnswerService`, `_cache_key`.
- `app/shared/ttl_cache.py` — `TTLCache`.
- `app/features/rag_agent/tests/test_answer_service.py`,
  `app/features/confluence_sync/tests/test_chat_endpoint.py`,
  `app/features/rag_agent/tests/test_pii.py` — 5.3's red-team tests.
- `app/features/evaluation/metrics/latency_metrics.py` — the unwired 5.4 target scaffold.

See [phase-4.6.md](./phase-4.6.md) for 4.6.6, the domain-layer fix that properly closed the root cause
5.3's HTTP-boundary validator only patched at one caller.
