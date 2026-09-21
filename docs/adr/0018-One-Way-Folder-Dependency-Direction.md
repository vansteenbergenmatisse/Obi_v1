# 0018 — One-Way Folder Dependency Direction

Status: Accepted
Date: 2026-09-18
Governs: the three top folders `frontend/`, `backend/`, `knowledge-base/`; `backend/tools/check_feature_boundaries.py`

## Context

Phase 1 (substep 1.1.1) split the code into three top folders — `frontend/`, `backend/`,
`knowledge-base/` — so the three parts can eventually become separate repositories. For that split
to hold, the dependency arrow must point one way only: `frontend → backend → knowledge-base`. A rule
with no checker erodes by the third pull request (the same reasoning as ADR-0003 for the intra-backend
feature boundaries). Substep 1.1.2 adds the enforcement.

During 1.1.1 the DB layer (`engine.py`, `models.py`) and `alembic/env.py` still imported
`app.platform.config`; that would have made `knowledge-base` depend on the backend and violated this
rule. They were repointed at a self-contained `knowledge-base/schema/settings.py`, so knowledge-base
is standalone before this rule is enforced.

## Decision

Extend the existing ADR-0003 checker (`backend/tools/check_feature_boundaries.py`) — do not add a
second script — with a repo-root pass carrying three rules, as data (a fifth rule later is one line):

1. **knowledge-base/** (`*.py`) must not import `app`, `features`, `platform` or `shared`. Its own
   package is `schema`; it imports nothing from the backend.
2. **backend/** (`*.py`) must not import `frontend`.
3. **frontend/** (`*.ts,*.tsx,*.js,*.jsx`) must not import a specifier that reaches into `backend/`
   or ends in `.py`. It may still *read* `knowledge-base/config/knowledge_scopes.json` at build/run
   time via a filesystem path (a `resolve()` string, not an import), which this rule does not touch.

The four intra-backend feature rules from ADR-0003 are unchanged and still run. The checker runs
inside `make test-unit` (via a `boundaries` prerequisite) and therefore in the CI unit job.

## Consequences

- A wrong-way import fails the unit level and CI, naming the file and line.
- `backend/tests/tools/test_boundaries.py` proves each rule with a negative case (a temp file under
  the real folder) plus a clean-tree positive case: `test_sec_boundary_kb_cannot_import_backend`,
  `test_sec_boundary_backend_cannot_import_frontend`, `test_sec_boundary_frontend_cannot_reach_backend`,
  `test_sec_boundary_clean_tree_passes`.
- The frontend rule scans import specifiers only (a lightweight regex, since the checker parses no
  TypeScript); a filesystem read of the tag list is intentionally allowed.
- Related: ADR-0003 (feature/platform/shared boundaries, the checker this extends).
