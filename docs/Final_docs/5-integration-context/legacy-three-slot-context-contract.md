# The shared integration-context contract (launch shape)

> **LEGACY — superseded by the directed form.** The three-slot `context.slots` contract (and the
> single `integration` claim) is still **accepted** by the gate, but it **no longer routes** content.
> The current contract is the directed token (`source_system`, `target_system`, `business_id`;
> ADR-directed-source-target-routing-labels), and only the **source** decides whether Obi shows
> (ADR-source-system-decides-widget-eligibility: `enabled_sources` = `mews`, `toast`, `opera-cloud`;
> unknown or disabled source → 403 `source_not_enabled`; the target is never checked). This page
> stays because code still cites it. For how a partner integrates today, see
> [`how-partners-integrate-with-obi.md`](../1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md).

**Status: design of record for the Step-5 build.** Everything normative here traces to the owner
decisions in `docs/Final_docs/plan.md` §D.13 (2026-10-05), to §D.1/§D.2/§D.11, or to real code
cited by file and line. Where the owner has not decided, this document says so and points at the
§D part that will decide it — the full open list lives in `integration-token-decisions.md`.

One contract serves **all three environments**: Base, Data Hub, and the standalone/test
environment (§D.1, §D.8). The standalone environment uses the same contract with
backend-validated presets; simulated test context is clearly distinguished from real
configuration and switching presets starts a fresh chat (§D.8 — preset design is a later
substep, not this document).

## 1 · The contract: company ID + three slots

Per §D.13 items 1–3, the verified context is:

- **`company_id`** — the company identifier alone; **no company name** in the contract
  (§D.13 item 2). Opaque to Obi; never a scope axis by itself.
- **Three slots per company**, each holding **one canonical product id** from the central product
  catalog (`knowledge-base/config/product_catalog.json`) **or staying empty**:
  - **POS** — supplied by **Data Hub** from its backend configuration.
  - **PMS** — supplied by **Data Hub** from its backend configuration.
  - **Accounting** — supplied by **Base** from its backend configuration.

A hotel with no POS sends an empty POS slot (§D.13 item 1, verbatim example). A slot never holds
more than one system at launch.

Slot values are canonical ids resolved through the catalog; alias values (e.g. `operacloud` →
`opera-cloud`) resolve through the catalog's aliases before validation (§D.11; see
`product-catalog.md` — no legacy compound value exists; O8 closed in decision round 2).

**Claim field names: FIXED (substep 8.1.2, 2026-10-05).** The owner decided the *content* of
the token (company ID + three slots); the exact JSON claim names and nesting were fixed when
`packages/contracts/` was extended (O5 closed — `integration-token-decisions.md` §3): the §8 shape below is
now the shape of record in `packages/contracts/src/token-claims.json`, verbatim.

## 2 · Trust model: the token decides, the body never does

Never-bend rules 2–3 (root `CLAUDE.md`) bind this contract unchanged:

- The three slots and the company ID come **only from the verified token** a platform's server
  signs (the note). Base and Data Hub supply verified context from their backend configuration
  (§D.1); nothing the widget or the page JavaScript asserts can add or change a slot.
- The request body never decides access. Today's enforcement is the model: the body
  `knowledge_scope` is shape-validated (short lowercase slug,
  `backend/app/features/rag_agent/server/router.py:209-216`) and membership-checked — an unknown
  value is a **400 before any search**
  (`router.py:271-283`), and a known value that disagrees with the token is **ignored and
  logged**. The extended contract keeps exactly this: body hints get shape + membership checks
  only; the authorization context is built once at the gate from the token.
- One authorization context per request (never-bend rule 3). Every database read — search,
  rerank text, curated lookup, parent expansion — runs under the context built from the token's
  slots. Frontend selections and prompt instructions never expand permissions (§D.1).

Applicability/eligibility is a **relevance restriction on top of** the existing access controls
(labels → membership + sharing; RLS + page restrictions → access), never a widening (§D
invariants). Untagged or `classified` content never becomes reachable through this contract.

