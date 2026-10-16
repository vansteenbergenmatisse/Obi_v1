# Decision memo · token/API extension for the integration context (§D.1)

This is the decision memo §D.1 requires — the place where the §15 keuzes 1–4
(`docs/Final_docs/sync-rules/plan.md` §15) are decided. The decisions themselves were made by the
owner in decision round 1 and recorded in `docs/Final_docs/plan.md` §D.13 (2026-10-05); this memo
records them, their compatibility consequences, the exact delta they imply for
`packages/contracts/`, and what the backend gate must validate. Nothing in `packages/contracts/`,
`backend/` or `frontend/` is changed by this memo — every delta below is a TODO for the
implementation substeps that follow the design-page panels (§D.12 item 7).

## 1 · The §15 keuzes, and the decisions of record

The four open choices as §15 posed them (sync-rules/plan.md:1031-1034, verbatim, Dutch):

> 1. Lijst in de token-claim (`knowledge_scopes: [toast, operacloud]`) vs. één scope met
>    voorrangsregel.
> 2. Zoekgedrag bij een lijst: één gefuseerde zoekronde over de unie van scopes, of per scope en
>    fuseren.
> 3. Wat de citations/trace tonen als bronnen uit verschillende scopes komen.
> 4. Backwards-compat: blijft de enkelvoudige claim geldig (lijst van één) zodat bestaande
>    platforms niet breken.

Decided — §D.13 item 3, verbatim:

> - **Token:** company ID plus the three slots; each slot holds one system or stays empty.
> - **Allowlist at launch:** Toast as POS, Mews as PMS. A filled POS/PMS slot outside the
>   allowlist → **Obi stays hidden**.
> - **Empty-slot rule (owner-decided yes):** a Mews hotel with an empty POS slot **does** see
>   Obi — Mews is allowed and nothing in the token is outside the allowlist. Only an
>   out-of-allowlist *filled* slot hides Obi; empty slots never do.
> - **Search (§15 keuze 2):** **one filtered search.** Eligible docs are: general guides, guides
>   for each filled slot, and guides for pairs the company actually has (Toast→Mews, Mews→their
>   accounting system).
> - **Sources (§15 keuze 3):** each result shows **which slot let it in**.
> - **Old tokens (§15 keuze 4):** keep working, interpreted as a token with **one filled slot**.

Mapping back: keuze 1 → not a flat scope list but a **structured three-slot claim** (POS/PMS from
Data Hub, Accounting from Base — §D.13 items 1–2 add company-ID-only); keuze 2 → one filtered
search over general + filled slots + actual pairs; keuze 3 → per-slot source attribution; keuze
4 → the one-filled-slot compatibility path. §15's status block (sync-rules/plan.md:1037-1039,
1096-1104) already points here.

## 2 · Compatibility behavior (decided, §D.11 + §D.13)

- **A single-integration token stays valid**, interpreted as a list/slot-set of one: the legacy
  `integration` claim value fills the slot matching the product's catalog role (e.g. `"mews"` →
  PMS slot), the other two slots empty. No platform breaks on rollout.
- **Legacy alias values map via the catalog.** Alias resolution happens in the catalog
  (`knowledge-base/config/product_catalog.json`) before any validation: per-product `aliases`
  (e.g. `operacloud` → `opera-cloud`, evidence-based) plus the `legacy_aliases` compound
  mechanism — which is **empty by decision round 2** (§D.11's `toast-opera` example was proven
  to exist nowhere; O8 closed, see `catalog.md` §4). The mechanism stays; values are added only
  with named evidence.
- **Unknown values keep failing closed** with a **400 before any search** — the behavior that
  exists today for an unknown body scope
  (`backend/app/features/rag_agent/server/router.py:283`) and that §D.11 fixes for unknown
  token values too. X3 (plan.md §D.14) live-proved the fail-closed ordering on the deployed
  backend.
- **Content compatibility** (for completeness, §D.11): pages without an "Applies to" record keep
  today's label-only behavior — an explicit documented default, not a silent wildcard. That is
  §D.3's territory, not this memo's.

