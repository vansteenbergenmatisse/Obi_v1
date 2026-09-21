# 1.1.3 · Fresh-session CLAUDE.md check

Substep 1.1.3 step 4: open a **fresh** Claude Code session (empty context), run `/context`,
then ask the two questions below. A rewritten CLAUDE.md passes if a naive agent — reading
only the file, with no prior conversation — answers with the new paths.

This scaffold is filled by the owner running the fresh session (this session cannot open a
genuinely context-free one). Paste each answer verbatim under its question.

**Provisional check recorded 2026-09-21.** A genuinely context-free *subagent* (no conversation
history, instructed to read only the repo `CLAUDE.md` and nothing else) was asked the two
questions. Its answers are recorded below and both name the new paths. This is the closest
proxy available from within a working session; it is **not** a substitute for the owner opening
a real fresh `/context` session, which remains the authoritative run. Treat the verdict as
PASS (provisional) until the owner replaces these two answers with a real fresh-session transcript.

## `/context`

Fresh context-free subagent; single file loaded (`CLAUDE.md`), no codebase exploration. (Owner:
replace with the real `/context` output when you run the true fresh session.)

## Q1 — "where does ingestion code live?"

**Expected:** `backend/app/features/ingestion/`

**Fresh-session answer:**

`backend/app/features/ingestion` — derived from `CLAUDE.md:38` (root is `backend/`) + `CLAUDE.md:41`
("`app/features/ingestion/` owns stages 3 and 4: normalize, chunk, contextualize, attachments,
embed, version, swap, garbage collection, rollback."), corroborated by `CLAUDE.md:73`
("`backend/app/features/<feature>/`").

## Q2 — "where do migrations live?"

**Expected:** `knowledge-base/migrations/versions/`

**Fresh-session answer:**

`knowledge-base/migrations/versions` — derived from `CLAUDE.md:50` (root is `knowledge-base/`) +
`CLAUDE.md:52` ("`migrations/versions/` holds numbered migrations, each with a downgrade; every
schema change on the design page lives in one migration."), corroborated by `CLAUDE.md:71`.

## Verdict

**PASS (provisional).** Both answers name the new paths and match the Expected values. Method
caveat: a fresh context-free subagent, not a true `/context` session — the owner's real fresh
session is still owed and, when run, its two answers replace the provisional ones above.