## 3 · Known, absent, unknown

§D.1 requires distinguishing **known products**, **absent products**, and **unknown
configuration** explicitly, and never inferring a target product or a connection from a flat
list of installed software.

In the decided launch token a slot has **two** states:

- **Filled** — the host platform's backend knows the system in that role: a *known product*.
- **Empty** — no system is asserted for that role. The §D.13 example reads this as *absent*
  ("a hotel with no POS sends an empty POS slot"); a host that simply cannot report a role
  produces the same empty slot.

Both empty cases behave identically and safely: an empty slot contributes **no** slot guides and
**no** pairs to eligibility — the company gets general guidance plus whatever its other filled
slots justify, never more. When connection-specific guidance would need the missing
configuration, the pipeline serves applicable general guidance and asks for the missing
configuration instead of broadening (§D.4). A three-way wire-level marker (absent vs
explicitly-unknown) is **not** part of the decided launch token; if §D.3/§D.4's richer context
record needs one, it is decided there (open item — `integration-token-decisions.md` §5).

## 4 · The launch allowlist and the visibility rule

§D.13 item 3, decided:

- Allowlist at launch: **Toast as POS, Mews as PMS.**
- **A FILLED POS or PMS slot holding a product outside the allowlist → Obi stays hidden.**
  Example: PMS = `opera-cloud` (a real, known catalog product, but not on the launch allowlist)
  hides Obi for that company.
- **An EMPTY slot never hides Obi** (owner-decided yes): a Mews hotel with an empty POS slot
  **does** see Obi — Mews is allowed and nothing in the token is outside the allowlist.

Notes that keep this honest:

- The decided rule names **POS/PMS slots only**. No visibility rule was decided for the
  Accounting slot; a filled accounting slot does not hide Obi under the decided wording. What an
  *unrecognized* accounting value does (beyond failing catalog membership, which fails closed)
  is an open item (`integration-token-decisions.md` §5).
- Hiding is a visibility decision, not the security boundary. A token whose slot value is not in
  the catalog at all keeps **failing closed — 400 before any search** (§D.11); the allowlist
  check is enforced by the backend gate as well, never only by the frontend (never-bend rules
  2–3).

> **Updated 2026-10-13 by ADR-widget-hides-via-visibility-probe (directed path).** This section's slot-form allowlist governs
> the slot token. The directed-connection token (ADR-directed-source-target-routing-labels) dropped the allowlist (D4/D5: routing
> is content-gated by the four label boxes), so ADR-widget-hides-via-visibility-probe restores a widget-eligibility gate for
> the directed path as a **separate global axis**: a product-global `enabled_targets` list in
> `product_catalog.json` (absent ⇒ all enabled, reversible, no migration). After shape/membership
> (unknown target → 400) and vend rights (un-vended → 401), a directed **target** not in
> `enabled_targets` is refused **403** (`TargetNotEnabledError`, body
> `{"error":"integration not available","reason":"target_not_enabled"}`, product id never leaked —
> rule 10). A read-only `GET /chat/visibility` runs the same gate and returns
> `{"visible":true}` / `{"visible":false,"reason":"target_not_enabled"}`. The backend 403 is the
> authority; the frontend hide (loader init fetch, then the `obi:hidden` frame→host message) is UX.
> Retrieval routing (the four-label hard filter, ADR-directed-source-target-routing-labels D5) is **unchanged** — this gate controls
> widget *eligibility* only.
>
> **Superseded 2026-10-20 by ADR-source-system-decides-widget-eligibility:** the list is now
> `enabled_sources` and gates the **source**, not the target. An unknown or disabled source → 403
> `source_not_enabled` (`SourceNotEnabledError`); visibility → `{"visible":false,"reason":"source_not_enabled"}`.
> The target is never checked; an unknown target routes on `[obi-general, {source}-general]`.

## 5 · Eligibility: one filtered search

§D.13 item 3 (§15 keuze 2), decided: **one filtered search.** Eligible documents are exactly:

