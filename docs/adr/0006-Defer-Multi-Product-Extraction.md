# 0006 — Defer Multi-Product Extraction

Status: **Superseded by 0007 (2026-08-10)** — the repo/package-split deferral in Decision items 1–2
below no longer holds; the user directed the actual split to proceed regardless of a second product's
timeline, for separation of concerns. See `docs/adr/0007-Frontend-Backend-Repository-Separation.md`
for the current decision. Kept for history — Decision items 3–6 (design-tokens' single-file
convention, ADR-0004 not being the multi-deployment mechanism) are unaffected and still apply.
Date: 2026-08-10
Governs: apps/web, apps/automation, packages/**, docs/future-ideas/IDEAS.md

## Context

The product intends to eventually reuse this same frontend (`apps/web`) and backend
(`apps/automation`) for a second product — working name "Muse" — that has its own knowledge base
(its own Postgres database/vector store) but the same functionality: chat UI, retrieval pipeline,
citations, feedback, security controls. Muse is a **second full deployment** of the same codebase,
not a tag inside Toast's existing corpus — a distinct concept from ADR-0004's `source_type`/
`source_id`/`tags` model, which isolates multiple *sources* inside **one** deployment's **one**
database. Confusing the two would misdirect design work: ADR-0004 does not, by itself, give you a
second product.

Today there is exactly one real consumer: Omniboost/Toast. Muse has no committed launch date and no
real second Postgres instance. The user's global standard's Proportionality Gates set the bar for a
new shared package at "two independent consumers exist today," and for a new abstraction/layer at
"no existing repository pattern expresses the requirement" — neither is met yet. The Brownfield
Preservation rule requires an accepted ADR before changing the folder structure absent a concrete
requirement. This ADR records that the requirement is real but not yet due, so the deferral is
explicit rather than silent.

Separately, the user identified a genuinely different, smaller-scoped need that *is* a tagging
problem inside one deployment: a single customer within one deployment (e.g. Toast) can have
**multiple instances of the same connector** (e.g. two separate QuickBooks accounts), and retrieval
should be scoped to the relevant connector instance, not the whole corpus for that integration.
This is tracked separately in `docs/future-ideas/IDEAS.md` idea #4 as an extension of ADR-0004's
existing tag model, not part of this ADR.

## Decision

1. **No structural change now.** Do not extract a new shared package, do not split into multiple git
   repos, and do not add a generic multi-tenant/multi-brand abstraction layer (a theme registry, a
   deployment-config service, a tenant resolver). None of these are justified by a consumer or
   requirement that exists today.

2. **A second full deployment already works with zero code changes**, because the architecture is
   already environment-driven where it matters: `apps/automation/app/platform/config/settings.py`
   reads every product/brand-sensitive value (`DATABASE_URL`, Confluence/connector credentials,
   model names, `CHAT_API_KEY`) from `Settings`, overridable by env var, with no product-specific
   literal baked into logic. Standing up Muse as a second deployment today would mean running the
   same checkout against a second `.env` — a deployment/ops action, not a refactor.

3. **`packages/design-tokens`'s single flat token file is correct as-is.** Its existing convention
   (documented in its own file header: "when the brand is applied, only the values change, not
   their names") already supports swapping *one* brand's values at a time. Do not add a `themes/`
   subfolder or a brand-selection layer until a second brand is real — that is new abstraction with
   no current requirement to express.

4. **The two cosmetic "Omniboost" UI strings are optional, not required, to change now.**
   `apps/web/src/app/page.tsx`'s heading and `apps/web/src/app/layout.tsx`'s `metadata.title` are the
   only hardcoded product-name strings found in real (non-mockup) code; both are decorative, not
   functional. Leave them as literals unless/until a second deployment is real — introducing an env
   var for two strings ahead of a second consumer is unnecessary layering.

5. **`ADR-0004` is not the multi-deployment mechanism and must not be treated as one.** It isolates
   multiple knowledge *sources* inside one deployment's one database via `source_id`/RLS. Muse, as a
   second full deployment, gets its own database entirely — ADR-0004's mechanism is orthogonal, not
   a prerequisite or a substitute.

6. **Trigger to revisit:** a committed launch decision for Muse (or any second product) **and** a
   real second Postgres connection target. At that point, open an ADR-gated phase (mirroring how
   Phase 6/Supabase and the Bedrock future-direction note in `docs/rag/PLAN.md` are already handled)
   before doing any extraction work — not an ad hoc refactor.

## Reason

Extracting packages or splitting repos ahead of a real second consumer would be speculative
generality: the shape of what Muse actually needs (which values must vary, which don't, whether it
shares `packages/contracts` verbatim or needs its own wire extensions) is unknowable until Muse is a
real deployment target. Reversing a premature split later is more expensive than deferring it now.
Meanwhile, the architecture's existing env-driven config already gives the cheap version of "reuse
the same code for a second deployment" for free — there is no gap to close today, only a decision to
record so it isn't silently forgotten or silently assumed to already be solved by ADR-0004.

## Alternatives considered

- **Extract `apps/web` + `packages/*` into a template/reusable repo now.** Rejected: no second
  consumer exists to validate what the template boundary should actually be; guessing it now risks
  building the wrong seam.
- **Add a multi-brand theming layer to `packages/design-tokens` now.** Rejected: no second brand
  exists to design against; the current single-flat-file convention already supports one-brand-at-
  a-time swaps at zero cost.
- **Treat ADR-0004's `source_type`/`tags` model as already solving multi-deployment.** Rejected:
  conflates two different isolation units (source-within-one-DB vs. a whole second DB) and would
  misdirect a future Muse design toward tagging Toast's own corpus instead of standing up a real
  second deployment.

## Consequences

- No new packages, repos, or abstraction layers are created by this ADR — it is a recorded
  deferral, not new structure.
- Standing up Muse later requires no retroactive refactor of `apps/automation`'s config layer; it
  does require a new ADR-gated phase to decide what (if anything) about `packages/contracts` or
  `packages/design-tokens` needs to branch or extend once Muse's real requirements are known.
- `docs/future-ideas/IDEAS.md` idea #4 is corrected to stop conflating "Muse vs. Toast" (a
  deployment split, governed by this ADR) with "multiple connector instances within one deployment"
  (a real tagging extension of ADR-0004, still a future idea, not built now).

## Paths governed

`apps/web/**`, `apps/automation/app/platform/config/settings.py`, `packages/contracts/**`,
`packages/design-tokens/**`, `docs/future-ideas/IDEAS.md`.
