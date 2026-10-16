# Auth-context gate (`build_auth_context`)

- **Workflow:** retrieval (stage 1 — the door, before any search)
- **Owning code:** `backend/app/features/rag_agent/application/auth_context.py` (the gate),
  `backend/app/features/rag_agent/server/token_verifier.py` (the trust boundary that feeds it),
  `backend/app/features/rag_agent/server/router.py` (`_resolve_auth_context`, the HTTP mapping)
- **Design panel:** `r1-auth` (edge identity) · `mi-gate` (slot validation + launch allowlist /
  directed source-target validation) · `mi-contract` (the company + three-slots / directed
  connection claim shapes)
- **Status:** Implemented (substep 8.1.3 — the gate accepts slots). Amended by substep 9.3.1
  (Option A, ADR-0020 — the gate also accepts the directed source → target form), and by Task 5
  (the target-enablement visibility gate — a directed target must be in the catalog's
  `enabled_targets`, else a 403). All tested at unit (Task 5) / unit + database (8.1.3, 9.3.1)
  levels, not yet proven against a live platform-signed token.

## What it does

`build_auth_context` turns a verified platform-signed JWT (`VerifiedClaims`) into the single
frozen `AuthContext` that drives every reader transaction on the answer path — its
`allowed_sources` set the source GUC for search, rerank text, curated lookup and parent expansion
(never-bend rule 3: one authorization context per request, built at the gate). Since 8.1.3 the
context also carries the validated integration slots (`slot_pos`/`slot_pms`/`slot_accounting`,
canonical catalog ids, `None` for empty), feeding the 8.3.x eligibility/attribution work; for a
directed chat it also carries the routing labels (the live content axis). The knowledge-scope axis
is retired (ADR-0021): `allowed_scopes` is empty everywhere and the scope GUC is opted out to the
wildcard, so it no longer filters any read.

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

The slot checks still run (they gate the session and feed eligibility), but the gate derives no
knowledge scopes: `allowed_scopes` is empty for every token (ADR-0021 — the scope axis is retired,
there is no base scope). The body `knowledge_scope` field is fully non-authoritative and inert: it
is logged (`body_knowledge_scope_ignored`) and ignored, never a 400 and never a filter (ADR-0021;
previously an unknown body value was a 400 before any search). All 401 failure modes stay
byte-identical on the wire.

### The directed connection form (substep 9.3.1, Option A, ADR-0020)

When the verified token carries the directed form — `source_system` + `target_system` +
`business_id` (`VerifiedClaims.source_system`/`target_system`/`business_id`, parsed by
`token_verifier._parse_directed`; a partner system missing its counterpart or a missing/empty
`business_id` is a malformed token → bare `TokenError`, 401; an integer `business_id` such as Base's
`2108` is accepted and normalized to the string `"2108"`, a boolean is not, since 2026-10-16
(`test_rt1_verifier_accepts_numeric_business_id`)) — `build_auth_context` takes a
separate branch (`_build_directed_context`) **before** the slot chain and routes on the directed
connection instead of the membership slots:

1. **Shape + membership (checks 1-2)** — source and target each resolve through the SAME lenient
   catalog resolver chat-start uses (`ProductCatalog.resolve_system`: canonical id, per-product
   alias or display name, case/space-insensitive), so the gate can never admit a connection
   chat-start would then fail to resolve. An unresolved source OR target → `UnknownIntegrationError`
   (the **400-before-any-search** family, §D.11), raised before any retrieval runs.
2. **Vend rights (check 4)** — the issuing platform may assert only systems its
   `allowed_integrations` resolve to; a source or target it may not vend → `IntegrationNotAllowedError`
   (401), the same cross-issuer boundary as the slot form.
3. The slot **role check (3)** and the **launch allowlist (5)** LAPSE for the directed form
   (ADR-0020 D4/D5: direction is primary — `toast → mews ≠ mews → toast`; accounting is a
   first-class target; launch is content-gated by the label boxes, not an allowlist).
