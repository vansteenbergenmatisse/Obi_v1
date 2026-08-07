# Omniboost RAG — Project Standard

Accuracy-first, Confluence-native RAG chatbot. This file is the project's governing
architecture standard; where it is silent, the global `~/.claude/CLAUDE.md` applies.
Durable decisions live in `docs/adr/`; per-feature contracts in
`apps/automation/app/features/FEATURES.md`.

## Layout

```
apps/
  automation/   Python 3.12 FastAPI RAG service (uv + Hatchling). The backend.
  web/          Next.js frontend (pnpm). The chat UI.
packages/       Shared TS packages (design-tokens, contracts).
docs/adr/       Architecture Decision Records.
infra/          Docker compose for local Postgres + pgvector.
```

Package managers do not mix: `uv` for `apps/automation`, `pnpm` for the JS/TS
workspace (driven by `pnpm-workspace.yaml` — there is no npm `workspaces` array).

## Backend structure (`apps/automation/app`)

The backend is a runnable service and uses three of the five standard folders:

```
app/
  main.py        FastAPI entrypoint — wiring only, no business rules.
  features/      Business capabilities, each behind one public root.
  platform/      Technical capabilities: db, clients, config, jobs, logging.
  shared/        Stable cross-feature primitives (e.g. hashing).
```

There is no `components/` — that folder is UI-only and belongs to `apps/web`. Backend
primitives with no clearer owner go in `shared/`, not `platform/` (ADR-0003).

## Feature boundaries (machine-enforced)

Every feature (`confluence_sync`, `ingestion`, `retrieval`, `evaluation`) and the
`platform/clients` capability expose one public root (`__init__.py`) that re-exports
the symbols crossing their boundary. `tools/check_feature_boundaries.py` fails the
build on four rules:

1. Code **outside** a feature imports it at its root (`app.features.<f>`) — never deeper.
2. Code **inside** `<f>` may deep-import `<f>`, but reaches **other** features at their root.
3. Code inside `<f>` must not import its own root (importing a half-built package raises
   ImportError at init — the self-facade trap).
4. `platform/**` and `shared/**` import no features; `shared/**` imports no `platform/**`.

`platform/db` is the one deliberate exception: its ~40 ORM classes and enums are a large
namespaced vocabulary imported by full path, not through a facade (ADR-0003 D5).

When adding a symbol other code needs, export it from the feature's `__init__.py` — do
not deep-import. Run `make boundaries` before you commit.

## Gate

Run from `apps/automation` (everything via `uv run`); `make check` bundles the enforced subset.

```
make boundaries   # architecture gate — must exit 0
make check        # boundaries + tests (the enforced gate)
uv run pytest -q  # 99 passing
uv run ruff check .        uv run ruff format --check .        uv run pyright
```

Ruff and Pyright are tracked at **no-regression**, not zero: a known baseline of dirt
predates this standard (Ruff 2 errors / 25 unformatted, Pyright 31/1). Do not reformat
files you did not otherwise touch, and do not let the whole-repo counts rise. Files you
edit are brought clean. See ADR-0003 D1.

## Run

```
make up        # start Postgres (pgvector) on :5434
make migrate   # alembic upgrade head
make test      # automation suite
make eval      # retrieval evaluation baseline
make web-dev   # Next.js dev server
uvicorn app.main:app   # serve (enable_background_jobs=true adds scheduler + worker)
```

Secrets load from the root `.env` (gitignored). Tests use a hermetic settings fixture
and the `omniboost_rag_test` database, independent of `.env` contents.
