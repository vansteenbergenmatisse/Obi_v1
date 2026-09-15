# Code-vs-design audit — 2026-09-14 (substep 0.3)

_Folder: `0.3-code-vs-design-audit-2026-09-14`._

## What this folder is (read this first)

A **point-in-time, read-only audit of Obi's codebase measured against the design page.**
On 2026-09-14, at one pinned commit, ten independent auditor agents each read one code
folder and wrote a synopsis: what the folder actually does, proved line by line, and how
each of its design claims holds up. Think of it as *"here is the truth of the code today,
next to what the design page says should be true, with every disagreement named."*

It answers a single question for every part of the system:
**does the code do what the design page claims — and if not, exactly how does it differ?**

Nothing here changes code. Nothing here is edited after substep 0.3 closed — it is a frozen
snapshot. To audit a *later* commit, make a new sibling folder (e.g. `0.9-synopsis-of-...`),
don't overwrite this one.

## Why it exists

The design page (`docs/Final_docs/obi-rag-system-flow (3).html`, 192 "panels") is the source
of truth for what each stage *should* do. Code drifts from it over time. Before planning any
implementation work, you need an honest, evidence-backed map of the gap. These ten files are
that map — the input to the delta list and the work plan (`docs/plan/delta.md`).

## What's inside

Eleven synopses (ten folders + the entrypoint file), plus this README:

| file | the folder it audits | in one line |
|---|---|---|
| `confluence_sync.md` | `app/features/confluence_sync` | webhook, event ledger, job queue/worker, sweeps, change classification, labels→scope |
| `ingestion.md` | `app/features/ingestion` | normalize, chunk, contextualize, embed, version, swap, GC, rollback |
| `retrieval.md` | `app/features/retrieval` | hybrid search, fusion, page permissions, rerank wiring, trace writes |
| `rag_agent.md` | `app/features/rag_agent` | the chat endpoint, auth/limits, small talk, rewrite, refusal, generation, citations |
| `evaluation.md` | `app/features/evaluation` | the gold-set runner, metrics, datasets |
| `platform.md` | `app/platform` (clients, config, jobs, db) | DB models, roles/RLS policies, API clients, settings, job queue, logging |
| `shared.md` | `app/shared` | small cross-feature primitives: hashing, rate limiter, TTL cache |
| `alembic-and-scripts.md` | `alembic/` + `scripts/` | numbered migrations (+downgrades) and operator scripts |
| `widget.md` | `apps/web` | the Next.js widget: UI, proxy route, embed frame, loader, i18n, JWT handshake |
| `packages-config-infra-docs.md` | `packages/` + `config/` + `infra/` + `docs/` | shared contracts/tokens, the tag/platform JSON, docker-compose, docs |
| `entrypoint.md` | `app/main.py` (+ `app/__init__.py`) | the composition root: startup, settings, engine/session wiring, retriever + answer-service + scheduler construction, the two router mounts |

## How each synopsis is structured

Every file follows the same eight-section `/obi-audit` template, so they read alike:

1. **Purpose** (two lines) — what the folder is for.
2. **Entry points** — the symbols other code calls in, with `file:line` and caller.
3. **Reads and writes** — tables, files, queues touched (read vs write), with `file:line`.
4. **External calls** — clients/endpoints and whether timeout/retry/breaker are present.
5. **Tests present** — test files, what they assert, and which panels they protect.
6. **Known gaps** — TODOs, dead code, untested behavior; one line each with `file:line`.
7. **Claims from the design** — the heart: one row per design claim → `file:line` → verdict.
8. **Not on the design page** — code in the folder that no panel mentions.

## How to read a verdict (section 7)

Each design claim carries exactly one of four verdicts:

- **confirmed** — the code matches the panel's "today" line.
- **drifted** — it exists but differs; the row says *exactly how* (often a stale line number, or a value/shape that changed).
- **missing** — not found in this folder. Frequently the code is real but lives in another folder — the note says `owned by <folder>`. That is expected: a panel's grep-hit folder is not always its owner.
- **needs live** — only checkable against staging/production (e.g. the deployed embedding model, `.env`-driven values, "applied to Supabase" claims).

