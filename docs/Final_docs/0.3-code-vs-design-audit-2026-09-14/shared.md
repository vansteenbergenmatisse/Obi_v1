# shared

## Purpose (two lines)
`apps/automation/app/shared/` holds small, stable cross-feature primitives with no clearer owner — currently a sliding-window rate limiter, a TTL cache, and stdlib-only hashing helpers (`apps/automation/app/shared/__init__.py:1-13`).
It is the bottom of the backend dependency graph: it must not import `app.features.*` or `app.platform.*` (`apps/automation/app/shared/__init__.py:4-6`), a rule enforced by tooling at `apps/automation/tools/check_feature_boundaries.py:46-103`.

## Entry points

| symbol | file:line | called by |
|---|---|---|
| `SlidingWindowRateLimiter` (class, `.allow()`) | `apps/automation/app/shared/rate_limiter.py:25-59` | `apps/automation/app/features/confluence_sync/server/webhook.py:42,96` (keyed by client IP); `apps/automation/app/features/rag_agent/server/router.py:165` (keyed by token subject, see `router.py:340`); instantiated in `apps/automation/app/main.py:49,200` |
| `TTLCache` (class, `.get()`, `.set()`) | `apps/automation/app/shared/ttl_cache.py:22-48` | `apps/automation/app/features/rag_agent/server/router.py:166,306-309` (Idempotency-Key replay cache); `apps/automation/app/features/rag_agent/application/answer_cache.py:42` (PLAN 5 exact-match answer cache) |
| `sha256_text` | `apps/automation/app/shared/hashing.py:23-24` | `apps/automation/app/features/rag_agent/server/router.py:164,340`; `apps/automation/app/features/rag_agent/application/answer_service.py:93`; `apps/automation/app/platform/clients/embeddings_client.py:31`; `apps/automation/app/features/ingestion/domain/chunking.py:28`; `apps/automation/app/features/ingestion/domain/normalization.py:18`; `apps/automation/app/features/ingestion/domain/change_detection.py:19` |
| `sha256_bytes` | `apps/automation/app/shared/hashing.py:15-20` | `apps/automation/app/features/ingestion/domain/chunking.py:28` |
| `normalize_text` | `apps/automation/app/shared/hashing.py:27-30` | `apps/automation/app/features/ingestion/domain/normalization.py:18` |
| `hash_json` | `apps/automation/app/shared/hashing.py:38-39` | `apps/automation/app/features/confluence_sync/infrastructure/event_repo.py:13`; internally by `hash_labels`, `hash_access_scope`, `hash_attachment_manifest` |
| `hash_labels`, `hash_access_scope`, `hash_attachment_manifest` | `apps/automation/app/shared/hashing.py:42-66` | `apps/automation/app/features/ingestion/domain/change_detection.py:15-20` |
| `canonical_json` | `apps/automation/app/shared/hashing.py:33-35` | no external caller found; used internally by `hash_json` only |

## Reads and writes

| tables, files, queues touched | read or write | file:line |
|---|---|---|
| none | — | `shared` holds pure in-process, in-memory primitives (a dict-backed cache and a dict-backed limiter). No database table, file or queue is touched anywhere in `apps/automation/app/shared/*.py`. |

## External calls

| client | endpoint | timeout, retry, breaker present? | file:line |
|---|---|---|---|
| none | — | not applicable | No HTTP, database, or third-party client code exists in `apps/automation/app/shared/`. |

## Tests present

| test file | behaviors asserted | panel ids |
|---|---|---|
| `apps/automation/app/shared/tests/test_ttl_cache.py:9-60` | hit returns stored value; miss on unknown key returns `None`; entry expires after TTL; entry survives up to the TTL boundary; expired entry is evicted (and counted) on read; `max_entries` evicts the oldest insertion; unbounded when `max_entries` is `None` | cm-shared |
| `apps/automation/app/shared/tests/test_rate_limiter.py:9-62` | allows up to `max_requests` within the window; allowed again once the window elapses; distinct keys are independent; an expired bucket is pruned from the dict on next access (PLAN 4.6.4); bucket count stays bounded across many distinct keys via `max_tracked_keys`; oldest key evicted first; unbounded when `max_tracked_keys` is `None` | cm-shared, i1-checks |
| (none) | `apps/automation/app/shared/hashing.py` has no dedicated test file in `apps/automation/app/shared/tests/` | cm-shared |

