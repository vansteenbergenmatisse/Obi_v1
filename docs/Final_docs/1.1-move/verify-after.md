# /obi-verify — AFTER the 1.1.1 folder move

Captured on the moved code (frontend/ · backend/ · knowledge-base/), by running each level's
`make` target from the repository root. Compare against `verify-before.md`.

The behavior levels (unit, database, browser, eval) are **identical line for line** to
verify-before — that is the proof the move changed no behavior. The `seconds` column is omitted
from both files (varies run to run).

| level | command | result | note |
|---|---|---|---|
| unit | `make test-unit` | **PASS** — 536 passed, 290 deselected, 1 warning | identical to before |
| database | `make test-db` | **PASS** — 289 passed, 536 deselected, 1 xfailed | identical to before; migrations applied from `knowledge-base/migrations/` via `alembic -c knowledge-base/migrations/alembic.ini` |
| lint + types | `ruff check .` · `ruff format --check .` · `pyright` | **PASS (no baseline yet)** — ruff **19** errors, **0** files unformatted, pyright **57** errors | see note ▼ — counts **improved** vs before (45→19 ruff, 11→0 unformatted), pyright unchanged (57). No count rose. |
| browser | `make test-ui` | **PASS** — 1 passed (`e2e/widget-mounts.spec.ts`) | identical to before. Frontend jsdom suite (`pnpm --filter web test`) also green: 237 passed / 29 files (includes the repointed `knowledge-scopes.test.ts`). |
| eval | `make eval` | **PASS (no baseline yet)** — smoke recall@5=1.000 mrr=0.750; ambiguity recall@5=1.000; permission recall@5=0.667; rerank ndcg@10 1.000→0.877 | identical to before |
| live | (isolation/backfill scripts) | **SKIPPED** — no `STAGING_DATABASE_URL` | identical to before |

**Overall: GREEN.**

### Why the lint numbers differ from verify-before (not a regression)
verify-before recorded ruff 45 / unformatted 11 / pyright 57. The import rewrite
(`app.platform.db.*` → `schema.*`) disturbed isort ordering in the touched files; per the
CLAUDE.md rule "files you touch are brought clean under ruff and pyright," those files were fixed
(`ruff check --fix` + `ruff format`, scoped to modified files only — untouched files were not
reformatted) and `schema` was pinned first-party in both `pyproject.toml`s. The net effect is
**fewer** lint errors (45→19) and **fewer** unformatted files (11→0); pyright is unchanged at 57.
Counts only dropped — the no-regression floor (ADR-0003 D1) is satisfied, and `baseline.md` still
carries "no baseline yet" so every count-tracked level PASSes by rule.

### Additional proofs (Step 7)
- **Leftover-path grep (code):** `grep -rn "apps/web\|apps/automation\|platform.db\|infra/foundation"` over the tree (excluding `.git`, `node_modules`, `.venv`, `docs`, `final_docs`, `.next`) returns **nothing** except the one intentional line `CLAUDE.md:55` — a self-deleting migration note that substep **1.1.3** rewrites and removes. The design page, action plan, ledger and other authoritative/append-only docs under `docs/` legitimately still name the old paths and are out of scope for code-cleanliness (the design-page target lines must not be edited).
  - Interpretation note: the pasted spec's proof grep excludes only `docs/archive`, but the design page (`docs/Final_docs/*.html`) and history genuinely reference the old paths and cannot be rewritten, so the "empty grep" is enforced over **code/config** (i.e. also excluding `docs/`).
- **`git diff --stat -M`:** 404 renames (278 pure `R100` + 126 renamed-with-path-edits) + 20 modified-in-place config/prose files + 2 new files (`knowledge-base/pyproject.toml`, `knowledge-base/schema/settings.py`). Two rename pairs (`brief.py`, the db `__init__.py`) show as delete+add because their content changed past git's rename threshold — same files, moved+edited.
  - Interpretation note: the spec predicted "R lines + config files only." Because the db package physically moved and ~80 files changed `app.platform.db.*`→`schema.*`, the honest diff is renames **plus** those content edits — expected, not "logic changes" beyond the move.
- **`python backend/tools/panel.py --list`** prints the panel list. ✓
- **`alembic -c knowledge-base/migrations/alembic.ini heads`** → `0012_widen_document_version_idem (head)` — same head as before the move; `make test-db` proved a clean `upgrade head` from the new location. ✓

### Break-it check (Step 8)
Reverted one import in `backend/app/platform/jobs/queue.py` (`from schema.models import` →
`from app.platform.db.models import`); `make test-unit` failed at collection with
`ModuleNotFoundError: No module named 'app.platform.db'` (2 collection errors). Restored the
`schema.*` import; `make test-unit` → **536 passed**. ✓
