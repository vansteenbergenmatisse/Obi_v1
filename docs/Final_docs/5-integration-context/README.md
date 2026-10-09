# 5 · Integration context (roadmap Step 5, §D.1) — index

The single home for the §D.1 "Complete integration context" **design + data deliverable**
(`docs/Final_docs/plan.md` §D.1, built strictly on the owner decisions of record in §D.13).
Same rule as `4-test-foundation/`: anything about the shared integration-context contract goes
here; look here first. This folder is design documentation plus one data file
(`knowledge-base/config/product_catalog.json`) — it changes **no running behavior** (see the
last section).

- `context-contract.md` — THE shared context contract for all environments (Base, Data Hub,
  standalone): the three-slot token (POS/PMS from Data Hub, Accounting from Base), company-ID-only
  identity, token-over-body trust (never-bend rules 2–3), known/absent/unknown configuration, the
  launch allowlist (Toast=POS, Mews=PMS) with the exact visibility rule, eligibility derivation
  (general + filled slots + the pairs the company actually has), how the §D.2 flow types map onto
  slot pairs — including why Toast+Mews+QuickBooks does **not** imply a direct Toast→QuickBooks
  pair — and four concrete token examples.
- `decision-memo.md` — the token/API extension decision memo §D.1 requires. Records the §15
  keuzes 1–4 verbatim as decided in §D.13 item 3, the compatibility behavior for old
  single-integration tokens and legacy alias values, the exact delta this implies for
  `packages/contracts/` (token claims + OpenAPI, as a TODO-for-implementation table with today's
  real field names, file-referenced), what the backend gate must validate, and the honest list of
  items the owner has **not** decided yet (each with a pointer to the §D part that will decide it).
- `catalog.md` — documentation of the new central product catalog
  (`knowledge-base/config/product_catalog.json`): every field, the validation rules a future
  loader must enforce, how to add a product, how aliases (including the legacy `toast-opera`
  value) resolve, and the rule that **nothing else in the repo may define a product**.
- `research-rerank-api.md` — read-only findings on the reranker as actually wired (Cohere
  `rerank-v3.5` via v2, string-documents only, **no instruction field exists**), the
  eligibility-before-rerank invariant, and the ranked options for the §D.6 build (enrich the
  query string + YAML metadata in document strings; `rank_fields` is v1-only escalation).
- `research-jasper-handoff.md` — the §D.9 Jasper-handoff verification: **no deployed `obi.js`
  URL exists** (frontend not deployed; `obi.omniboost.com/obi.js` → 404 parking host), the
  embed contract and JWT/JWKS requirements per side, the four-case test matrix
  (works-today vs future), and the draft reply skeleton the owner edits before sending.

## What this does NOT change yet

This deliverable is design + data only. Explicitly out of scope in this pass:

- **No backend behavior changes.** No loader, no validator, no gate change, no migration, no
  retrieval change is wired. The catalog JSON sits unread by any code until its implementation
  substep lands (the loader is an implementation TODO recorded in `catalog.md`).
- **`packages/contracts/` untouched.** Today's token claims and OpenAPI stay exactly as they are;
  the required delta is *documented* in `decision-memo.md`, not applied.
- **Handover docs untouched.** `docs/Final_docs/handover/tag-administration.md` and
  `integration-onboarding.md` document today's proven behavior only; their Step-5-flagged
  sections update in the same substeps that land the behavior (§D.12 item 5).
- **Design page + action plan first.** Per §D.12 item 7, the new applicability/retrieval stages
  need design-page panels and action-plan substeps **before** any implementation starts — the
  design page remains the source of truth. Implementation substeps follow this deliverable; they
  are not part of it.