## Known gaps

- No `test_hashing.py` under `apps/automation/app/shared/tests/`: `sha256_bytes`, `normalize_text`, `canonical_json`, `hash_labels`, `hash_access_scope`, and `hash_attachment_manifest` (`apps/automation/app/shared/hashing.py:15-66`) are only exercised indirectly through consumer tests (e.g. `apps/automation/app/features/rag_agent/tests/test_answer_service.py`), not directly in `shared`.
- `apps/automation/app/shared/__init__.py:9-12` lists "Current inhabitants" as only `hashing` and `rate_limiter`; it does not mention `ttl_cache.py`, even though that file exists in the same folder and is actively imported by two consumers (`apps/automation/app/features/rag_agent/server/router.py:166` and `apps/automation/app/features/rag_agent/application/answer_cache.py:42`). The module docstring is behind the folder's actual contents.
- `canonical_json` (`apps/automation/app/shared/hashing.py:33-35`) has no caller found outside `hash_json` itself — it is exported but not used standalone anywhere in the codebase searched.
- The cm-shared panel itself flags `TTLCache`'s use in the answer cache "to remove" — as of `apps/automation/app/features/rag_agent/application/answer_cache.py:42` that import is still present, so the removal has not happened yet (self-acknowledged, not-yet-done cleanup, not a drift against the panel's own wording).

## Claims from the design

