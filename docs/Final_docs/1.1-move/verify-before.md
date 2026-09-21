# /obi-verify — BEFORE the 1.1.1 folder move

Captured on the untouched code (branch `feat/rag-phase-3.5`), by running each level's
`make` target from the repository root (equivalent to `/obi-verify`). The working tree at
capture time had only `docs/plan/decisions.md` modified (the Step-0 `kb-import-name` row) and
the new `docs/Final_docs/1.1-move/` records — no source change.

`verify-after.md` must match this table **line for line on `level`, `command`, `result` and
`note`**. The wall-clock `seconds` column is intentionally omitted from both files: it varies
run to run and is not part of the identity check (the design's "identical line for line"
is about outcomes, not timings).

| level | command | result | note |
|---|---|---|---|
| unit | `make test-unit` | **PASS** — 536 passed, 290 deselected, 1 warning | deselected = the `db`-marked tests |
| database | `make test-db` | **PASS** — 289 passed, 536 deselected, 1 xfailed | xfail = `tg-deactivate` (tracked, built in 2.2.4); pgvector up, migrated to head, roles+policies, rolled back |
| lint + types | `ruff check .` · `ruff format --check .` · `pyright` | **PASS (no baseline yet)** — ruff 45 errors, 11 files unformatted, pyright 57 errors | `docs/plan/baseline.md` has no numbers, so these levels PASS by rule; counts must not rise after the move |
| browser | `make test-ui` | **PASS** — 1 passed (`e2e/widget-mounts.spec.ts`) | build:obi + playwright chromium, stub host page |
| eval | `make eval` | **PASS (no baseline yet)** — smoke recall@5=1.000 mrr=0.750; ambiguity recall@5=1.000; permission recall@5=0.667; rerank ndcg@10 1.000→0.877 | baseline reports written; no gold-set numbers in baseline.md yet |
| live | (isolation/backfill scripts) | **SKIPPED** — no `STAGING_DATABASE_URL` set | staging-only; not part of this move's proof |

**Overall: GREEN** — every wired level passed; no lint/type count above baseline (there is no baseline floor yet).

_Test-count reference (for the CI ≥621 floor and for 1.1.2's floor bump): 826 collected (536 unit + 289 db + 1 xfail)._
