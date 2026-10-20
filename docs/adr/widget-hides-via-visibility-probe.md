# Target-Enablement Widget Eligibility in the Directed Path

Identifier: `ADR-widget-hides-via-visibility-probe` (formerly numbered 0022). File paths updated to the current layout (`backend/`, `frontend/`, `knowledge-base/`) on 2026-10-20; the decision is unchanged.

Status: Accepted — the target-vs-source choice is superseded by `ADR-source-system-decides-widget-eligibility`
(2026-10-20). Read every `enabled_targets` / `TargetNotEnabledError` / `target_not_enabled` below as
`enabled_sources` / `SourceNotEnabledError` / `source_not_enabled`, gating the SOURCE. The mechanism
(visibility probe, 403 render, `obi:hidden`, init-time eligibility fetch) is unchanged.
Date: 2026-10-13
Governs: `knowledge-base/config/product_catalog.json` (`enabled_targets`),
`backend/app/platform/config/product_catalog.py` (loader rule 6b, the `enabled_targets` frozenset),
`backend/app/features/rag_agent/application/auth_context.py` (`TargetNotEnabledError`,
`_build_directed_context`), `backend/app/features/rag_agent/server/router.py`
(`GET /chat/visibility`, the 403 render), `backend/app/features/rag_agent/__init__.py` +
`server/__init__.py` (the app-level exception handler), `packages/contracts/src/openapi/chat.yaml`
(`Error.reason`), `packages/contracts/src/iframe-messages.ts` (`obi:hidden`),
`frontend/src/features/embed/loader.ts` (the init-time eligibility fetch + `__OBI_ENABLED_TARGETS__`),
`frontend/src/app/embed/embed-frame.tsx` (the `GET /chat/visibility` probe + the Next proxy).
Amends ADR-directed-source-target-routing-labels D4/D5 (the launch-allowlist lapse in the directed path). Does NOT touch the retrieval
routing axis (ADR-directed-source-target-routing-labels D1/D5 four-label hard filter), source/company isolation (ADR-source-id-row-security-with-reader-writer-roles / ADR-db-level-customer-scope-isolation-backstop), the
edge-token verification (ADR-signed-token-verified-at-the-edge), or the knowledge-scope retirement (ADR-routing-labels-sole-content-axis).

## Context

ADR-directed-source-target-routing-labels adopted directed-connection routing and, in D4/D5, made launch behavior **content-gated**:
direction is primary, accounting is a first-class target, and a chat is served when its four label
boxes have pages and refused with a reason when they are empty. In doing so the directed path
deliberately dropped the slot form's launch **allowlist** (`context-contract.md` §4: a filled
off-allowlist POS/PMS slot hides Obi). The consequence — recorded as the directed-path "allowlist
lapse" (`auth_context.py:202-205`; `decision-memo.md` §6; `sync-rules/plan.md` §D.18 item 4) — was
that a directed token for any catalog-valid target (e.g. `mews → quickbooks-online` at launch, when
no `*-to-accounting` pages exist) was accepted if it verified and vended, and the customer saw an
already-mounted widget that could only refuse for lack of content. There was **no widget-eligibility
gate** on the directed path: hiding was frontend UX layered over a bare backend 401, not a decided,
backend-enforced rule.

The owner wants the §D.2 Toast→QuickBooks intent honored as a visible behavior: a token whose target
is not yet live yields **no widget**, the way a filled off-allowlist slot hides Obi in the slot form —
without reintroducing the allowlist as a retrieval filter and without a Confluence/DB change.

## Decision

1. **Partially reverse the ADR-directed-source-target-routing-labels D4/D5 lapse — for WIDGET ELIGIBILITY ONLY.** A new global
   target-enablement axis decides whether the widget is eligible to mount for a directed connection.
   The retrieval routing axis is **unchanged**: the four-label hard filter (ADR-directed-source-target-routing-labels D1/D5), direction
   primacy (D4), and accounting as a first-class target (D5) all stand exactly as ratified. This gate
   adds no label, removes no label, and changes no search. Because retrieval behavior does not change,
   never-bend rule 11's before/after gold-set number does **not** trigger for this change.

