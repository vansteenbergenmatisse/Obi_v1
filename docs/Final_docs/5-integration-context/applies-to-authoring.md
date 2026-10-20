# Authoring "Applies to" on a Confluence page

**Status: the authoring guide of record for panel `mi-applies` (substep 8.2.1, 2026-10-05).**
The validated schema lives in `backend/app/features/ingestion/domain/applicability.py`; the
design is plan.md §D.3. This guide is for page authors: what to put on a page so Obi knows
exactly which setup the page is for.

## 1 · The decision: a standard table in the page body

§D.3 required choosing ONE authoring approach — a standard applicability table on the page, or
structured content properties with a controlled editing form. **Decided (8.2.1): the standard
table in the page body.** Evidence, not taste:

1. **The sync already fetches it.** The Confluence client fetches every page body in storage
   format (`backend/app/platform/clients/confluence_client.py:205`, `body-format=storage`) —
   the table arrives with the body the pipeline already reads. Content properties would need a
   new v2 API surface (`/pages/{id}/properties`), new client code and new failure modes.
2. **A table edit is a content edit.** Editing a body table bumps the page version and fires
   the same webhook/sweep path every content change rides — the metadata edit is *seen*.
   A content-property edit does **not** bump the page version: today's change detection would
   never notice it, a silent-staleness risk the design forbids.
3. **Authors already have the editor.** The "controlled editing form" for content properties
   would be a Forge/Connect app that does not exist. A table is authored in the normal
   Confluence editor by the same people who already manage labels
   (`docs/Final_docs/handover/tagging-guide.md`).

Parsing the table out of the stored body (and stamping the validated record onto chunks)
landed in substep **8.2.2** (`applies_to_parsing.py` + the sync command handler): the table
is lifted out of the body *before* normalization — it is metadata, never chunk content — so
editing only the table restamps the existing chunks over the §D.0 route (same version id, no
re-embed), and removing it restamps back to label-only. The editor's capitalization is
forgiven at the parse edge: the header match is case-insensitive, and field names and values
are trimmed and lowercased before validation (the same normalization labels get). A
mixed-applicability page is **split** into separate pages — several tables on one page OR
together as whole-page alternatives (§D.4); there are no per-section rules by design, so one
broad page never exposes unrelated instructions.

## 2 · The shape: one table per rule

Put a two-column table on the page. The **header row's first cell is exactly `Applies to`**
(the second header cell is free text, e.g. "value"). Every row below it is one `field | value`
pair. One table = one complete rule. **Several `Applies to` tables on one page OR together**
(§D.4): the page applies when *any one* table matches. Within one table, every row must match
the *same actual connection* — conditions AND together.

**A page with no `Applies to` table at all keeps today's label-only behavior.** That is the
documented compatibility default (§D.11), not a wildcard: labels still decide membership and
sharing, and nothing new is required of existing pages. An authored table that is *wrong* never
falls back to that default — it fails validation loudly at sync, by name.

### The iron rules

- **"Any" is always written out.** Where a wildcard is allowed, you author the literal value
  `any`. A field you *leave out* never becomes a wildcard — a missing required field is a
  loud validation failure (`missing-field:<name>`), never a silent widening.
- **One vocabulary.** Products, roles, connection types and flow directions come from the
  product catalog (`knowledge-base/config/product_catalog.json`; see `product-catalog.md`). Aliases
  resolve (`operacloud` → `opera-cloud`); unknown values fail (`unknown-product`).
- **Typos fail loudly.** A field name the level does not know is rejected (`unknown-field`) —
  a silently dropped row would silently widen the rule.
- Applicability **restricts relevance on top of** labels, RLS and page permissions — it never
  grants access. An `Applies to` table on an untagged or `classified` page grants nothing.

## 3 · The five levels and their required fields

| level | required fields | `any` allowed in |
|---|---|---|
| `general` | — | — |
| `software` | `product` | nowhere (`product: any` is rejected — author level `general` instead) |
| `platform-interface` | `product`, `platform` | nowhere |
| `connection` | `connection`, one field per role of that connection type, `directions` | the role fields; `directions` |
| `workflow` | `binding`, `connection-1`, `connection-2` (… `-N`) each with their role and directions fields | the per-connection role fields; directions — but the *shared linking product* must be concrete |

