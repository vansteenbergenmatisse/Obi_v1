# entrypoint

## Purpose (two lines)
`apps/automation/app/main.py` is the composition root: it builds the FastAPI app from `Settings`, wires the Confluence gateway, the `HybridRetriever` + `AnswerService` (wrapped in a cache), the rate limiter and token verifier, mounts the two feature routers, and — when enabled — starts the APScheduler background jobs. `apps/automation/app/__init__.py` holds only the single `__version__` string main.py stamps onto the app.

## Entry points
| symbol | file:line | called by |
|---|---|---|
| `build_gateway` | `apps/automation/app/main.py:56` | `create_app` (main.py:181) |
| `build_answer_service` | `apps/automation/app/main.py:64` | `create_app` (main.py:202) |
| `scheduled_lightweight_reconcile` | `apps/automation/app/main.py:120` | APScheduler job `lightweight_reconcile` (main.py:137-144) and `dev_lightweight_reconcile` (main.py:166-174) |
| `scheduled_complete_reconcile` | `apps/automation/app/main.py:125` | APScheduler job `complete_reconcile` (main.py:145-152) |
| `worker_tick` | `apps/automation/app/main.py:130` | APScheduler job `worker_tick` (main.py:153-160) |
| `_build_scheduler` | `apps/automation/app/main.py:135` | `create_app`'s `lifespan` (main.py:188), and directly by `apps/automation/app/features/confluence_sync/tests/test_scheduler.py:14,26,34` |
| `create_app` | `apps/automation/app/main.py:178` | module-level `app = create_app()` (main.py:220); `test_webhook.py:22`, `test_chat_endpoint.py:53,690`, `test_router_auth_context.py:50` |
| `health` (route handler) | `apps/automation/app/main.py:214` | FastAPI `GET /health` — no test file calls this route (see Known gaps) |
| `app` (module-level ASGI instance) | `apps/automation/app/main.py:220` | the ASGI server (uvicorn) at process start |

