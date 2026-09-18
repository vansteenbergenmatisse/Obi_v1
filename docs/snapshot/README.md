# Pre-target snapshot — the starting point of the plan

Substep **0.1.1 · Freeze the code**. This records the test state of the exact commit the
plan starts from, so every later change is measured against a real, tagged baseline.

## The tag

- **Tag / branch:** `pre-target-2026-09-14` (annotated tag **and** a branch of the same name)
- **Commit:** `bf7fece829e3ce1e9757e1bdb5fa538fbd6456ae`
- **git describe:** `green-baseline-151-gbf7fece`
- **Starting-point date:** 2026-09-14 (the commit itself is dated 2026-09-13, `docs(rag): PLAN §0 …`)
- **Tag cut on:** 2026-09-18 — cut **late**, after work had already started, and placed on the
  starting commit, never on the commit of the day it was cut (per 0.1.1's "Must be true").
- Source of the pinned commit: `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/README.md`
  ("Ground truth audited"). Note: substep 0.3.1's prompt named the target folder
  `final_docs/0.3-synopsis-of-today/`, but the produced folder is
  `docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/`, and that is where the SHA lives.

## The test run at that commit

Checked out in an isolated git worktree on 2026-09-18 (not a fresh clone — same effect, no
network) and run with the test command that existed at that commit.

- **Command:** `cd apps/automation && uv run --extra dev --extra tokenizers pytest -m "not db"`
  (at `bf7fece` the Makefile `test` target is bare `uv run pytest`; the `test-unit`/`test-db`
  split was added later by substep 0.5.1. No local Postgres was provisioned for this snapshot.)
- **Result:** **428 passed, 166 errors** in ~40 s.
- **What the 166 errors are:** all database tests (webhook/worker-sync ingestion, migration
  round-trips) erroring on a missing DB connection — at this commit they were not yet tagged with
  the `db` marker, so `-m "not db"` did not exclude them and they errored at fixture setup rather
  than being deselected. They are **environment errors (no database), not test failures.** A full
  green at this commit requires `make up` + `alembic upgrade head` first, which this snapshot did
  not run — recorded honestly rather than provisioning a DB to manufacture a clean number.

## Way back

`git checkout pre-target-2026-09-14` (or the commit hash to avoid the tag/branch name
ambiguity) returns the tree to the plan's starting point.