## 3 · The `packages/contracts/` delta (CLOSED — landed in substep 8.1.2, 2026-10-05)

Today's real shapes, file-referenced, and what the decided contract required of them. All six
rows closed by substep 8.1.2 with the names below (O5/O6 decided there):

| # | Today (real code) | Where | Required delta (decided by) | Status |
|---|---|---|---|---|
| T1 | `integration` — single string claim, "the ONLY business value that maps to knowledge scopes" | `packages/contracts/src/token-claims.json:16` | Add the structured context claim: company ID + three slots (pos/pms/accounting), each one canonical catalog id or empty. `integration` stays accepted as the legacy one-filled-slot form (§D.13 keuze 4). Names chosen (O5): top-level `company_id` + `context` object with required `slots` object carrying `pos`/`pms`/`accounting`, each `string` or `null` (null/omitted = empty) — contract §8's proposed shape adopted unchanged | ✅ closed (8.1.2) |
| T2 | `company_id` + `company_name` + `integration` are all-three-or-none (`dependentRequired`) | `token-claims.json:14-22` | New contract carries **company_id only — no company name** (§D.13 item 2): `dependentRequired` now reads `context → [company_id]`, and the all-three-or-none rule is scoped to the legacy form via an `if`/`then` that applies only when `context` is absent — legacy tokens still carrying `company_name` stay valid, never dropped | ✅ closed (8.1.2) |
| T3 | `ChatRequest.knowledgeScope` — optional body string, non-authoritative hint | `packages/contracts/src/index.ts:69`, `src/openapi/chat.yaml:197-204` | O6 decided: **keeps the single-string shape unchanged** — stays non-authoritative (never-bend rule 2) either way, and a slots-shaped body hint would add no capability since only the verified token decides; nothing to migrate, no behavior change | ✅ closed (8.1.2) |
| T4 | `Citation` — `id`/`pageId`/`title`/`url`/`version?`/`snippet?` | `index.ts:78-91`, `chat.yaml:206-227` | Field name chosen (O5): `Citation.attribution`, optional, enum `general \| pos \| pms \| accounting \| pair` (§D.13 keuze 3 verbatim), TS union `CitationAttribution` exported from `index.ts`. Absent until 8.3.4 assembles it | ✅ closed (8.1.2) |
| T5 | OpenAPI 400 description covers body-shape errors only | `chat.yaml:41-46` | `chat.yaml` now documents the unknown-slot/alias **400 before any search** in the /chat 400 description and the **out-of-allowlist filled POS/PMS refusal** in the /chat description — documented as the contract; gate enforcement lands in 8.1.3 | ✅ closed (8.1.2) |
| T6 | `iframe-messages.ts` token hand-off types | `packages/contracts/src/iframe-messages.ts` | Confirmed no-op: the note rides `obi:token` as an opaque signed JWT string, so the payload growing with T1 changes no message type. Platform-side note changes ride the Jasper handoff (§D.12 item 9) | ✅ closed (8.1.2, no change needed) |

The drift test keeping `token-claims.json` in lockstep with the backend verifier was extended in
8.1.2 (`backend/app/features/rag_agent/tests/test_token_claims_contract.py` — the legacy rule now
asserted under the context-absent conditional) and joined by seven contract tests
(`test_mi_contract_slots.py`) that pin both token forms, the slot names and the attribution
vocabulary against the backend catalog's `VALID_PRODUCT_ROLES` (substep 8.1.1).

## 4 · What the backend gate must validate (CLOSED — enforced by substep 8.1.3, 2026-10-05)

> Status: the five checks below are implemented in `build_auth_context`
> (`backend/app/features/rag_agent/application/auth_context.py`), in this order, with the
> stated statuses (unknown/invalid values → 400 before any search; vend/allowlist failures →
> the bare 401); the verifier extracts `context.slots` and scopes the legacy trio rule to
> context-less tokens. Proven by `test_mi_gate_slots.py` (one red-first test per check),
> `test_token_verifier.py` (context extraction/structure) and `test_router_auth_context.py`
> (endpoint statuses). The text below stays as the spec of record.