1. **General guides** — always.
2. **Guides for each filled slot** — the slot product's own documentation.
3. **Guides for pairs the company actually has** — "(Toast→Mews, Mews→their accounting system)"
   (§D.13 verbatim).

### 5.1 · How pairs derive from slots, and the four flow types

§D.2 models four flow directions: **POS→PMS**, **PMS→POS**, **PMS→Accounting**,
**POS→Accounting**. POS→PMS and PMS→POS can be two directions of **one** connection. Pairs map
onto the slots like this:

| Pair (connection type) | Flow directions (§D.2) | Derivable from the launch slots? |
|---|---|---|
| POS–PMS | pos_to_pms, pms_to_pos | Yes — POS and PMS slots both filled |
| PMS–Accounting | pms_to_accounting | Yes — PMS and Accounting slots both filled |
| POS–Accounting | pos_to_accounting | **Not from slots alone** — see below |

### 5.2 · The Toast→QuickBooks honesty clause

§D.2, binding: *"A customer using Toast, Mews, and QuickBooks does **not** automatically have a
direct Toast→QuickBooks connection."* Slots imply **candidate** pairs; only real connections
make a pair one "the company actually has."

The decided launch contract carries **slots only — no connection records**. So the launch
semantics of "pairs the company actually has" (§D.13 item 3) is read from the owner's own
enumeration, which names exactly two pair families: **Toast→Mews** (POS+PMS both filled) and
**Mews→their accounting system** (PMS+Accounting both filled). At launch:

