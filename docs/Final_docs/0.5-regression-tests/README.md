# 0.5-regression-tests

Date: 2026-09-18
Commit: `9a9ab3b` (feat/rag-phase-3.5), with an uncommitted working tree (the
`p0-s0_5-reg-system-overview` batch + doc updates)
Substep: 0.5 regression phase — harness (0.5.1), per-panel regression batches (0.5.2–0.5.x),
CI gate (0.5.4), and the release audit (2026-09-18)

History note: this README was first written for substep 0.5.1 (dated 2026-09-16, commit `2ac7e7a`)
and listed the files that substep changed. It was refreshed on 2026-09-18 by the release audit to
carry the current date/commit and one line per evidence file in this directory, per the audit's
Test-1 requirement.

## Evidence files in this directory

- `README.md` — this index.
- `harness.md` — the four commit-gating commands (`test-unit`/`test-db`/`test-ui`/`eval`), what each
  starts and runs, the 16 fixture pages, the coverage floor (621), and the CI job mapping. Matches
  the root `Makefile` and `.github/workflows/ci.yml` command-for-command. Contains two stale claims
  flagged by the 2026-09-18 audit: it says the repo "has no git remote" (one now exists) and its
  illustrative test counts (453 unit / 168 db) predate later batches (now 533 / 289).
- `coverage-map.md` — one row per built design panel (panel id · title · test file · test name ·
  level · green), plus a narrative section per `p0-s0_5-reg-*` batch, the `needs live` table, and the
  (empty) `red today` table. The 2026-09-18 audit found two defects here: a blank `ov-auth` row and a
  stale `w-scope` row (a panel demoted `built → change` in 0.4.2). Both are reported, not silently
  repaired.
- `ci-gate-proof.md` — the substep-0.5.4 proof that CI blocks regressions (branch protection on
  `main` requiring the check, a deliberate webhook-HMAC break, the red run, the revert, the green
  run, PR #1 closed unmerged). Carries a 2026-09-18 read-only re-verification note.
- `live-isolation-2026-09-16.txt` — the last live staging isolation run (owner-confirmed staging,
  exit 0, ADR-0004 read-path isolation green). The 2026-09-18 audit did **not** produce a fresh run —
  Test 4 is BLOCKED (no `STAGING_*` config / no this-session staging confirmation), so no
  `live-isolation-2026-09-18.txt` was created rather than fabricate one.
- `release-audit-2026-09-18.md` — the release audit of the whole regression phase: five tests, the
  full evidence, and the overall result (FAIL — Test 2 fails, Test 4 blocked; Tests 1/3/5 pass).
- `regression-decisions.md` — the owner's settled calls (2026-09-14) the regression panels build
  their defaults to: embedding model, accuracy-before-speed, folder move, embedded scoping, note
  rules, platform order, translation, keyword-index language, cost-per-question, support judge,
  hosting, dev webhook, plus the three still-open numbers (freshness target, worst-case latency
  budget, rerank depth). `docs/plan/decisions.md` points here for the settled list.

## Commands (all from the repo root)

```
make test-unit   # fakes only, no DB/network        (-m "not db")
make test-db     # local pgvector compose, RLS on, rolled back per test   (-m db)
make test-ui     # the widget's Playwright smoke suite against a stub host page
make eval        # the retrieval evaluation baseline over the bundled datasets
```

CI (`.github/workflows/ci.yml`) runs all four on every pull request, gated by a coverage-floor step
(`pytest --collect-only` ≥ 621).