Optional on every level: the variant requirements `variant-feature`, `variant-accounting-flow`,
`variant-version` (§D.3) — author one only when the instructions depend on it. To not restrict
by a variant, **omit the field** (`variant-…: any` is rejected: an optional restriction is
omitted, not wildcarded).

Vocabulary today (from the catalog and the platform registry):

- products: `toast` (pos) · `mews` (pms) · `opera-cloud` (pms) · `quickbooks-online`
  (accounting) · `xero` (accounting)
- connection types → directions: `pos-pms` → `pos_to_pms`, `pms_to_pos` ·
  `pms-accounting` → `pms_to_accounting` · `pos-accounting` → `pos_to_accounting`
- platforms: `datahub` (Base joins the registry with O7, after Phase A — until then
  `platform: base` fails validation honestly)
- bindings: `same-instance`, `same-property`

## 4 · Worked examples (the §D.3 five, verbatim intent)

### 4.1 General Mews guidance → applies to Mews PMS (level: software)

| Applies to | value |
|---|---|
| level | software |
| product | mews |

### 4.2 General Mews accounting guidance → Mews connected to ANY supported accounting target

The "any" is authored explicitly — and it is kept literally, so it tracks the catalog: when a
new accounting product is added to the catalog, the rule covers it without editing the page.

| Applies to | value |
|---|---|
| level | connection |
| connection | pms-accounting |
| pms | mews |
| accounting | any |
| directions | pms_to_accounting |

### 4.3 Mews-to-QuickBooks instructions → the actual Mews→QuickBooks accounting connection

| Applies to | value |
|---|---|
| level | connection |
| connection | pms-accounting |
| pms | mews |
| accounting | quickbooks-online |
| directions | pms_to_accounting |

### 4.4 Toast-to-Mews room-charge instructions → the actual Toast→Mews flow direction

| Applies to | value |
|---|---|
| level | connection |
| connection | pos-pms |
| pos | toast |
| pms | mews |
| directions | pos_to_pms |

### 4.5 A Toast→Mews→QuickBooks guide → both linked connections, same Mews instance, same property

| Applies to | value |
|---|---|
| level | workflow |
| binding | same-instance, same-property |
| connection-1 | pos-pms |
| connection-1-pos | toast |
| connection-1-pms | mews |
| connection-1-directions | pos_to_pms |
| connection-2 | pms-accounting |
| connection-2-pms | mews |
| connection-2-accounting | quickbooks-online |
| connection-2-directions | pms_to_accounting |

The two connections must share a **concrete** product (here `mews`) — that shared product is
what the binding binds. `any` never counts as the link.

### 4.6 Two alternatives OR together (§D.4's never-cross example)

A page for *Mews/QuickBooks or Opera-Cloud/Xero* is **two tables** (4.3 above plus the same
shape with `pms: opera-cloud`, `accounting: xero`). It can then never accidentally apply to
Mews/Xero: each table is complete on its own, and matching never mixes rows across tables.

### 4.7 Platform-interface guidance (level 3)

| Applies to | value |
|---|---|
| level | platform-interface |
| product | mews |
| platform | datahub |

### 4.8 General guidance (level 1)

| Applies to | value |
|---|---|
| level | general |

Author this only when the page genuinely applies to everyone; it is *not* the default for a
page without a table (that default is label-only behavior, §2).

## 5 · What failure looks like

Validation failures are named, one reason per failure, raised at sync: the sync job FAILS
(loud in the job queue, the reason slug in its recorded error) and the page's previously
indexed state survives untouched — a wrong table never silently falls back to label-only.
The schema reasons: `missing-field:<name>` · `empty-value` · `unknown-level` ·
`unknown-field` · `unknown-product` · `ambiguous-product` · `any-not-allowed` ·
`unknown-platform` · `unknown-connection-type` · `role-mismatch` · `unknown-direction` ·
`missing-field:binding` · `unknown-binding` · `too-few-connections` · `unlinked-connections` ·
`empty-record`. Every one is proven by a test in
`backend/app/features/ingestion/tests/test_applicability_schema.py` (panel `mi-applies`).
The parser adds two table-shape reasons (8.2.2): `malformed-table` (a row that is not one
`field | value` pair, or a body too broken to parse that still appears to carry a table) and
`duplicate-field` (the same field twice in one table — last-one-wins would silently drop a
condition); proven in `test_applies_to_parsing.py` and, end to end, in
`test_applicability_stamp.py::test_in2_applies_invalid_table_fails_the_sync_loudly`.