| panel | claim | file:line | verdict | note |
|---|---|---|---|---|
| cm-shared | `shared/rate_limiter.py` — `SlidingWindowRateLimiter`, used by webhook and chat | `apps/automation/app/shared/rate_limiter.py:25` (class); consumers at `apps/automation/app/features/confluence_sync/server/webhook.py:42,96` and `apps/automation/app/features/rag_agent/server/router.py:165` | confirmed | Matches exactly: one class, two independent HTTP-surface consumers as the panel states. |
| cm-shared | `shared/ttl_cache.py` — `TTLCache`, used by idempotency (and the answer cache, to remove) | `apps/automation/app/shared/ttl_cache.py:22` (class); consumers at `apps/automation/app/features/rag_agent/server/router.py:166,306-309` (idempotency) and `apps/automation/app/features/rag_agent/application/answer_cache.py:42` (answer cache) | confirmed | Both consumers exist as named; the "to remove" instruction for the answer-cache use is still pending (see Known gaps), which the panel itself already flags as not-yet-done, so this is not a drift. |
| cm-shared | `shared/hashing.py` — `hash_json`, `sha256_text` | `apps/automation/app/shared/hashing.py:38-39` and `:23-24` | confirmed | Both named symbols exist exactly as described. Panel names only these two of the module's eight public functions (see "Not on the design page"). |
| ov-auth | Hands each person a signed card (JWT); "Today: Does not exist" — no code location given for this panel | — | missing | Owned by the host backend / auth service (outside this repo per the panel's own "Outside system" kind). No file in `apps/automation/app/shared` implements or references this; not shared's responsibility. |
| cm-contracts | Source of truth `src/openapi/chat.yaml`; shared request/answer shape between widget and backend | — | missing | Owned by `packages/contracts` (a frontend/contracts package), not `apps/automation/app/shared`. No matching file found under the audited folder. |
| cm-platform | `platform/db/models.py`, `platform/clients/*`, `platform/config/*`, `platform/jobs/queue.py` | — | missing | All four listed code locations are under `apps/automation/app/platform/`, not `apps/automation/app/shared/`. Owned by platform, out of scope for this audit. |
| i1-checks | `shared/rate_limiter.py` — `SlidingWindowRateLimiter` is the rate-limit mechanism (300/min, part of the four webhook checks) | `apps/automation/app/shared/rate_limiter.py:25-59`; instantiated `apps/automation/app/main.py:200` with `settings.webhook_rate_limit_per_minute` default `300` at `apps/automation/app/platform/config/settings.py:204`; used at `apps/automation/app/features/confluence_sync/server/webhook.py:96` keyed by `client_ip` | confirmed | The shared-owned portion (the generic limiter primitive and the 300/minute default) checks out. The other three checks named by this panel (body-size cap, HMAC signature, JSON parse) and their exact call site live in `apps/automation/app/features/confluence_sync/server/webhook.py:67-101` — owned by confluence_sync, not audited here. |
| w-token | Code locations `apps/web/src/features/chat/api/access-token.ts` and `apps/web/src/features/chat/server/auth.ts` | — | missing | Owned by the frontend widget (`apps/web/`), not `apps/automation/app/shared`. No file at the given paths exists under the audited backend folder. |
| s-edge | Code locations `apps/automation/app/features/rag_agent/server/router.py:254-267` and `apps/web/src/features/chat/server/auth.ts` | — | missing | Owned by `rag_agent` (backend feature) and the frontend proxy, not `shared`. Note: the rate-limit key computation the panel describes ("the token subject") is implemented at `apps/automation/app/features/rag_agent/server/router.py:340` using `sha256_text` from `apps/automation/app/shared/hashing.py:23-24` — shared supplies the hash primitive, but the panel's own cited code locations point outside `shared`. |
| sc-user | Example scenario (a Mews user); no code location given | — | missing | Illustrative example panel, not a code claim. Nothing in `apps/automation/app/shared` to check against it. |
| em-token | The signed note (JWT contract); "Today: Does not exist"; no code location given | — | missing | Not implemented anywhere found in this repo; would belong to an auth/platform layer if built, not `shared`. |
| em-kb | Row security in the shared Postgres database, tag-based; no code location given | — | missing | Owned by `apps/automation/app/platform/db/` (row security policies), not `apps/automation/app/shared`. |
| em-loader | Code locations `apps/web/src/features/embed/loader.ts`, `apps/web/src/features/embed/iframe-bridge.ts`, `apps/web/src/app/embed/page.tsx`, all marked "(planned)" | — | missing | Owned by the frontend embed feature and explicitly not yet built per the panel ("planned"). No relation to `apps/automation/app/shared`. |
| s-user | (panel id not found) | — | missing | `python3 apps/automation/tools/panel.py s-user` returned "no panel with id 's-user'". `python3 apps/automation/tools/panel.py --grep user` lists `sc-user` and `s-writer` as the nearest ids; neither was substituted since the assignment named `s-user` specifically. No claim could be extracted or checked. |

## Not on the design page

- `hashing.py` exports six more functions beyond the two cm-shared names (`hash_json`, `sha256_text`): `sha256_bytes` (`apps/automation/app/shared/hashing.py:15-20`), `normalize_text` (`:27-30`), `canonical_json` (`:33-35`), `hash_labels` (`:42-43`), `hash_access_scope` (`:46-52`), `hash_attachment_manifest` (`:55-66`). None of these are named on any panel in the assignment list.
- The boundary contract in `apps/automation/app/shared/__init__.py:4-6` ("MUST NOT import `app.features.*` or `app.platform.*`") and its enforcement in `apps/automation/tools/check_feature_boundaries.py:46-103` are not described by any design panel in the assignment list; they come from `CLAUDE.md`'s Boundaries section, not the design page.
- `TTLCache`'s eviction policy detail — insertion-order (oldest-inserted-first), explicitly not true LRU — is documented only in the module docstring (`apps/automation/app/shared/ttl_cache.py:12-14`), not on any panel.
- `SlidingWindowRateLimiter`'s `max_tracked_keys` bounded-memory fix (PLAN 4.6.4) at `apps/automation/app/shared/rate_limiter.py:11-16,52-55` is not mentioned by any panel in the assignment list (i1-checks names only the 300/minute figure).
