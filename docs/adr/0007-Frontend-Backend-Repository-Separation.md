# 0007 — Frontend/Backend Repository Separation

Status: Accepted
Date: 2026-08-10
Governs: apps/web, apps/automation, packages/**, docs/adr/0001*, docs/adr/0006*, root CLAUDE.md

## Context

`docs/adr/0006-Defer-Multi-Product-Extraction.md` recorded a deferral: do not split `apps/web`/
`apps/automation` into separate repositories or extract new packages until a second real product
("Muse") has a committed launch date and a real second database target, per the global standard's
proportionality gate ("two independent consumers exist today"). That ADR was accepted the same day
this one is written.

The user has since directed that the split happen anyway, independent of any second product's
timeline: `apps/web` (frontend) should get its own repository, `apps/automation` (backend) should
get its own repository, "because we want separation of concerns." This is a direct, explicit
instruction that overrides the deferral — the user is the authority on when a proportionality
tradeoff is worth taking ahead of its usual trigger, and has chosen to take it now for engineering
hygiene and independent deployability, not for multi-product reuse per se (though it also serves
that later goal).

This ADR records the reversal so it isn't silent, and scopes exactly what changes vs. what ADR-0006
still governs.

## Decision

1. **Split now, ahead of a second product.** `apps/web` and `apps/automation` become independently
   deployable, independently versioned codebases, each able to live in its own git repository. This
   proceeds regardless of Muse's timeline — the user has decided separation of concerns is worth the
   cost today, not contingent on a second deployment materializing.

2. **`packages/contracts` and `packages/design-tokens` become published, versioned packages**
   (private registry — see `docs/rag/PLAN.md` Phase 4.8.1 for the still-open registry-choice
   decision), not `workspace:*` links. This is the mechanical requirement of the split: a
   `workspace:*` dependency only resolves inside one pnpm workspace, and once `apps/web` leaves this
   monorepo it needs a real install target for both packages.

3. **`packages/contracts`'s existing hand-authored-on-both-sides convention is unchanged** — only its
   distribution mechanism changes (published package vs. workspace link), not the "no codegen,
   Pydantic models hand-written against the same wire shapes" design already in place.

4. **Sequencing: after the UI refactor (`docs/rag/PLAN.md` Phase 4.7), not before or during.** Splitting
   the repo while the widget's component layout is still being actively rewritten would mean either
   redoing the split or dragging an in-flight refactor across two repos mid-stream. Settle the file
   layout in the monorepo first, then move it once.

5. **What ADR-0006 still governs, unchanged by this ADR:** its Decision items 3–6 — `packages/
   design-tokens`'s single-flat-file convention stays correct until a second brand is real; ADR-0004's
   `source_type`/`source_id`/RLS model remains a different concept from a second full deployment and
   must not be treated as solving multi-deployment; no generic multi-tenant abstraction layer is
   being added by this split. This ADR reverses **only** the "don't split repos/extract packages"
   part of ADR-0006, not its reasoning about deferring speculative multi-brand abstractions.

6. **Open decisions before execution** (tracked as blockers in `docs/rag/PLAN.md` Phase 4.8, not
   guessed here): which package registry hosts `@omniboost/contracts`/`@omniboost/design-tokens`;
   names for the two new repositories; whether the origin monorepo is archived or kept as a thin
   local-dev umbrella once both extractions are verified.

## Reason

The user is the party who bears the cost of this tradeoff (more CI surfaces, a real package-publish
workflow, cross-repo coordination on contract changes) and has decided it's worth taking now rather
than waiting for a second product to force the question. Recording that as an ADR — rather than just
doing the split ad hoc — keeps the decision auditable and keeps ADR-0006's still-valid parts (the
multi-brand-abstraction deferral) from being silently swept away along with the part that changed.

## Alternatives considered

- **Leave ADR-0006's deferral in place, argue the user out of splitting early.** Rejected: this is a
  user-owned tradeoff about engineering process, not a factual question with a right answer the
  agent can adjudicate; the user gave a direct, repeated instruction.
- **Split silently without touching ADR-0006.** Rejected: leaves a durable record contradicting the
  actual codebase, which is exactly the kind of silent drift this project's documentation discipline
  (see the `docs/rag/fixes/` audit that prompted Phase 4.6) exists to prevent.
- **Fold this into a revision of ADR-0006 itself instead of a new ADR.** Rejected: ADR-0006 still
  correctly governs the multi-brand-abstraction question; rewriting it in place would lose the
  historical record of why the repo-split deferral was originally made and then reversed.

## Consequences

- `packages/contracts` and `packages/design-tokens` need a real publish pipeline before either app
  can leave the monorepo — this is new operational surface that didn't exist before.
- Cross-repo contract changes become a versioning discipline problem (a breaking change is a major
  version bump, consumed explicitly), not a same-PR atomic change across `apps/web` and
  `apps/automation` as today.
- `docs/adr/0001-Archetype-And-Stack.md` (which describes the current one-monorepo archetype) needs
  amendment or a superseding note once the split actually executes (`docs/rag/PLAN.md` Phase 4.8.6).
- Root `CLAUDE.md`'s "Layout" section, which documents the monorepo `apps/`/`packages/` tree as
  fact, needs updating once the split is real — not before, to avoid documenting a topology that
  doesn't exist yet.

## Paths governed

`apps/web/**`, `apps/automation/**`, `packages/contracts/**`, `packages/design-tokens/**`,
`docs/adr/0001-Archetype-And-Stack.md`, root `CLAUDE.md`.
