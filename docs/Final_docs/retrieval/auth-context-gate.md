# Auth-context gate (`build_auth_context`)

- **Workflow:** retrieval (stage 1 — the door, before any search)
- **Owning code:** `backend/app/features/rag_agent/application/auth_context.py` (the gate),
  `backend/app/features/rag_agent/server/token_verifier.py` (the trust boundary that feeds it),
  `backend/app/features/rag_agent/server/router.py` (`_resolve_auth_context`, the HTTP mapping)
- **Design panel:** `r1-auth` (edge identity) · `mi-gate` (slot validation + launch allowlist /
  directed source-target validation) · `mi-contract` (the company + three-slots / directed
  connection claim shapes)
- **Status:** Implemented (substep 8.1.3 — the gate accepts slots). Amended by substep 9.3.1
  (Option A, ADR-0020 — the gate also accepts the directed source → target form), by Task 5
  (ADR-0022, a visibility gate), and by ADR-0023 (2026-10-20 — only the SOURCE decides: it must be
  in the catalog's `enabled_sources`, else a 403; the target is never checked). All tested at unit
  (Task 5, ADR-0023) / unit + database (8.1.3, 9.3.1)
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

Since ADR-0023 (owner, 2026-10-20) **only the source system decides**; a source can have hundreds
of targets, so the target is assumed supported and never checked.

1. **Source** — resolves through the SAME lenient catalog resolver chat-start uses
   (`ProductCatalog.resolve_system`: canonical id, per-product alias or display name,
   case/space-insensitive). Unresolved → `SourceNotEnabledError` (**403**, Obi hidden — not an
   error). A known source must be vendable by the issuing platform (`allowed_integrations`, else
   `IntegrationNotAllowedError`, **401**, the cross-issuer boundary) and then be in the catalog's
   `enabled_sources`, else `SourceNotEnabledError` (**403**). Precedence: vend 401 before
   enablement 403.
2. **Target** — resolved with the same resolver for routing only. Unknown (e.g. Base's "NetSuite")
   → `target_slug = None`, and `build_labels` falls back to the boxes the source alone can fill,
   `[obi-general, {source}-general]`. Known → the four routing labels as before. No vend,
   enablement, role or allowlist check applies to the target.
3. The slot **role check (3)** and the **launch allowlist (5)** LAPSE for the directed form
   (ADR-0020 D4/D5). `UnknownIntegrationError` no longer fires on this path.

#### The source-enablement visibility gate (ADR-0023, supersedes the Task 5 target gate)

`knowledge-base/config/product_catalog.json` carries an optional flat top-level
`enabled_sources` list of canonical product ids (loader rule 6b in
`backend/app/platform/config/product_catalog.py` — every id must be a real product; stored as
`ProductCatalog.enabled_sources: frozenset[str]`; renamed from `enabled_targets`). A directed
**source** is enabled iff it is in the set. **Absent ⇒ every product enabled.** The shipped value is
`["mews", "toast", "opera-cloud"]`.

`router._resolve_auth_context` maps `SourceNotEnabledError` to **HTTP 403** with a top-level body
`{"error": "integration not available", "reason": "source_not_enabled"}` — rendered top-level by
`render_source_not_enabled`, wired on the app in `main.create_app`, so it matches chat.yaml's
`Error` schema and the frontend proxy forwards a `reason` the widget reads. The body **never names
the product** (never-bend rule 10).

The read-only **`GET /chat/visibility`** (same host-key + `X-Obi-Token` auth as `POST /chat`, no
body) runs the same gate via `_visibility_payload` and returns `{"visible": true}`, or
`{"visible": false, "reason": "source_not_enabled"}` on the 403 — including for an unknown source,
so a partner's unsupported customer gets no widget instead of an error. A 401 hard failure
propagates as `POST /chat` would. The widget loader also hides at load time: `build:obi` injects
every normalized name of the enabled sources (`frontend/scripts/enabled-source-names.mjs`) and the
loader compares the token's normalized `source_system` against it.

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
  `test_rt1_directed_unknown_target_is_accepted_with_no_target_slug`,
  `test_rt1_directed_unknown_source_is_hidden_before_search`,
  `test_rt1_directed_source_resolves_by_display_name`,
  `test_rt1_directed_target_is_never_vend_checked`,
  `test_mi_gate_visibility_probe_hides_an_unknown_source`,
  `test_mi_gate_visibility_probe_reports_visible_for_any_target`,
  `test_rt1_directed_vend_rights_bind_the_source`,
  `test_rt1_directed_accounting_target_is_first_class` (now pins an all-enabled catalog so it
  isolates the allowlist-lapse claim from the Task 5 enablement axis), and
  `test_sec_body_can_never_carry_the_connection` (the body model forbids source/target). Task 5
  added `test_mi_gate_directed_refuses_disabled_source`,
  `test_mi_gate_directed_allows_every_enabled_source`,
  `test_mi_gate_directed_vend_violation_is_401_before_enablement` (precedence guards).
- `backend/app/platform/config/tests/test_product_catalog.py` (unit, panel `mi-gate`, Task 5):
  `test_enabled_sources_parses_the_listed_ids`,
  `test_enabled_sources_unknown_id_fails_and_names_it`,
  `test_enabled_sources_absent_means_all_products_enabled`,
  `test_enabled_sources_committed_value_is_mews_toast_opera_cloud`.
- `backend/app/features/rag_agent/tests/test_mi_gate_visibility.py` (unit, panels `mi-gate` /
  `mi-contract`, Task 5): `test_mi_gate_disabled_source_maps_to_403_with_reason_and_no_product_id`,
  `test_mi_gate_visibility_probe_reports_hidden_for_disabled_source`,
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
