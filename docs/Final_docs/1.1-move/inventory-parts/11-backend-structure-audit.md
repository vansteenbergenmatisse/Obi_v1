# 11 · Backend structure audit — `apps/automation/`

Read-only structural map for the mover. Ownership before restructuring.

## KEY FINDING — `db/` is NOT self-contained

`app/platform/db/` imports **out** to `app.platform.config`. Moving `db/` to
`knowledge-base/schema` as-is would create a `knowledge-base → backend` import,
violating the one-way rule (`knowledge-base` imports nothing from `backend`).

Non-test hits (production code — these block the move):

```
apps/automation/app/platform/db/engine.py:12: from app.platform.config import get_settings
apps/automation/app/platform/db/models.py:36: from app.platform.config import get_settings
```

Test-file hits inside `db/tests/` (move with the package or stay in backend):

```
apps/automation/app/platform/db/tests/test_models_indexes.py:30:            from app.platform.config import get_settings
apps/automation/app/platform/db/tests/test_reader_default_privileges.py:23:      from app.platform.config import get_settings
apps/automation/app/platform/db/tests/test_migration_0009_reader_rls_reconcile.py:25: from app.platform.config import get_settings
apps/automation/app/platform/db/tests/test_migration_0011_subject_hash.py:21:      from app.platform.config import get_settings
apps/automation/app/platform/db/tests/test_migration_0010_scope_rls.py:27:         from app.platform.config import get_settings
apps/automation/app/platform/db/tests/test_migration_0007_knowledge_scope.py:22:    from app.platform.config import get_settings
apps/automation/app/platform/db/tests/test_r3_reader_role_protect.py:26:           from app.platform.config import get_settings
apps/automation/app/platform/db/tests/test_engine_reader_role.py:16:              from app.platform.config import Settings
```

No imports of `app.features` or `app.shared` inside `db/`. The only leak is
`app.platform.config`. `engine.py` and `models.py` both call `get_settings()`
to read the DB URL / connection settings. Internal `db/` imports
(`app.platform.db.base`, `.enums`, `.models`) are self-referential and fine.

**Mover action required:** the connection-settings dependency must be inverted
(e.g. `knowledge-base/schema` receives a DB URL/config object as a parameter
rather than importing backend config) before `db/` can move cleanly.

## `app/main.py` — wiring only (no business rules)

FastAPI entrypoint. Selects a Confluence gateway (live `HttpConfluenceClient`
when configured, else `FixtureConfluenceGateway`), mounts the confluence_sync
webhook router + rag_agent chat router + health probe, builds services
(`AnswerService`/`CachingAnswerService`, Anthropic clients, `TokenVerifier`,
`HybridRetriever`, `PrincipalPermissionPolicy`, rate limiter), and — when
`enable_background_jobs` is set — runs reconciliation crons + an in-process
queue worker via APScheduler. Imports each feature at its root only.

## `app/features/` (each has its own `tests/` dir unless noted)

- **confluence_sync/** — ingestion stages 1–2: webhook, event ledger, job queue/worker, sweeps, change classification, labels→scope. (`application/ domain/ infrastructure/ schemas/ server/ tests/`)
- **ingestion/** — stages 3–4: normalize, chunk, contextualize, attachments, embed, version, swap, GC, rollback. (`application/ domain/ infrastructure/ tests/`)
- **retrieval/** — retrieval stages 2–4: hybrid search, fusion, page permissions, rerank wiring, trace writes. (`application/ domain/ infrastructure/ tests/`)
- **rag_agent/** — stages 1 & 5: chat endpoint, token/key checks, limits, small talk, rewrite, refusal, generation, citations, support check, prompts. (`application/ domain/ infrastructure/ schemas.py server/ tests/`)
- **evaluation/** — eval runner, metrics, gold datasets. (`datasets/ metrics/ runner.py run_baseline.py fixtures.py schemas.py README.md tests/`)

`features/FEATURES.md` documents the set.

## `app/platform/` subdirs

- **db/** — SQLAlchemy `Base`, engine/sessionmaker (reader + writer), models, enums, schema. See KEY FINDING. Owns `db/tests/` (the db-marked tests live here).
- **config/** — `settings.py`, `knowledge_scopes.py`, `platforms.py`; own `tests/`. The target of the db leak.
- **clients/** — external API clients: `anthropic_client`, `confluence_client`, `fixture_confluence_client`, `embeddings_client`, `reranker_client`; own `tests/`. Public boundary root.
- **jobs/** — `queue.py`, the job-queue primitive.
- **logging/** — `setup.py` (`configure_logging`, `get_logger`).

## `app/shared/` — cross-feature primitives

`hashing.py`, `rate_limiter.py` (`SlidingWindowRateLimiter`), `ttl_cache.py`, plus `tests/`. No `platform/` or feature imports.

## Where db-marked tests live

Three test homes:

1. **Feature-local** — `app/features/<feature>/tests/` (unit + db tests next to their feature).
2. **`app/platform/db/tests/`** — the DB-role / migration / RLS / model-constraint db tests (`test_migration_0007…0011`, `test_r3_reader_role_protect`, `test_reader_default_privileges`, `test_s_anon_public_grant`, `test_engine_reader_role`, `test_models_constraints`, `test_models_indexes`). This is the primary home for schema/db-marked tests.
3. **`apps/automation/tests/`** — repo-level meta tests only: `test_cm_docs.py` plus `code_map/`, `fixtures/`, `tools/` (not feature db tests).

Also `platform/config/tests/`, `platform/clients/tests/`, `shared/tests/`.

## `apps/automation/scripts/` — one moves, rest stay in backend/scripts

- **seed_curated_knowledge.py** — one-off CLI to add/update/deactivate a `curated_knowledge_entry` row (PLAN 10.6, ADR-0011). **→ MOVES to `knowledge-base/seed`** (seed data).
- rotate_chat_api_key.py — rotate `CHAT_API_KEY` with no outage (PLAN 5). *(stays)*
- run_reconciliation_once.py — one COMPLETE reconciliation sweep + drain jobs (PLAN 10.7). *(stays)*
- seed_source_scope.py — add/update a Confluence sync root in `source_scope` (PLAN 3.5.6). *(stays)*
- setup_supabase.py — operator CLI: stand up RAG schema + roles on managed Postgres. *(stays)*
- verify_knowledge_scope_backfill.py — PLAN 10.7 exit-gate readiness check. *(stays)*
- verify_knowledge_scope_live.py — live self-test: a Confluence label change propagates into the DB. *(stays)*

`seed_curated_knowledge.py` is the only script slated to move.

## `apps/automation/tools/`

- **panel.py** — read/update one design panel from the Obi design page.
- **brief.py** — regenerate the markdown brief from the design page (needs beautifulsoup4).
- **agent_guard.py** — PreToolUse guard for the Obi subagents (stdlib only).
- **check_feature_boundaries.py** — enforces the feature/platform/shared import architecture (`make boundaries`).