- POS+PMS filled → the POS–PMS pair's guides are eligible (both directions).
- PMS+Accounting filled → the PMS–Accounting pair's guides are eligible.
- **A direct POS–Accounting pair is NOT derived from three filled slots.** It needs a real
  POS→Accounting connection, and the launch token cannot express one. Direct-pair guides become
  eligible only when §D.4's real-connection matching lands and the context carries actual
  connection records (§D.1's illustrative record; open item — `integration-token-decisions.md` §5).

This is a deliberate, honest narrowing: within what the three-slot token can express, the
slot-derived POS–PMS and PMS–Accounting pairs coincide with connections the host platforms
actually configure (Data Hub wires the POS–PMS sync; Base wires the accounting link), which is
why the owner's enumeration stops there. When in doubt the pipeline excludes the pair guide and
answers from general + slot guides — it never invents a connection (§D.1, §D.4).

### 5.3 · Matching discipline (forward pointer)

Within one applicability rule conditions AND together and must match the same actual connection;
separate rules OR; Mews/QuickBooks-or-OperaCloud/Xero must never accidentally admit Mews/Xero
(§D.4). That machinery is §D.3/§D.4 design, not this contract — this contract only fixes what
context it will receive.

## 6 · Per-slot source attribution

§D.13 item 3 (§15 keuze 3), decided: **each result shows which slot let it in.** Every retrieved
document (and its citation/trace) is attributable to the reason it was eligible: `general`, a
named filled slot (`pos` / `pms` / `accounting`), or a slot pair. Wire-level field names were
fixed in substep 8.1.2 (`integration-token-decisions.md` §3, T4/O5 closed): `Citation.attribution`, optional,
enum `general | pos | pms | accounting | pair` (TS union `CitationAttribution`), absent until
the backend assembles it (8.3.4). The requirement — inspectable inclusion reasons, which §D.10's
human validation checks — is decided.

## 7 · Compatibility: old tokens

§D.13 item 3 (§15 keuze 4), decided: existing single-integration tokens **keep working,
interpreted as a token with one filled slot**. Concretely (§D.11):

- Today's `integration: "mews"` claim (`packages/contracts/src/token-claims.json:16`) is read as
  PMS = `mews`, POS empty, Accounting empty. The slot a legacy value fills follows the product's
  role in the catalog.
- Alias values (e.g. `operacloud`) map to canonical ids via the catalog's aliases (§D.11).
  No legacy *compound* value exists — §D.11's `toast-opera` example was proven to appear
  nowhere in the repo and was removed (O8 closed, decision round 2; see `product-catalog.md` §4).
- Unknown values keep failing closed: **400 before any search** (§D.11), exactly like today's
  unknown-scope behavior (`router.py:283`).

## 8 · Examples (the claim shape of record since substep 8.1.2)

The business-claim content below is decided (§D.13); the field names `context`, `slots` and the
null-for-empty convention were **fixed as-is** by the `packages/contracts/` extension (substep
8.1.2, O5 closed — `token-claims.json` now carries this shape, drift-tested against the backend
catalog roles). Standard JWT claims (`iss`, `aud`, `sub`, `iat`, `exp`) are unchanged from
`packages/contracts/src/token-claims.json:7-13` and omitted here for brevity.

### 8.1 · Full three-slot token (Data Hub + Base both configured)

```json
{
  "company_id": "cmp-3141",
  "context": {
    "slots": {
      "pos": "toast",
      "pms": "mews",
      "accounting": "quickbooks-online"
    }
  }
}
```

Visible (every filled POS/PMS slot is on the allowlist). Eligible: general guides, Toast guides,
Mews guides, QuickBooks Online guides, Toast–Mews pair guides, Mews–QuickBooks pair guides.
**Not** eligible: a direct Toast–QuickBooks guide (no real-connection record — §5.2), Mews–Xero
or Opera-Cloud guides (§D.4, §D.9 example 1).

### 8.2 · One-slot token (the legacy-equivalent shape)

```json
{
  "company_id": "cmp-2718",
  "context": {
    "slots": {
      "pos": null,
      "pms": "mews",
      "accounting": null
    }
  }
}
```

Exactly what an old `integration: "mews"` token means after §7's compatibility mapping. Visible.
Eligible: general + Mews guides. No pairs (only one slot filled).

### 8.3 · Mews hotel with an empty POS slot (the decided empty-slot example)

```json
{
  "company_id": "cmp-1618",
  "context": {
    "slots": {
      "pos": null,
      "pms": "mews",
      "accounting": "xero"
    }
  }
}
```

**Visible** — §D.13 verbatim: the empty POS slot never hides Obi; Mews is allowed and nothing in
the token is outside the allowlist. Eligible: general, Mews, Xero, and Mews–Xero pair guides.
Never Mews–QuickBooks guides (§D.4).

### 8.4 · Out-of-allowlist FILLED slot

```json
{
  "company_id": "cmp-0577",
  "context": {
    "slots": {
      "pos": "toast",
      "pms": "opera-cloud",
      "accounting": null
    }
  }
}
```

**Obi stays hidden**: the PMS slot is filled with a real catalog product that is not on the
launch allowlist (only Mews is, as PMS). The backend gate refuses to serve the session too — the
frontend hiding is UX, not the boundary (§4).

> **Directed-path analogue (ADR-widget-hides-via-visibility-probe, 2026-10-13).** The directed token has no allowlist (§4
> note), but the same "hidden + backend refuses" shape now holds via target-enablement: a directed
> `source → target` whose **target** is not in `product_catalog.json`'s `enabled_targets` yields
> `GET /chat/visibility` → `{"visible":false,"reason":"target_not_enabled"}` (widget hidden) and a
> **403** on `POST /chat`. E.g. `mews → quickbooks-online` at launch (QuickBooks not enabled) hides
> Obi, mirroring this off-allowlist slot example.
>
> **Superseded 2026-10-20 (ADR-source-system-decides-widget-eligibility):** only the source decides.
> `mews → quickbooks-online` now **shows** Obi (Mews is an enabled source); `quickbooks-online → mews`
> is hidden (`source_not_enabled`).

## 9 · Deliberately NOT in the launch contract

§D.1's illustrative context record is richer than the decided launch token. These fields exist
in the design's target shape but are **not** decided for launch and are **not** in this
contract: `property_id` and per-property context, `connections` (actual connection records with
`type`/`directions`/`instance`), `selected_connection`, `unknown_roles`, multiple
instances/connections per company. Each is tracked in `integration-token-decisions.md` §5 with the §D part
that will decide it (§D.3–§D.4). Never infer any of them from the slots.
