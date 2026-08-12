# 0010 — Re-defer Frontend/Backend Repository Separation

Status: Accepted
Date: 2026-08-12
Governs: apps/web, apps/automation, packages/**, docs/adr/0006*, docs/adr/0007*, docs/rag/PLAN.md,
docs/future-ideas/IDEAS.md

## Context

`docs/adr/0007-Frontend-Backend-Repository-Separation.md` (2026-08-10) reversed ADR-0006's deferral
and scheduled the split as `docs/rag/PLAN.md` Phase 4.8, ahead of any second product/deployment, for
separation-of-concerns and independent-deployability reasons. That phase never started — it sat
blocked on three "needs your input" decisions (registry choice, two new repo names, origin-monorepo
fate) through Phase 7's entire lifecycle.

Revisiting on 2026-08-12: the user reconsidered and does not currently have real answers to those
three decisions, and nothing about the split can be validated without a live second consumer to
design the seam against — exactly the concern ADR-0006 originally raised. Nothing is live yet: no
second product/deployment exists, no registry has been chosen, and no repo-naming/ops work has
actually happened beyond the phase's own text. In the user's own words, this is something wanted "in
future," not now, and belongs in `docs/future-ideas/IDEAS.md` rather than as a phase in the active
plan.

## Decision

1. **Re-defer the split.** ADR-0007's Decision item 1 ("split now, ahead of a second product") is
   reversed. ADR-0006's original Decision items 1–2 (no structural change now) are back in force.
2. **Phase 4.8 is removed from `docs/rag/PLAN.md`'s active scope.** Its content (goal, all seven
   sub-steps, the three open decisions) moves to `docs/future-ideas/IDEAS.md` as a fully-detailed,
   unscheduled idea — not deleted, per that file's own history-preservation convention.
3. **Phase 9's sequencing simplifies.** Phase 9 (9.2 onward) was sequenced after "Phase 7 + Phase
   4.8" per prior direction; with 4.8 removed from the plan, that dependency drops — Phase 9 now
   waits only on Phase 7 (already done).
4. **ADR-0007's Decision items 2–6** (published-package mechanics, the hand-authored-contracts
   convention, the "settle 4.7's layout first" sequencing note, what ADR-0006 still governs, the
   three open decisions) remain an accurate historical record of the reasoning **if and when** this
   is revisited — they are not being re-litigated, only un-scheduled.
5. **Trigger to revisit, mirroring ADR-0006's original trigger:** a real second product/deployment
   with a committed launch date, or the user separately deciding the three open decisions (registry,
   repo names, monorepo fate) with enough conviction to actually execute. Either trigger reopens this
   as a real PLAN.md phase, not an ad hoc restart.

## Reason

Scheduling a phase ahead of the decisions it needs to execute produces a phase that can only ever sit
blocked — exactly what happened here. ADR-0006's original reasoning (extracting packages/repos ahead
of a real second consumer is speculative generality; reversing a premature split later is more
expensive than deferring it now) never stopped applying; ADR-0007 accepted that cost deliberately,
and the user has now decided that trade isn't worth carrying in the active plan while nothing is
live. Moving it to `IDEAS.md` keeps the detailed design work (registry options, extraction mechanics,
CI/secrets split, doc updates) from being lost, without it blocking Phase 9 or falsely reading as
"next up."

## Alternatives considered

- **Leave Phase 4.8 in PLAN.md, unblocked, waiting for the three decisions.** Rejected: it has sat
  blocked since 2026-08-10 with no path to an answer; keeping it in the active plan misrepresents it
  as near-term work.
- **Delete the phase's content outright instead of moving it.** Rejected: violates this project's
  documentation discipline (nothing gets silently dropped — see `docs/rag/fixes/` and IDEAS.md's own
  "not deleting history" convention); the detailed sub-step breakdown is real design work worth
  keeping for whenever this is revisited.
- **Amend ADR-0007 in place rather than writing a new ADR.** Rejected: same reasoning ADR-0007 itself
  gave for not amending ADR-0006 in place — it would lose the historical record of why the split was
  scheduled and then un-scheduled.

## Consequences

- `docs/rag/PLAN.md`'s Phase 4.8 section, its status-ledger references, its phase-table row, and its
  Phase-9 sequencing text are all updated to remove the phase and drop the "+ Phase 4.8" dependency.
- `docs/future-ideas/IDEAS.md` gains a new, fully-detailed idea entry (registry options, extraction
  mechanics, monorepo-fate options, CI/secrets split, doc updates, the three open decisions) so no
  design work already done is lost.
- `docs/adr/0001-Archetype-And-Stack.md` needs no amendment — it was never amended for 4.8 since 4.8
  never executed, so the monorepo archetype it documents remains accurate as-is.
- If revisited later, whoever picks this up should re-read ADR-0006, ADR-0007, and this ADR in order
  before restarting, not just resume mid-phase.

## Paths governed

`apps/web/**`, `apps/automation/**`, `packages/contracts/**`, `packages/design-tokens/**`,
`docs/rag/PLAN.md`, `docs/future-ideas/IDEAS.md`, `docs/adr/0006*`, `docs/adr/0007*`.