## Two caveats before you trust a row

- **Line numbers drift.** The design page pins `file:line`; code has moved since. Many "drifted"
  verdicts are just an off-by-a-few line reference, not a behavior change — read the note.
- **The design page is itself stale in places.** Several panels marked "planned / does not exist"
  are in fact already built and live-proven (notably the per-user JWT auth and the widget embed
  handshake). A "drifted" verdict can mean *the code is ahead of the page*, not behind it.

## Ground truth audited

- **Commit:** `bf7fece829e3ce1e9757e1bdb5fa538fbd6456ae`
- **git describe:** `green-baseline-151-gbf7fece`
- **Date:** 2026-09-14
- **Design page:** `docs/Final_docs/obi-rag-system-flow (3).html` (read via `tools/panel.py`; 192 panels)
- **Produced by:** ten `obi-auditor` subagents (substep 0.3.1), one per folder, run in parallel then reconciled.

## Assignments

| # | folder path | output file | lines | agent | done |
|---|---|---|---|---|---|
| 1 | `apps/automation/app/features/confluence_sync` | `confluence_sync.md` | 134 | obi-auditor | ✓ |
| 2 | `apps/automation/app/features/ingestion` | `ingestion.md` | 129 | obi-auditor | ✓ |
| 3 | `apps/automation/app/features/retrieval` | `retrieval.md` | 131 | obi-auditor | ✓ |
| 4 | `apps/automation/app/features/rag_agent` | `rag_agent.md` | 105 | obi-auditor | ✓ |
| 5 | `apps/automation/app/features/evaluation` | `evaluation.md` | 80 | obi-auditor | ✓ |
| 6 | `apps/automation/app/platform` (clients, config, jobs, db) | `platform.md` | 144 | obi-auditor | ✓ |
| 7 | `apps/automation/app/shared` | `shared.md` | 71 | obi-auditor | ✓ |
| 8 | `apps/automation/alembic` + `apps/automation/scripts` | `alembic-and-scripts.md` | 109 | obi-auditor | ✓ |
| 9 | `apps/web` | `widget.md` | 149 | obi-auditor | ✓ |
| 10 | `packages/` + `config/` + `infra/` + `docs/` | `packages-config-infra-docs.md` | 86 | obi-auditor | ✓ |
| 11 | `apps/automation/app/main.py` (+ `app/__init__.py`) | `entrypoint.md` | 84 | obi-auditor | ✓ |

_Row 11 (the entrypoint / composition root) was added as a coverage-completion pass after the initial ten; the substep's original list did not name `app/` as its own assignment._

## Coverage

Every panel id from `python3 apps/automation/tools/panel.py --list` (192) has at least one
row in one synopsis. **Coverage: 192/192.** All eleven files carry the eight template sections.

### Reconciliation (substep step 7)

Nineteen ids had no row after the first pass and were reassigned to the closest folder's
agent, which re-ran to add them:

- **confluence_sync**: `ov-confluence` `i2-nochange` `tg-purge` `tg-state` `tg-filter` `ks-orphan`
- **rag_agent**: `r1-short` `r5-dedupe` `r5-nocite` (this file's final heading was also corrected from `## Not on design page` to `## Not on the design page`)
- **platform**: `s-anon` `s-audit` `vd-text` `vd-question`
- **evaluation**: `e-split` `e-stage3` `e-stage4` `e-judge`
- **retrieval**: `r3-deny` `r4-proceed`

Note: `s-user` was named in the shared assignment but is **not a real panel id**, so it was dropped, not reassigned.

## What was NOT audited here (scope honesty)

The eleven assignments cover all runnable code that carries design panels — including the
entrypoint (`entrypoint.md`, added as row 11). For completeness, these remaining areas have
no synopsis of their own, and none carry design panels:

- `apps/automation/tools/` — the audit tooling itself (`panel.py`, `brief.py`, `agent_guard.py`); meta, no panels.
- `apps/automation/tests/tools/` and repo-root `tests/` (just `TESTING.md`) — test scaffolding.
- `apps/automation/eval-reports/` — generated data artifacts, not source.