2. **`enabled_targets` config (absent ⇒ all enabled, reversible).** `product_catalog.json` gains an
   optional flat `enabled_targets` array (shipped value `["mews", "toast", "opera-cloud"]`). Loader
   rule 6b validates each entry is an existing catalog canonical id and stores a frozenset; when the
   key is **absent the feature is inert — all products are enabled** (backward-compatible). It is a
   data edit, not code, and needs **no migration**.

3. **Backend 403 is the authority; frontend hide is UX.** In `_build_directed_context`, after shape +
   membership (unresolved source OR target → 400 before any search) and after vend rights (un-vended →
   401), the **target** product must be in `enabled_targets`, else `TargetNotEnabledError`. Precedence
   is therefore: unknown target → **400**, un-vended → **401**, not-enabled → **403**. Only the target
   gates; the source's enablement is ignored. The router maps `TargetNotEnabledError` to HTTP **403**
   via an app-level exception handler, with the top-level body
   `{"error":"integration not available","reason":"target_not_enabled"}` — rendered so it matches
   `chat.yaml`'s `Error` schema, and **the product id is never leaked** (never-bend rule 10). A new
   optional `Error.reason` is added to `chat.yaml`. A read-only `GET /chat/visibility` (same
   `X-Obi-Token` auth) runs the SAME gate and returns `200 {"visible":true}` or
   `200 {"visible":false,"reason":"target_not_enabled"}`; 400/401 and other hard failures propagate
   and are **not** masked as `visible:false`. The frontend hiding is the UX surface of this backend
   decision, never the boundary (never-bend rules 2–3).

4. **Authorized bent convention #1 — an init-time, eligibility-only token fetch.** `build:obi` bakes
   `enabled_targets` into `__OBI_ENABLED_TARGETS__` (esbuild `--define`, like `__OBI_ORIGIN__`). The
   loader `init()` fetches the token once and decodes a **display-only** `target_system` to hide
   before mount when the target is not enabled, failing **open** on any uncertainty. This is a second
   token fetch in addition to the trust-bearing click fetch; the click fetch stays fresh and remains
   the authority. ADR-widget-hides-via-visibility-probe authorizes the extra init fetch as an eligibility-only, non-authoritative
   read.

5. **Authorized bent convention #2 — a 4th `ObiMessage` type `obi:hidden`.** `embed-frame.tsx` calls
   `GET /chat/visibility` through a new same-origin Next proxy that injects the host key; a
   `visible:false` answer posts a NEW frame→host message `obi:hidden`, on which the loader `destroy()`s
   the widget. `obi:hidden` is the **sole** frame→host message and is accepted only from Obi's own
   iframe at the exact Obi origin. ADR-widget-hides-via-visibility-probe authorizes this 4th message type and its one-way direction.

## Consequences

- **Amends ADR-directed-source-target-routing-labels D4/D5.** The directed path regains a widget-eligibility gate, but as a separate
  global enablement axis, not as the slot allowlist and not as a retrieval filter. ADR-directed-source-target-routing-labels's routing
  decisions are untouched.
- **Honesty surface.** A not-yet-live target (e.g. QuickBooks at launch) now yields no widget and a
  clean 403 (`reason: target_not_enabled`), instead of an already-mounted launcher that can only
  refuse. `context-contract.md` §4/§8.4, `decision-memo.md` §6, `catalog.md`, and
  `phase-a-validation-cases.md` Case 18 are synced; Case 18 flips from decision-dependent to a live
  pass/fail gate.
- **Reversible, no migration.** Removing or emptying `enabled_targets` makes the feature inert and
  restores today's content-gated behavior with no code revert and no schema change (rule 11; plan 5f).
- **Per-platform enablement (plan R3/R4) is deferred.** This ADR ratifies the product-global default
  only; a per-platform `enabled_targets` override is the documented extension beyond it.
- **Invariants that MUST hold (unchanged):** never-bend rule 2–3 (the token decides, one auth context
  at the gate, no read looser than the search), rule 10 (no secret/product id leaked in a body), rule
  11 (no change without its test; no retrieval change — so no gold-set number owed here), and the
  edge-JWT verification (ADR-signed-token-verified-at-the-edge).
