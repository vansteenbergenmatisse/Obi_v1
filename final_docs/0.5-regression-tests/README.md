# 0.5-regression-tests

Date: 2026-09-16
Commit: uncommitted, on top of `2ac7e7a` (feat/rag-phase-3.5)
Substep: 0.5.1 · The test harness

## Files this step writes or changes

- `final_docs/0.5-regression-tests/README.md` — this file.
- `final_docs/0.5-regression-tests/harness.md` — the four commands, what each starts and
  runs, real timings, the fixture table, the coverage floor, the CI job name.
- `Makefile` (repo root) — adds `test-unit`, `test-db`, `test-ui`; documents `eval` as already
  working; leaves `test`/`check` as they were.
- `apps/automation/pyproject.toml` — registers the `db` pytest marker, `--strict-markers`.
- `apps/automation/app/platform/db/tests/test_migration_000{7,9}*.py`,
  `test_migration_0010_scope_rls.py`, `test_migration_0011_subject_hash.py` — `pytestmark =
  pytest.mark.db`.
- `apps/automation/app/features/confluence_sync/tests/test_*.py` (23 files) — `pytestmark =
  pytest.mark.db` (every test in this package needs a real Postgres via its own
  session-scoped `conftest.py`).
- `apps/automation/tests/fixtures/confluence/` — 10 new fixture pages (3001-3010), their
  `labels/`, `restrictions/`, `attachments/` entries, one new real attachment file, the
  `group_members.json` entry for the new group-restricted page, `manifest.json`, `loader.py`
  (an optional per-page `file` override so a fixture's file name can carry its id and labels),
  and `README.md` (page-mapping table).
- `apps/automation/app/features/evaluation/tests/test_fixtures_loader.py` — the pre-existing
  `test_list_pages_expected_ids` fixed for the new page count; new tests proving each new
  fixture category loads correctly through `loader.py`.
- `.github/workflows/ci.yml` — one job, the four make targets plus a coverage-floor step, on
  every pull request (no CI existed before this substep; this repo has no git remote
  configured, so no real PR could be opened to prove the workflow runs — see harness.md and
  the ledger entry).
- `apps/web/playwright.config.ts`, `apps/web/e2e/widget-mounts.spec.ts` — the browser level:
  one smoke test against the existing `/test-hosts/none` stub host page.
- `apps/web/package.json` — `@playwright/test` devDependency, the `test:e2e` script.
- `.gitignore` — Playwright's `test-results/`/`playwright-report/`/`blob-report/` artifacts.