## Reads and writes
| tables, files, queues touched | read or write | file:line |
|---|---|---|
| `Settings` (env / `.env`, via `get_settings()`) | read | `apps/automation/app/main.py:179` |
| DB writer engine/sessionmaker (`get_sessionmaker()`) | read (constructs, lazy connect) | `apps/automation/app/main.py:86,102,112` |
| DB reader engine/sessionmaker (`get_reader_sessionmaker()`, `rag_reader` role) | read (constructs, lazy connect) | `apps/automation/app/main.py:78,112` |
| `Job` queue / reconciliation state (via `reap`, `drain`, `run_reconciliation` — owned by `confluence_sync`) | write (triggered from main.py's scheduled callbacks) | `apps/automation/app/main.py:121-122,126-127,131-132` |
| `app.state.settings`, `.gateway`, `.rate_limiter`, `.answer_service`, `.token_verifier` (in-process, not persisted) | write | `apps/automation/app/main.py:198-209` |

Note: main.py itself performs no direct SQL — it only obtains sessionmakers/engines and passes them into feature constructors (`HybridRetriever`, `AnswerService`, `session_scope`). The actual reads/writes happen inside those features' code, out of this file's scope.

## External calls
| client | endpoint | timeout, retry, breaker present? | file:line |
|---|---|---|---|
| `HttpConfluenceClient` (only if `confluence_base_url` + `confluence_api_token` set) | Confluence REST (owned by `platform/clients`) | not configured in main.py — main.py only decides live-vs-fixture | `apps/automation/app/main.py:56-61` |
| `AnthropicMessagesClient` | Anthropic Messages API | timeout=`settings.answer_timeout_seconds`, retries=`settings.answer_max_retries`, breaker_threshold=`settings.answer_breaker_threshold` — all three params passed at construction | `apps/automation/app/main.py:89-95` |
| `build_embedding_provider(settings)` | OpenAI (or offline fallback) | not configured in main.py — delegated to `platform/clients` (per `build_answer_service`'s own docstring, main.py:70-72) | `apps/automation/app/main.py:79` |
| `build_reranker(settings)` | Cohere (or offline fallback) | not configured in main.py — delegated to `platform/clients` | `apps/automation/app/main.py:81` |

## Tests present
| test file | behaviors asserted | panel ids |
|---|---|---|
| `apps/automation/app/features/confluence_sync/tests/test_webhook.py:13,21-24,47-55` | `create_app(settings, start_scheduler=False)` boots a working app; `/confluence/events` route mounted and reachable | cm-root (no explicit panel-id reference in the test file itself — see Known gaps) |
| `apps/automation/app/features/confluence_sync/tests/test_chat_endpoint.py:25,52-55,686-691` | `create_app` boots; `/chat` route mounted; `test_create_app_wires_the_answer_cache_by_default` directly asserts `app.state.answer_service` is a `CachingAnswerService` instance (main.py:201-205) | cm-root |
| `apps/automation/app/features/confluence_sync/tests/test_router_auth_context.py:16,50-53` | `create_app` boots with a real `AuthContext`/token-verifier wiring path, then overrides `app.state.token_verifier` for the test | cm-root |
| `apps/automation/app/features/confluence_sync/tests/test_scheduler.py:14,20-42` | `_build_scheduler` registers the three baseline jobs (`lightweight_reconcile`, `complete_reconcile`, `worker_tick`) always, and the optional `dev_lightweight_reconcile` job only when `dev_reconcile_interval_seconds` is set | cm-root |

No test file in the repo names `cm-root` or `sc-backend` literally as a panel id (grep for both strings returned no matches under `apps/automation`); tests instead cite PLAN item numbers (e.g. "PLAN 5", "PLAN 11.1c") in docstrings. See Known gaps.

## Known gaps
- `GET /health` (`apps/automation/app/main.py:213-215`) has no test anywhere in the repo — `grep` for the literal route string `"/health"` matches only its own definition in main.py.
- `build_gateway` (`apps/automation/app/main.py:56`) has no test that calls it directly or asserts on `app.state.gateway`'s live-vs-fixture selection; it is only exercised indirectly by whichever fixtures the other main.py tests use.
- The real `TokenVerifier(settings.platform_registry)` construction at `apps/automation/app/main.py:209` is never asserted on directly — every test that boots `create_app` immediately overrides `app.state.token_verifier` (`test_router_auth_context.py:52`) or never inspects it, so the "fail-fast on bad platforms.json" guarantee the main.py:206-208 comment describes is not proven at this file's boundary (it is proven, if at all, by `apps/automation/app/platform/config/tests/test_platforms.py`, which is out of this audit's scope).
- `app.state.rate_limiter` (`apps/automation/app/main.py:200`) is constructed once at startup, but `apps/automation/app/features/confluence_sync/server/webhook.py:80-85` (`_rate_limiter`) lazily re-creates it if `request.app.state.rate_limiter` is ever `None` — main.py's own construction is exercised only indirectly through `test_webhook.py`'s rate-limit tests, not asserted as the object identity in use.

## Claims from the design

### Panel cm-root — "app/main.py: the wiring"
| panel | claim | file:line | verdict | note |
|---|---|---|---|---|
| cm-root | Today: "Builds the FastAPI app, the retriever, the answer service, the scheduler, and mounts the two routers." | `apps/automation/app/main.py:178-217` | confirmed | `create_app` does exactly these five things: `FastAPI(...)` (197), retriever inside `build_answer_service` (77-88), answer service (202), scheduler wiring in `lifespan` (184-196), two `include_router` calls (210-211). |
| cm-root | Code location: `apps/automation/app/main.py` — `create_app`, `build_answer_service` | `apps/automation/app/main.py:64,178` | confirmed | Both symbols exist exactly as named. |
| cm-root | Code location: `apps/automation/app/platform/config/settings.py` — every knob, read from .env | `apps/automation/app/platform/config/settings.py:32` (`class Settings(BaseSettings)`) | confirmed (out of file scope) | This claim is about `settings.py`, not `main.py`; verified only that the file and class exist as named — full "every knob" audit is out of this audit's assignment. |
| cm-root | Step 1: "Read settings." | `apps/automation/app/main.py:179` | confirmed | `settings = settings or get_settings()`. |
| cm-root | Step 2: "Build the reader engine (fails closed without DATABASE_READER_URL outside local)." | `apps/automation/app/main.py:78,112` calling into `apps/automation/app/platform/db/engine.py:36-64` | drifted | main.py does not build the reader engine itself — it calls `get_reader_sessionmaker()`, which lazily calls `get_reader_engine()`. The actual fail-closed check lives in `apps/automation/app/platform/db/engine.py:50-57`, not in main.py. Also the design says "outside local"; the code's actual guard is "outside an offline env" (`settings.is_offline_env()`, engine.py:51), which per the engine.py docstring (lines 44-46) includes local, dev, test and the CI/test harness — a broader set than just "local". |
| cm-root | Step 3: "Build HybridRetriever with embedder, reranker, and the scope flag." | `apps/automation/app/main.py:77-88` | confirmed | `HybridRetriever(get_reader_sessionmaker(), build_embedding_provider(settings), PrincipalPermissionPolicy(), build_reranker(settings), ..., enable_knowledge_scope_filtering=settings.enable_knowledge_scope_filtering)`. |
| cm-root | Step 4: "Build AnswerService with rewriter, generator, and the recognized scopes." | `apps/automation/app/main.py:96-114` | confirmed | `AnswerService(retriever, AnthropicQueryRewriter(...), AnthropicAnswerGenerator(...), ..., recognized_knowledge_scopes=settings.knowledge_scope_set, ...)`. |
| cm-root | Step 5: "Mount /confluence/events and /chat. Start the sweep scheduler." | mounts: `apps/automation/app/main.py:210-211`; routes: `apps/automation/app/features/confluence_sync/server/webhook.py:88` (`@router.post("/confluence/events")`) and `apps/automation/app/features/rag_agent/server/router.py:499` (`@router.post("/chat")`); scheduler start: `apps/automation/app/main.py:187-190` | confirmed | Both routers included by root import (`confluence_router`, `chat_router`); scheduler only starts when `should_start` is true (main.py:182, resolved from `settings.enable_background_jobs` or the `start_scheduler` override). |

### Panel sc-backend — "One backend"
| panel | claim | file:line | verdict | note |
|---|---|---|---|---|
| sc-backend | Today: "apps/automation: FastAPI, five feature folders (confluence_sync, ingestion, retrieval, rag_agent, evaluation), platform clients, the job worker." | main.py imports from `confluence_sync` (main.py:20-27), `rag_agent` (main.py:28-36), `retrieval` (main.py:37), `platform.clients` (main.py:38-45) | confirmed (partial, in-scope only) | main.py itself only touches `confluence_sync`, `rag_agent`, `retrieval`, and `platform.clients`/`platform.config`/`platform.db`/`platform.logging`; it imports nothing from `ingestion` or `evaluation` directly. Those two features and the folder-level claim as a whole are owned by their respective folders, not verifiable from main.py alone. |
| sc-backend | "Owns... the webhook and sweeps... token verification, the authorization context, search, rerank... generation, the citation and support checks, the audit trail" | main.py wires but does not implement any of these: webhook route owned by `apps/automation/app/features/confluence_sync/server/webhook.py:88`; `TokenVerifier` owned by `apps/automation/app/features/rag_agent/server/token_verifier.py` (imported at main.py:34); search/rerank owned by `HybridRetriever` (imported at main.py:37) | confirmed (wiring only) | main.py's role is limited to construction/injection (main.py:77-114, 209); the business logic these nouns describe is owned by the named feature folders, not main.py — consistent with the CLAUDE.md rule that `app/` is "wiring only". |
| sc-backend | "Talks to Postgres as rag_reader for reads and as the owner for writes" | reader sessionmaker: `apps/automation/app/main.py:78,112` (`get_reader_sessionmaker()`); writer sessionmaker: `apps/automation/app/main.py:86,102` (`get_sessionmaker()`) | confirmed | main.py passes the reader sessionmaker to `HybridRetriever` (rag_reader role, per `platform/db/engine.py:37-64`) and the writer sessionmaker to `AnswerService`'s trace/session args and to `session_scope()` in the scheduled-job helpers (main.py:121-122,126-127). |
| sc-backend | "Talks to... Confluence, OpenAI, Cohere and Claude over HTTPS" | Confluence: `apps/automation/app/main.py:56-61`; Claude: `apps/automation/app/main.py:89-95`; OpenAI/Cohere: `apps/automation/app/main.py:79,81` (`build_embedding_provider`, `build_reranker`) | confirmed (wiring only) | main.py selects/constructs all four clients but the HTTP calls themselves are owned by `platform/clients` — out of this file's scope to verify transport details. |
| sc-backend | Code location: `apps/automation/app/main.py` — "wires everything" | `apps/automation/app/main.py:1-220` | confirmed | Matches the file's own module docstring (main.py:1-7): "Wiring only — all behavior lives in the features." |
| sc-backend | Code location: `apps/automation/app/features/` — the five features | n/a (owned by `features/`) | needs live / out of scope | Not verifiable from main.py; main.py only imports from `confluence_sync`, `rag_agent`, and `retrieval` (see Today-claim note above). Owned by `apps/automation/app/features/`. |
| sc-backend | Code location: `apps/automation/app/platform/` — clients, settings, jobs (and today also db models) | `apps/automation/app/main.py:38-49` (imports `platform.clients`, `platform.config`, `platform.db.engine`, `platform.logging`) | confirmed (imports only) | main.py imports from `platform.clients`, `platform.config`, `platform.db.engine`, and `platform.logging`; it does not import `platform` db models directly (ADR-0003 exception is used elsewhere, not in main.py). Full `platform/` content audit is owned by `platform/`, out of scope. |

## Not on the design page
- `_WORKER_OWNER = "in-process-worker"` constant, passed to `drain()` as the job-claim owner tag — `apps/automation/app/main.py:53,132`. Not mentioned in either panel.
- The `dev_lightweight_reconcile` optional DEV-only fast-poll scheduler job — `apps/automation/app/main.py:166-174`. The cm-root panel's step 5 only says "Start the sweep scheduler"; this DEV-only fourth job (gated on `settings.dev_reconcile_interval_seconds`) is not named on either panel, though it is covered by `test_scheduler.py:32-42`.
- `GET /health` endpoint — `apps/automation/app/main.py:213-215`. Neither panel's "today" line or code-location list mentions a health probe, though main.py's own module docstring calls it out ("webhook ingress, health, and (optional) background jobs", main.py:1).
- `app.state.rate_limiter` (`SlidingWindowRateLimiter`) construction — `apps/automation/app/main.py:200`. Not named on either panel; owned in practice by `shared/rate_limiter` and consumed by the webhook route.
- `apps/automation/app/__init__.py:8` — `__version__ = "0.2.0"`, stamped onto the app at `apps/automation/app/main.py:197`. Not mentioned on either panel.
