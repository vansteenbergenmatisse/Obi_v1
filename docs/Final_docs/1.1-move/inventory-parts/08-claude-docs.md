# Inventory 08 — .claude/ and project CLAUDE.md path strings

Scope: `.claude/**` and the project-root `CLAUDE.md`. Substep 1.1 move renames
`apps/web → frontend/`, `apps/automation → backend/`, and moves db/migrations/config/seed/local → `knowledge-base/`.

Grep terms: `apps/web`, `apps/automation`, `infra/foundation`, `config/knowledge_scopes`,
`platform.db`, `tools/panel.py`, `tools/brief.py`, `tools/agent_guard.py`, `alembic`.

Notes:
- No `.claude/hooks/` directory exists. No `.claude/settings.json`. Hooks are declared
  inline in the agent `.md` frontmatter (obi-tester/obi-auditor/obi-implementer).
- No hits for `apps/web`, `infra/foundation`, `config/knowledge_scopes`, or `platform.db`
  anywhere under `.claude/` or the project `CLAUDE.md`.
- Classification: **PATH-ONLY** = safe to edit as a string now in this move.
  **STRUCTURE PROSE** = defer to substep 1.1.3 (the CLAUDE.md structure rewrite).

---

## .claude/settings.local.json

- `6`: `"Bash(find '.../RAG-TOAST-omniboost/apps/automation/app/features/retrieval' -type f -name *.py)"` — **PATH-ONLY** (stale permit; path becomes `backend/...`; note the repo dir differs — `RAG-TOAST-omniboost` not `-version2`).

## .claude/agents/obi-tester.md  — CRITICAL (hook)

- `12`: `command: python3 "$CLAUDE_PROJECT_DIR/apps/automation/tools/agent_guard.py" tester` — **PATH-ONLY**, HOOK command.

## .claude/agents/obi-auditor.md  — CRITICAL (hook)

- `13`: `command: python3 "$CLAUDE_PROJECT_DIR/apps/automation/tools/agent_guard.py" auditor` — **PATH-ONLY**, HOOK command.
- `19`: ``Read design panels with `python3 apps/automation/tools/panel.py <id>`.`` — **PATH-ONLY** (executable ref in prose).

## .claude/agents/obi-implementer.md  — CRITICAL (hook)

- `13`: `command: python3 "$CLAUDE_PROJECT_DIR/apps/automation/tools/agent_guard.py" implementer` — **PATH-ONLY**, HOOK command.
- `18`: ``Read the substep and every panel it names with `python3 apps/automation/tools/panel.py <id>`;`` — **PATH-ONLY** (executable ref).

## .claude/skills/obi-change/SKILL.md  — CRITICAL (executable refs)

- `13`: ``For every panel id in refs: `python3 apps/automation/tools/panel.py <id>`.`` — **PATH-ONLY**.
- `25`: ``For each panel closed: `python3 apps/automation/tools/panel.py <id> --status <word> --today "..."`.`` — **PATH-ONLY**.
- `26`: ``Regenerate the brief: `python3 apps/automation/tools/brief.py`.`` — **PATH-ONLY**.

## .claude/skills/obi-verify/SKILL.md

- `8`: `...its targets cd into apps/automation themselves, so call make from the root — never cd apps/automation && make.` — **PATH-ONLY** (prose refs to executable path).
- `14`: `| lint + types | cd apps/automation && uv run ruff check . ; ... pyright | ...` — **PATH-ONLY** (executable command).
- `17`: `| live ... | cd apps/automation && uv run python scripts/setup_supabase.py verify-isolation && ...` — **PATH-ONLY** (executable command).

## .claude/skills/obi-audit/SKILL.md

- `4`: `allowed-tools: ... Bash(python3 apps/automation/tools/panel.py:*)` — **PATH-ONLY** (tool-permit path).
- `10`: ``for each panel ... run python3 apps/automation/tools/panel.py <id>; ... python3 apps/automation/tools/panel.py --grep <folder name> ...`` — **PATH-ONLY** (two occurrences).

## CLAUDE.md (project root)

- `23`: `make migrate     # alembic upgrade head` — **PATH-ONLY** (command text; `alembic` term, no path change unless migrations relocate under `knowledge-base/`; keep as `alembic upgrade head` — verify Makefile target after move).
- `55`: `<!-- Phase 1 of the plan moves apps/web → frontend/, apps/automation → backend/, ... Rewrite this section then and delete this note. -->` — **STRUCTURE PROSE** — defer to 1.1.3 (this is the "Where things go" section rewrite the comment itself schedules).

---

## Critical items (break after the move if not updated)

The three inline HOOK commands hardcode `$CLAUDE_PROJECT_DIR/apps/automation/tools/agent_guard.py`
(obi-tester.md:12, obi-auditor.md:13, obi-implementer.md:13). If `apps/automation → backend/`
and these are not updated to `backend/tools/agent_guard.py`, every obi-* subagent's guard hook
fails to launch → the substep-lock enforcement silently breaks.

Same risk for the executable `panel.py` / `brief.py` refs in obi-change, obi-audit, obi-tester,
obi-implementer, and the `cd apps/automation` commands in obi-verify — the panel/brief tooling
and verify table stop working until repointed to `backend/`.