4. **Target enablement (check 5t, Task 5)** — placed **after vend rights**, the resolved TARGET
   product must be in the catalog's `enabled_targets` set, else `TargetNotEnabledError`. Only the
   target gates (the source's enablement is ignored). Precedence is therefore: unknown target →
   **400** (membership), un-vended → **401** (vend), not-enabled → **403**. This is a separate,
   flat/global axis from the (lapsed) launch allowlist.

#### The target-enablement visibility gate (Task 5)

`knowledge-base/config/product_catalog.json` carries an optional flat top-level
`enabled_targets` list of canonical product ids (loader rule 6b in
`backend/app/platform/config/product_catalog.py` — every id must be a real product; stored as
`ProductCatalog.enabled_targets: frozenset[str]`). A directed **target** is enabled iff it is in
the set. **Absent ⇒ every product enabled** (backward compatible — the check never fires), so
removing or emptying the field makes the feature inert with no code change (reversibility). The
shipped value is `["mews", "toast", "opera-cloud"]`; the accounting products (xero,
quickbooks-online) are deliberately not listed, so a directed connection whose target is one of
them is refused until it goes live.

`router._resolve_auth_context` maps `TargetNotEnabledError` to **HTTP 403** with a top-level body
`{"error": "integration not available", "reason": "target_not_enabled"}` — a 403 (off the 401
renew path; distinct from the 400 fail-closed family), rendered top-level (not FastAPI's default
`{"detail": ...}`) by `render_target_not_enabled`, wired on the app in `main.create_app`, so it
matches chat.yaml's `Error` schema and the frontend proxy forwards a `reason` the widget reads.
The body **never names the product id** (never-bend rule 10).

A new read-only **`GET /chat/visibility`** (same host-key + `X-Obi-Token` auth as `POST /chat`,
no body) lets the frontend hide Obi *before* any chat round-trip: it runs the same gate via
`_visibility_payload` and returns `{"visible": true}`, or `{"visible": false, "reason":
"target_not_enabled"}` on the enablement 403. A 400/401 hard failure propagates exactly as
`POST /chat` would — the probe never masks a malformed/forbidden connection as merely hidden.

`business_id` (verified present for this form) becomes the `AuthContext.company_id`
company-isolation axis; the resolved `source_slug`/`target_slug` ride the context for chat-start
(9.2.1) to build the four routing labels + connection block. No knowledge scopes are derived here
(ADR-0021) — the label hard filter is the content axis, wired into retrieval at stage 9.4.1. The
body still never decides the connection (rules 2-3): `build_auth_context` takes no body, and
`ChatRequestBody` forbids a `source_system`/`target_system` key outright (`extra="forbid"`).

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
- `backend/app/features/rag_agent/tests/test_mi_gate_directed.py` (unit, panels `mi-gate` /
  `mi-contract`, substep 9.3.1): the directed branch — `test_rt1_directed_form_accepted`,
  `test_rt1_directed_unknown_source_is_400_before_search`,
  `test_rt1_directed_unknown_target_is_400_before_search`,
  `test_rt1_directed_vend_rights_bind_both_systems`,
  `test_rt1_directed_accounting_target_is_first_class` (now pins an all-enabled catalog so it
  isolates the allowlist-lapse claim from the Task 5 enablement axis), and
  `test_sec_body_can_never_carry_the_connection` (the body model forbids source/target). Task 5
  added `test_mi_gate_directed_refuses_disabled_target`,
  `test_mi_gate_directed_allows_enabled_target`,
  `test_mi_gate_directed_unknown_target_is_400_before_enablement`,
  `test_mi_gate_directed_vend_violation_is_401_before_enablement` (precedence guards).
- `backend/app/platform/config/tests/test_product_catalog.py` (unit, panel `mi-gate`, Task 5):
  `test_enabled_targets_parses_the_listed_ids`,
  `test_enabled_targets_unknown_id_fails_and_names_it`,
  `test_enabled_targets_absent_means_all_products_enabled`,
  `test_enabled_targets_committed_value_is_mews_toast_opera_cloud`.
- `backend/app/features/rag_agent/tests/test_mi_gate_visibility.py` (unit, panels `mi-gate` /
  `mi-contract`, Task 5): `test_mi_gate_disabled_target_maps_to_403_with_reason_and_no_product_id`,
  `test_mi_gate_visibility_probe_reports_hidden_for_disabled_target`,
  `test_mi_gate_visibility_probe_reports_visible_for_enabled_target`,
  `test_mi_gate_visibility_probe_propagates_400_unknown_target`,
  `test_mi_gate_403_body_is_rendered_top_level_not_wrapped_in_detail`.
- `backend/app/features/rag_agent/tests/test_token_verifier.py` (unit, panel `mi-contract`,
  substep 9.3.1): `test_rt1_verifier_extracts_directed_connection`,
  `test_rt1_malformed_directed_connection_rejected`.
- Contract drift (unit): `test_token_claims_contract.py::test_directed_connection_form_is_published_and_optional`
  and the updated `test_business_claims_are_all_three_or_none` (new `if` conditional);
  `test_mi_contract_slots.py` moved with the contract (the `if` shape, the directed fields, and
  the `connection` attribution value in the TS mirror + OpenAPI enum).

Gap (honest): no live proof yet against a real platform-signed token (slot or directed — no
platform mints either form today), and neither the slots nor the directed labels yet filter
retrieval — slot eligibility landed in 8.3.x; the directed label hard filter lands in 9.4.1, and
chat-start session population (9.2.1's `start_chat_session`) is not yet wired into the request
path (it is wired where the labels are consumed, in 9.4.1).
