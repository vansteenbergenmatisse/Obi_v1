# 1.1.3 · Fresh-session CLAUDE.md check

Substep 1.1.3 step 4: open a **fresh** Claude Code session (empty context), run `/context`,
then ask the two questions below. A rewritten CLAUDE.md passes if a naive agent — reading
only the file, with no prior conversation — answers with the new paths.

This scaffold is filled by the owner running the fresh session (this session cannot open a
genuinely context-free one). Paste each answer verbatim under its question.

## `/context`

<!-- paste the /context output (or a one-line note that it loaded CLAUDE.md) -->

## Q1 — "where does ingestion code live?"

**Expected:** `backend/app/features/ingestion/`

**Fresh-session answer:**

<!-- paste here -->

## Q2 — "where do migrations live?"

**Expected:** `knowledge-base/migrations/versions/`

**Fresh-session answer:**

<!-- paste here -->

## Verdict

<!-- PASS if both answers name the new paths; otherwise note the gap and it becomes the next ledger task -->