Today's gate chain — `VerifiedClaims` (issuer, subject, company_id, company_name, integration;
`backend/app/features/rag_agent/server/token_verifier.py:50-55`) → `build_auth_context`
(`backend/app/features/rag_agent/application/auth_context.py:104-138`) with the active-platform
gate (AUTH-1/CIP-A2) and the per-platform `allowed_integrations` vend check (CIP-A1, backed by
`knowledge-base/config/platforms.json`) — extends to the slot contract. The gate must validate,
in the same fail-closed style:

1. **Shape** — each slot value a short lowercase slug or empty; company_id present when slots
   are (mirrors today's slug validator, `router.py:209-216`).
2. **Membership** — every filled slot value resolves (directly or via a catalog alias) to a
   canonical product in `product_catalog.json`; the product's catalog role matches the slot it
   sits in (toast never valid in the PMS slot). Unknown → fail closed, 400 before any search
   (§D.11).
3. **Vend rights** — the issuing platform may only assert the slots it is trusted to fill
   (today's CIP-A1 generalized: Data Hub vends POS/PMS, Base vends Accounting), per the platform
   registry. Base's registry entry does not exist yet — §5-O7.
4. **Allowlist** — a filled POS/PMS slot outside the launch allowlist (Toast=POS, Mews=PMS) →
   the session is not served (and the frontend hides Obi); an empty slot never triggers this
   (§D.13 item 3). **The allowlist gates POS/PMS only (O4 closed, decision round 2,
   2026-10-05, owner-delegated):** a filled Accounting slot never hides Obi or refuses the
   session — a recognized-but-unsupported accounting product is simply **inert for
   eligibility** (no accounting-slot guides, no accounting pairs; general + the supported
   slots still serve, and accounting-specific questions get a cited refusal per never-bend
   rule 7). Unknown accounting values still fail closed at membership (gate rule 2).
5. **Body never authoritative** — body hints get shape + membership checks only; a known body
   value that disagrees with the token is ignored and logged, exactly today's
   `_validate_body_knowledge_scope` behavior (`router.py:271-283`). One authorization context
   per request drives every read (never-bend rules 2–3).

## 4b · The "Applies to" authoring approach (DECIDED — substep 8.2.1, 2026-10-05, default built per CLAUDE.md)

§D.3 required choosing ONE authoring approach. **Chosen: the standard applicability table in
the page body (storage format), not content properties.** Evidence (full reasoning in
`applies-to-authoring.md` §1): (1) the Confluence client already fetches every body in storage
format (`confluence_client.py:205`) — content properties would need a new v2 API surface and
client code; (2) a body-table edit bumps the page version and rides the existing webhook/sweep
change-detection path, while a content-property edit does NOT bump the version and would go
silently stale; (3) the controlled editing form content properties presuppose does not exist,
while the table uses the editor authors already use for labels. The validated schema landed in
`backend/app/features/ingestion/domain/applicability.py` (five levels + variants, explicit any,
loud named failures, label-only default for absent records); table→record parsing and chunk
stamping are substep 8.2.2. **O2 partial:** 8.2.1 fixed the workflow *binding vocabulary*
(`same-instance`, `same-property`, bound to the shared concrete product); runtime
property/instance context records stay open in O1/O2.

## 5 · Open items — honestly not decided

| Id | Open item | Decided by |
|---|---|---|
| O1 | **Connection records beyond the three slots** — actual connections with type, enabled directions, `selected_connection`; required before a direct POS→Accounting pair can ever be eligible (§D.2's Toast→QuickBooks clause; contract §5.2) | §D.4 (deterministic real-connection matching), context shape per §D.1's illustrative record |
| O2 | **Property/instance bindings** — `property_id`, `instance`, same-Mews-instance-same-property workflow rules, multiple instances per company | §D.3 level 5 + §D.4 |
| O3 | **Known/absent/unknown three-way marker** — the launch slot has two states (filled/empty); whether the richer record distinguishes "absent" from "not reported" on the wire | §D.3/§D.4 (with §D.1's `unknown_roles` field as the candidate shape) |
| O4 | ✅ **CLOSED (decision round 2, 2026-10-05, owner-delegated):** the allowlist gates **POS/PMS only**. A filled accounting slot outside support never hides Obi — it is inert for eligibility (no accounting guides/pairs; general + supported slots still serve; accounting-specific questions refuse with a reason). Rationale: the customer's primary supported integration decides visibility; punishing a Mews hotel for an unsupported accounting package serves nobody. Unknown values still 400 at membership. Full wording in §4 rule 4 | closed |
| O5 | ✅ **CLOSED (substep 8.1.2, 2026-10-05):** contract §8's proposed shape adopted unchanged — top-level `company_id` + `context.slots.{pos,pms,accounting}` (each one canonical catalog id or `null`; `context` requires `company_id`; the legacy all-three-or-none rule scoped to context-less tokens), and `Citation.attribution` with enum `general/pos/pms/accounting/pair` (TS: `CitationAttribution`). Why: the proposal matched §D.13's decided content exactly, the slot names reuse the catalog loader's one role vocabulary (`VALID_PRODUCT_ROLES`, no second spelling to drift), and the attribution values are §D.13 keuze 3 verbatim. Details in §3 | closed |
| O6 | ✅ **CLOSED (substep 8.1.2, 2026-10-05):** `knowledgeScope` **keeps the single-string shape unchanged**. Why: it is non-authoritative either way (never-bend rule 2 — only the verified token decides), so a slots-shaped body hint adds no capability while forcing a migration; the conservative no-behavior-change default wins | closed |
| O7 | **Base + Data Hub platform-registry entries** — `platforms.json` has datahub with TODO issuer/JWKS placeholders (`knowledge-base/config/platforms.json:5`) and **no Base entry at all**; issuers, JWKS URLs and vend sets are owner/platform-supplied facts (never-bend rule 12 — never invented). ~~**Owner ordered (decision round 2, 2026-10-05): deliberately LAST**~~ → **AMENDED (decision round 4, 2026-10-13, `plan.md` §D.18 item 1): integration prep runs NOW, in parallel with Phase A** — contact both partners, collect the five facts, stand the wiring up to activation; the ordering guard that remains is "no registration goes `active:true` until its issuer/JWKS/token endpoint verify." **Status: partial facts in from both, 0/5 confirmed each; neither activatable** — per-field status + ready-to-paste entries in `partner-facts.md`. | owner + platform teams; in progress — **tracked in `partner-facts.md`** |
| O8 | ✅ **CLOSED (decision round 2, 2026-10-05):** `toast-opera` **does not exist** — whole-repo search finds it in no config, code, token, or tag; it was plan.md's own illustrative example ("e.g. legacy values like `toast-opera`") carried from §D.1 into §D.11, a placeholder describing the alias mechanism, never an observed datum. Removed from the catalog; `legacy_aliases` is `{}` (mechanism kept, values only with named evidence). Full reasoning in `catalog.md` §4 | closed |
| O9 | **Accounting products ↔ knowledge scopes** — no Confluence scope tag exists today for QuickBooks Online or Xero (`knowledge_scopes.json` has mews/operacloud/toast only); how accounting-product guides are tagged and scoped | §D.3 (applicability metadata) + the tag-map substep that adds the scopes |
| O10 | **Standalone preset definitions** — §D.8 requires backend-validated presets covering the four flow types + the three-system workflow; their concrete contents | the §D.8 substep |

Each O-item is tracked here until a §D substep closes it; closing one updates this memo (same
change), per the component-doc rule in the root `CLAUDE.md`.

## 6 · Routing/visibility clarification (2026-10-13 — serves §D directed-routing R2/R5)

Captured for the sync-rules active work block (Task 4, `docs/Final_docs/sync-rules/plan.md`
lines 119–123). Serves the directed-routing requirements **R2** (the target decides whether the
widget appears) and **R5** (the backend validates the real customer connection and target
enablement) in `sync-rules/plan.md` §D (R-items at lines 2052–2104), and resolves the open §D
intent "QuickBooks target ⇒ widget hidden" (§D.2's Toast→QuickBooks clause; §D.18 item 4 — "no
target-enablement eligibility gate today, widget hiding is frontend UX over the backend 401").
Append-only; nothing above is changed.

**Confirmed label model (verified against code, `sync-rules/plan.md` lines 49–69).**
`product_catalog.build_labels(source, target)`
(`backend/app/platform/config/product_catalog.py:137-157`) yields **exactly four labels**:
`[obi-general, {source}-general, {target}-general, {source}-to-{target.role}]`. The connection
label is **source-product → target-*role*** (e.g. `toast-to-pms`), **not** source→target-product;
the target product's own software docs ride the separate product-level `{target}-general` label.

- `toast → mews` → `[obi-general, toast-general, mews-general, toast-to-pms]`
- `toast → opera-cloud` → `[obi-general, toast-general, opera-cloud-general, toast-to-pms]` —
  reuses the **same** `toast-to-pms` connection pages as toast→mews.
- `mews → quickbooks-online` →
  `[obi-general, mews-general, quickbooks-online-general, mews-to-accounting]`.

**Content-coverage consequence.** The content long-pole is **small for a same-role target**: a new
PMS target such as opera-cloud reuses the existing `toast-to-pms` connection pages, so the only new
content needed is its own `opera-cloud-general` software docs. It is **real only for a brand-new
target role**: an accounting target (e.g. `mews → quickbooks-online`) needs **both** new
`{target}-general` docs **and** new `{source}-to-accounting` connection pages, and **no
`*-to-accounting` pages exist today**. This bears on O9 (accounting products ↔ scopes) above but
does not close it.

**Target-enablement hide is being built (Task 5 / ADR-0022).** The resolution of the open §D intent
is under construction as Task 5 of this work block: a **configurable, backend-enforced
target-enablement gate on the directed path** with a matching frontend eligibility signal, so a
token whose target is not enabled (e.g. QuickBooks at launch) yields **no widget** rather than
today's bare 401 on an already-mounted launcher. Config is a product-global `enabled_targets` list
in `knowledge-base/config/product_catalog.json` (absent ⇒ all enabled, reversible); the backend
adds a `TargetNotEnabledError` → **403** after the vend-rights check, plus a read-only
`GET /chat/visibility` probe; the frontend hides at load time. Retrieval routing (the four-label
hard-filter, ADR-0020 D5) is **unchanged** — this gate controls widget *eligibility* only. It is
ratified in **ADR-0022 "Target-Enablement Widget Eligibility in the Directed Path"** (amends
ADR-0020 D4/D5). Per-platform enablement (R3/R4) is kept as the documented extension beyond the
product-global default.

## 7 · Sync note — ADR-0022 ratified and shipped (2026-10-13, Task 5e)

Append-only; nothing above is changed. Task 5 (backend + frontend) is built and green and
**ADR-0022 is now Accepted** (`docs/adr/0022-Target-Enablement-Widget-Eligibility-In-The-Directed-Path.md`),
so §6's "being built" is now **done**. As shipped: optional flat `enabled_targets`
(`["mews","toast","opera-cloud"]`) in `product_catalog.json` (loader rule 6b; absent ⇒ all
enabled; reversible, no migration); `TargetNotEnabledError` after vend rights → **403** with body
`{"error":"integration not available","reason":"target_not_enabled"}` (product id never leaked —
rule 10); new optional `Error.reason` in `chat.yaml`; read-only `GET /chat/visibility`; frontend
loader init fetch + the 4th `obi:hidden` frame→host message (both bent conventions authorized by
ADR-0022). Retrieval routing (ADR-0020 D5 four-label hard filter) is **unchanged** — the gate is
widget-eligibility only, so rule 11's gold-set before/after does not apply. `context-contract.md`
§4/§8.4 and `catalog.md` are synced, and `phase-a-validation-cases.md` Case 18 is flipped from
decision-dependent to a live pass/fail gate (disabled target ⇒ widget hidden + 403). The §D.18
item-4 intent is now resolved in code and of record.
