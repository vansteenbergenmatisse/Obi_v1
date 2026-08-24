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

## Phase documentation (`docs/rag/ingestion/`, `docs/rag/retrieval/`)

The write path (`confluence_sync` + `ingestion`) and the read/answer path (`retrieval` +
`rag_agent`) each have a folder of per-phase docs: one file per project phase that actually
touched that side (`phase-0.md`, `phase-1.md`, `phase-3.5.md`, …), stating what happens in that
phase and exactly which files/folders it uses. A phase only gets a file in a folder if it actually
touched that side — no filler stubs. A phase that touches both sides (e.g. 3.5, 4.6) gets a file in
both, each scoped to that side only and cross-linking to its counterpart. `docs/rag/
how_this_works.md` stays the short end-to-end index — the 60-second picture, data model, and one
worked example — and points into these folders instead of repeating their detail.

**Keep both folders in sync with every future change to ingestion or retrieval code:** when a task
edits, adds, or removes ingestion/retrieval behavior, update the matching phase file (or add a new
one for a new phase; delete/merge one if a phase is reverted or superseded) as part of that same
change — do not let this drift the way `how_this_works.md` did before PLAN 4.6.14. `docs/rag/
PLAN.md` §0 remains the authoritative status ledger; these folders are the reader-facing map of
"what runs and where," not a second ledger.

## Gate

Run from `apps/automation` (everything via `uv run`); `make check` bundles the enforced subset.

```
make boundaries   # architecture gate — must exit 0
make check        # boundaries + tests (the enforced gate)
uv run pytest -q  # 401 passing
uv run ruff check .        uv run ruff format --check .        uv run pyright
```

Ruff and Pyright are tracked at **no-regression**, not zero: a known baseline of dirt
predates this standard (Ruff 2 errors / 15 unformatted, Pyright 34/1 — reconciled from the
original 31/1 at PLAN 4.6.9, see ADR-0003 D1 amendment). Do not reformat files you did not
otherwise touch, and do not let the whole-repo counts rise. Files you edit are brought
clean.

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

## Testing & Regression Safety

For every new feature, component, or meaningful behavior change, add appropriately scoped automated tests covering its public behavior, critical business rules, edge cases, failure paths, and integrations where relevant. Tests MUST protect existing contracts and core behavior so future changes can be made confidently without unintentionally breaking, removing, or altering established features, components, or system invariants. Prefer maintainable tests at the lowest effective level—unit, integration, contract, or end-to-end—based on the risk and responsibility of the code being changed.

# Phase Gates & Compaction

For every multi-phase implementation, **stop completely after each phase and never begin the next phase automatically**. Before stopping, verify the phase against its requirements, fix gaps or incomplete work, ensure appropriate tests exist and pass, and run all relevant validation. Update `plan.md` and `design.md` after every phase to accurately document what was completed, what remains, implementation/design changes, decisions made, and any instructions or corrections I gave during execution. Then explicitly stop so I can perform **Ultra compaction**.

After compaction, before starting the next phase, re-read `plan.md`, `design.md`, the implementation, and tests, and independently audit the previous phase again. Fix anything missing or incorrect, add any tests that should have existed, run them, and reconcile the documentation with the actual repository state. **Only when the previous phase is fully implemented, tested, validated, and documented may the next phase begin.**
