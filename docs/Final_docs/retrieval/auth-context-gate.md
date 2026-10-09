# Auth-context gate (`build_auth_context`)

- **Workflow:** retrieval (stage 1 — the door, before any search)
- **Owning code:** `backend/app/features/rag_agent/application/auth_context.py` (the gate),
  `backend/app/features/rag_agent/server/token_verifier.py` (the trust boundary that feeds it),
  `backend/app/features/rag_agent/server/router.py` (`_resolve_auth_context`, the HTTP mapping)
- **Design panel:** `r1-auth` (edge identity) · `mi-gate` (slot validation + launch allowlist) ·
  `mi-contract` (the company + three-slots claim shape)
- **Status:** Implemented (substep 8.1.3 — the gate accepts slots; tested at unit + database
  levels, not yet proven against a live platform-signed slot token)

## What it does

`build_auth_context` turns a verified platform-signed JWT (`VerifiedClaims`) into the single
frozen `AuthContext` that drives every reader transaction on the answer path — its
`allowed_scopes` set the scope GUC for search, rerank text, curated lookup and parent expansion
(never-bend rule 3: one authorization context per request, built at the gate). Since 8.1.3 the
context also carries the validated integration slots (`slot_pos`/`slot_pms`/`slot_accounting`,
canonical catalog ids, `None` for empty), ready for the 8.3.x eligibility/attribution work.

The verifier extracts both token forms: the structured `context.slots` claim (structural
garbage → bare `TokenError`, 401; the legacy all-three-or-none business rule is scoped to
context-less tokens, matching the schema's conditional) and the legacy single `integration`
claim, which the gate reads as exactly one filled slot (the product's catalog role picks the
slot; aliases resolve through the catalog, §D.11).

After the active-platform gate (AUTH-1/CIP-A2, unchanged), the five slot checks of
`docs/Final_docs/5-integration-context/decision-memo.md` §4 run in order over the filled slots:

1. **Shape** — every filled value a short lowercase slug; `company_id` present when a slot is
   filled → `InvalidSlotValueError`, mapped to **400 before any search**.
2. **Membership** — every filled value resolves (canonical id or catalog alias) to a product in
   `knowledge-base/config/product_catalog.json` → `UnknownIntegrationError` (a subclass of the
   400 family). This replaced the old registry-map lookup and its bare 401.
3. **Role agreement** — the product's catalog role matches its slot (toast is never a PMS) →
   `InvalidSlotValueError` (400).
4. **Vend rights** — the issuing platform may only fill slots with products its
   `allowed_integrations` resolve to (CIP-A1 generalized: Data Hub vends POS/PMS, Base — once
   registered, O7 — vends Accounting) → `IntegrationNotAllowedError` (401).
5. **Allowlist** — a FILLED POS/PMS slot must be on the launch allowlist (Toast as POS, Mews as
   PMS) → `SlotNotOnAllowlistError` (bare 401). The Accounting slot is never gated here (owner
   decision O4: inert for eligibility); an empty slot never refuses.

Scopes are the union of the filled slots' registry scopes plus general; a filled slot with no
scope mapping yet (accounting products, O9 open) contributes none and never errors. The body
`knowledge_scope` stays non-authoritative: an unknown body value is a 400 before any search; a
recognized value disagreeing with the token is logged (`body_knowledge_scope_ignored`) and
ignored. All 401 failure modes stay byte-identical on the wire.

## Why it does it

The request body never decides access (never-bend rule 2); scope comes only from the verified
note (ADR-0014, PLAN 11.1c). Verification is deliberately trust-free — the verifier proves *who
signed*, the gate decides *what that signer may assert*. The five checks fail closed in order so
an unknown or misplaced product dies as a 400 before any search (§D.11 / the 8.1.2 chat.yaml
contract), a cross-tenant or un-vended slot dies as the same bare 401 as every trust failure,
and an unsupported-but-real POS/PMS product refuses the session exactly as the frontend hides
Obi — the backend is the boundary, the hiding is UX (`context-contract.md` §4). Empty slots
never refuse ("empty slots never hide Obi") and a legacy note keeps working forever as one
filled slot (§D.13 keuze 4).

## How we know it works

- `backend/app/features/rag_agent/tests/test_mi_gate_slots.py` (unit, panel `mi-gate`): one
  red-first test per check — `test_rt1_slot_shape_rejects_a_malformed_value`,
  `test_rt1_filled_slots_without_company_id_are_invalid`,
  `test_rt1_unknown_slot_value_fails_closed`,
  `test_rt1_role_mismatch_toast_in_pms_slot_is_refused`,
  `test_rt1_vend_rights_bind_slots_to_the_issuing_platform`,
  `test_rt1_pms_opera_cloud_outside_allowlist_is_refused` — plus
  `test_rt1_empty_pos_with_mews_pms_serves`,
  `test_rt1_accounting_outside_support_is_inert_never_refuses`,
  `test_rt1_all_empty_slots_are_general_only`,
  `test_rt1_legacy_note_reads_as_one_filled_slot`,
  `test_rt1_legacy_alias_resolves_via_the_catalog_then_hits_the_allowlist`. Each check's
  break-it ran red with its one change undone, green restored.
- `backend/app/features/rag_agent/tests/test_token_verifier.py` (unit, panel `mi-contract`):
  `test_rt1_verifier_extracts_context_slots`,
  `test_rt1_context_token_is_company_id_only_no_trio_rule`,
  `test_rt1_malformed_context_is_rejected`, beside the unchanged alg/JWKS/lifetime/trio suite.
- `backend/app/features/confluence_sync/tests/test_router_auth_context.py` (database, panel
  `mi-gate`): `test_rt1_pms_opera_cloud_slot_is_refused_at_chat`,
  `test_rt1_empty_pos_with_mews_pms_serves_at_chat`,
  `test_rt1_unknown_slot_value_is_400_before_search`,
  `test_rt1_accounting_slot_outside_support_serves_at_chat`,
  `test_rt1_legacy_note_serves_identically_to_one_filled_slot`,
  `test_rt1_body_hint_never_overrides_the_note_slots`; the pre-existing `r1-auth` suite stays
  green with two disclosed premise rewrites (`test_unknown_integration_is_400_before_search`,
  the G9 byte-identical-401 set swapping the unknown-value mode for the allowlist refusal —
  both forced by the 8.1.2 contract, not a weakening).
- `backend/app/features/rag_agent/tests/test_auth_context.py` (unit, panel `r1-auth`): all 15
  pre-8.1.3 tests green **unmodified** — the legacy token path is byte-compatible.

Gap (honest): no live proof yet against a real platform-signed slot token (no platform mints
the structured form today — O7 keeps Base/Data Hub registry entries for Step 5's tail), and
the slots do not yet filter retrieval — eligibility lands in 8.3.1, attribution in 8.3.4.
