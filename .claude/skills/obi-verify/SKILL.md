---
name: obi-verify
description: Run every Obi test level and print one summary table. Use before marking any substep done, after any change, and when asked whether it is green.
allowed-tools: Bash(make:*), Bash(uv run:*), Bash(pnpm:*), Bash(docker:*), Read, Glob
---
# /obi-verify

Run from the repository root. The Makefile is at the repository root and its targets `cd` into backend themselves, so call `make` from the root — never `cd backend && make`. Run every level below in order and print one table. Commands and results only.

| level | command | pass rule |
|---|---|---|
| unit | make test-unit | exit 0 (every test NOT marked `db`) |
| database | make test-db | exit 0 (every `db`-marked test, against the local pgvector Postgres, migrated to head, both roles and all policies applied) |
| lint + types | cd backend && uv run ruff check . ; uv run ruff format --check . ; uv run pyright | counts not above the baseline in docs/plan/baseline.md; if that file is missing or says "no baseline yet", PASS with note "no baseline yet" |
| browser | make test-ui | exit 0; if the target does not exist print "not wired yet" |
| eval | make eval | prints recall@75, P@5, NDCG@10, refusal rate; none below docs/plan/baseline.md; if that file is missing or says "no baseline yet", PASS with note "no baseline yet" |
| live (only if STAGING_DATABASE_URL is set) | cd backend && uv run python scripts/setup_supabase.py verify-isolation && uv run python scripts/verify_knowledge_scope_backfill.py | both exit 0; if the var is unset print "skipped" |

Baseline: read docs/plan/baseline.md once. A missing file, or a numbered line reading "no baseline yet", is not a failure — report the level PASS with the note "no baseline yet". A real number that is exceeded (lint/type counts rose, or an eval metric fell) is RED.

Output:

| level | command | result | seconds | note |
|---|---|---|---|---|

Under the table: the first failing assertion verbatim with file and line. Nothing else.
Final line: GREEN if every wired level passed and no baseline rose; otherwise RED and the levels that failed.
Never fix anything. Never skip a level silently: a level that cannot run prints "not wired yet" and the missing command.
