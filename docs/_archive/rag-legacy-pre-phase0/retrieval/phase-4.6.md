# Phase 4.6 — Fixes-backlog remediation (retrieval/chat-relevant sub-steps)

**Status:** ✅ done (`docs/rag/PLAN.md` lines 2135–2935). Six independent audit agents re-ran
tests/boundaries/ruff/pyright live and read code directly across Phases 0–4 on 2026-08-10, finding a
CRITICAL access-control bypass and a HIGH cross-principal leak in phases the ledger had already marked
"done." Only the retrieval/chat-relevant sub-steps are covered here.
**Ingestion-side sub-steps** (4.6.1 Confluence group-restriction fail-closed, 4.6.2 group-membership
expansion, 4.6.5 `rollback_to`'s stale hashes, 4.6.7 Confluence client hardening, 4.6.11 event dedup,
4.6.13 attachment-extraction dead-code disposition) are documented in
[`../ingestion/phase-4.6.md`](../ingestion/phase-4.6.md).

## 4.6.3 — Idempotency cache cross-principal leak (HIGH)

`_idempotency_cache_key(idempotency_key, principal, history)`
(`app/features/rag_agent/server/router.py`) hashes `sha256(idempotency_key + "|" + json(turns) + "|" +
principal)` instead of using the raw `Idempotency-Key` header as the cache key — mirroring
`answer_cache._cache_key`'s already-correct binding. A replay of the same header with a *different*
principal or history is now treated as a fresh request, never a hit on another caller's cached
`Answer`.

## 4.6.4 — Rate-limiter/idempotency hardening batch (MEDIUM-HIGH + MEDIUM)

Two fixes in `app/shared/rate_limiter.py` / `app/features/rag_agent/server/router.py`:

1. **`_rate_limit_key` dropped `principal` entirely.** It used to prefer `principal:{principal}` when
   supplied — since `principal` is untrusted, caller-rotatable free text, any caller could defeat
   `chat_rate_limit_per_minute` by sending a different principal per request. Now always
   `ip:{client_ip}`, the one dimension a caller can't freely rotate.
2. **`SlidingWindowRateLimiter` bounded memory** (`app/shared/rate_limiter.py`) — a
   `max_tracked_keys` eviction bound, closing an unbounded-memory-growth path that compounded finding
   #1 (unlimited rotated principals = unlimited tracked keys).

## 4.6.6 — `permission.py`'s overloaded `scope` string (MEDIUM)

`PrincipalPermissionPolicy.allowed()` (`app/features/retrieval/domain/permission.py`) no longer takes
a raw `scope: str | None` and re-derives trust kind via `.isdigit()` inside itself — that was the root
cause the 5.3 red-team finding only patched at one HTTP-boundary caller (see
[phase-5.md](./phase-5.md)'s 5.3 entry). The classification is now a single pure function,
`classify_scope(scope) -> (space_id, principal)`, called **exactly once** per search in
`HybridRetriever._search` (`application/retriever.py`), which hands the already-classified pair to
`allowed(space_id=..., principal=...)`. The domain layer can no longer reinterpret an all-digit
*principal* string as space-level trust for any caller, not just the one HTTP validator patched it at.

## 4.6.10 — RLS reader-role no-op outside offline envs (LOW)

`Settings.is_offline_env()` (`app/platform/config/settings.py`) replaces a duplicated `_OFFLINE_ENVS`
constant in `embeddings_client.py`/`reranker_client.py`. `get_reader_engine()`
(`app/platform/db/engine.py`) now **raises** `ReaderRoleMisconfiguredError` when `database_reader_url`
is unset outside `local`/`test`/`dev`/`ci` — previously it silently fell back to the RLS-bypassing
writer connection in any environment, which is a silent security regression in a real deployment, not
a convenience. Inside an offline env, the silent fallback is preserved exactly (matches the offline
dev-without-a-reader-role workflow).

## 4.6.12 — `Answer.refusal_reason` never reaches an observable surface (LOW)

`refusal_reason` (computed since 4.1, unit-tested since 4.2) was never logged anywhere outside the
process. Added to the `chat_request` structured log line in `_stream_answer`
(`app/features/rag_agent/server/router.py`) — `None` when not refused, a static templated category
string when it is (never a diagnostic with an interpolated score — see [phase-9.md](./phase-9.md)'s
9.4 entry for why that distinction matters for fallback-rate reporting).

## Cross-cutting gates (not retrieval-specific, but gate this whole sub-phase)

- **4.6.9 — Pyright baseline reconciliation.** Governance fix: the pyright error count had crept
  31→34 across earlier phases, reported "unchanged" without ever reconciling against ADR-0003's
  actual fixed number. Every 4.6 sub-step above is diffed against this reconciled baseline (2 ruff
  errors / ≤25 unformatted / 34 pyright errors), not just counted.
- **4.6.16 — Exit gate.** All 16 sub-steps green, 274 tests, no ruff/pyright regression. Gates Phase
  5.4 (live-LLM red-team, embedder bake-off, adaptive routing).

## Files & folders used

- `app/features/rag_agent/server/router.py` — `_idempotency_cache_key`, `_rate_limit_key`,
  `chat_request` log line.
- `app/shared/rate_limiter.py` — `SlidingWindowRateLimiter`, `max_tracked_keys`.
- `app/features/retrieval/domain/permission.py` — `classify_scope`, `PrincipalPermissionPolicy.allowed`.
- `app/features/retrieval/application/retriever.py` — the single `classify_scope` call site.
- `app/platform/config/settings.py` — `is_offline_env()`.
- `app/platform/db/engine.py` — `ReaderRoleMisconfiguredError`, `get_reader_engine()`.
- `app/features/rag_agent/tests/`, `app/features/retrieval/tests/`,
  `app/platform/db/tests/test_engine_reader_role.py` — the regression tests per sub-step above.

See [`../ingestion/phase-4.6.md`](../ingestion/phase-4.6.md) for the write-path sub-steps of this same
backlog.
