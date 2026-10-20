# 5 · Integration context (roadmap Step 5, §D.1) — index

The single home for the §D.1 "Complete integration context" **design + data deliverable**
(`docs/Final_docs/plan.md` §D.1, built strictly on the owner decisions of record in §D.13).
Same rule as `4-test-foundation/`: anything about the shared integration-context contract goes
here; look here first. This folder began as design documentation plus one data file
(`knowledge-base/config/product_catalog.json`).

> **Current contract (2026-10-20).** Partners (Base and the Data Hub, the only two that embed Obi)
> send the **directed token**: `iss`, `aud: "obi"`, `sub`, `iat`, `exp` (at most the platform's
> `lifetime_minutes`, 60), `source_system`, `target_system`, `business_id` (string or integer;
> integers are normalized to a string). Display names resolve case- and space-insensitively.
> Routing rides the routing labels (ADR-directed-source-target-routing-labels); the knowledge-scope
> axis is retired (ADR-routing-labels-sole-content-axis).
>
> **Only the source decides whether Obi shows** (ADR-source-system-decides-widget-eligibility,
> 2026-10-20). `enabled_sources` in `knowledge-base/config/product_catalog.json` is `mews`, `toast`,
> `opera-cloud`. An unknown or disabled source hides the widget (403 `source_not_enabled`; the
> visibility probe answers `visible: false`). The target is never checked; an unknown target routes
> on `[obi-general, {source}-general]`.
>
> The three-slot `context.slots` contract and the single `integration` claim described in
> `legacy-three-slot-context-contract.md` and `integration-token-decisions.md` are **legacy**: still accepted, no longer routing.
>
> How a partner integrates, step by step:
> [`how-partners-integrate-with-obi.md`](../1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md).

> **History (2026-10-09).** The §D.1 design was implemented in substeps 8.1.1–8.5.1 (the three-slot
> token, the catalog loader, the gate's slot checks, chunk applicability in migration 0015, the
> launch allowlist); the frontend was deployed in 8.4.3. Phase 9 then replaced slot routing with the
> directed form above. The "What this did NOT change" section below is kept for history only.

- `legacy-three-slot-context-contract.md` — **legacy** (superseded by the directed form): the original shared
  context contract for all environments (Base, Data Hub, standalone): the three-slot token (POS/PMS from Data Hub, Accounting from Base), company-ID-only
  identity, token-over-body trust (never-bend rules 2–3), known/absent/unknown configuration, the
  launch allowlist (Toast=POS, Mews=PMS) with the exact visibility rule, eligibility derivation
  (general + filled slots + the pairs the company actually has), how the §D.2 flow types map onto
  slot pairs — including why Toast+Mews+QuickBooks does **not** imply a direct Toast→QuickBooks
  pair — and four concrete token examples.
- `integration-token-decisions.md` — the token/API extension decision memo §D.1 requires. Records the §15
  keuzes 1–4 verbatim as decided in §D.13 item 3, the compatibility behavior for old
  single-integration tokens and legacy alias values, the exact delta this implies for
  `packages/contracts/` (token claims + OpenAPI, as a TODO-for-implementation table with today's
  real field names, file-referenced), what the backend gate must validate, and the honest list of
  items the owner has **not** decided yet (each with a pointer to the §D part that will decide it).
- `product-catalog.md` — documentation of the new central product catalog
  (`knowledge-base/config/product_catalog.json`): every field, the validation rules a future
  loader must enforce, how to add a product, how aliases resolve (the `legacy_aliases` table is
  empty today — the once-illustrative `toast-opera` value was confirmed in §D.16/O8 to exist in no
  config, code, token or tag and is **not** a real alias), and the rule that **nothing else in the
  repo may define a product**.
- `reranker-api-wiring-notes.md` — read-only findings on the reranker as actually wired (Cohere
  `rerank-v3.5` via v2, string-documents only, **no instruction field exists**), the
  eligibility-before-rerank invariant, and the ranked options for the §D.6 build (enrich the
  query string + YAML metadata in document strings; `rank_fields` is v1-only escalation).
- `partner-facts.md` — per partner (Base/Marien, Data Hub/Jasper): which of the five
  integration facts are confirmed and which are missing. The status page to check first.
- `partner-activation-patch.md` — the pre-staged `platforms.json` block per partner; not applied.
- `directed-routing-partner-reply-drafts.md` — the owner's drafts of the directed-contract replies to the partners.
- `directed-routing-security-review.md`, `directed-routing-isolation-run.txt` — Phase 9
  security review and isolation/reversibility proof for the directed form.
- `human-validation-cases.md`, `human-validation-fill-in-worksheet.md` — Phase A human validation cases and the
  fill-in run sheet (prepared, not run).
- `applies-to-authoring.md` — how page authors fill the "Applies to" table.
- `embed-live-check-output.txt` — the 8.4.3 live embed check output. obi.js is served at
  `https://obi-web-production.up.railway.app/obi.js` (frame at `/embed`).

## What this did NOT change in the original design pass (now superseded — all landed)

At authoring, this deliverable was design + data only. Everything listed below has **since been
implemented** (substeps 8.1.1–8.5.1); the list is kept for history. Read each "no change" item as
"designed here, wired later":

- **No backend behavior changes.** No loader, no validator, no gate change, no migration, no
  retrieval change is wired. The catalog JSON sits unread by any code until its implementation
  substep lands (the loader is an implementation TODO recorded in `product-catalog.md`).
- **`packages/contracts/` untouched.** Today's token claims and OpenAPI stay exactly as they are;
  the required delta is *documented* in `integration-token-decisions.md`, not applied.
- **Handover docs untouched.** `docs/Final_docs/handover/tag-administration.md` and
  `integration-onboarding.md` document today's proven behavior only; their Step-5-flagged
  sections update in the same substeps that land the behavior (§D.12 item 5).
- **Design page + action plan first.** Per §D.12 item 7, the new applicability/retrieval stages
  need design-page panels and action-plan substeps **before** any implementation starts — the
  design page remains the source of truth. Implementation substeps follow this deliverable; they
  are not part of it.
