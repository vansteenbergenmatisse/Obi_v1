# Routing test labels — the Confluence pages to create (Option A / substep 9.5.1)

**Handed over to the owner 2026-10-12. Owner-finalized 2026-10-12.** This is the exact label scheme for
the directed-connection routing engine (ADR-0020). The owner creates these as separate Confluence pages;
the engine (`9.2.1`–`9.4.1`) routes on the routing label, and the automated DB tests seed the same scheme.

**The live routing-label set is exactly these nine labels** — `obi-general`, `toast-general`,
`mews-general`, `opera-cloud-general`, `toast-to-pms`, `mews-to-pos`, `opera-cloud-to-pos`,
`toast-to-accounting`, `mews-to-accounting`. There is **no** accounting-product general page
(e.g. `quickbooks-online-general`) and **no** `opera-cloud-to-accounting` page at launch: those are valid
engine labels (see "The full catalog" below) but their boxes stay empty (content-gated, ADR-0020 D5).

Source of truth: `knowledge-base/config/product_catalog.json` + `build_labels()` in
`backend/app/platform/config/product_catalog.py`. A connection `source → target` resolves to exactly
four label "boxes": `obi-general`, `{source.slug}-general`, `{target.slug}-general`,
`{source.slug}-to-{target.role}` (the role is the **target's** kind: pos/pms/accounting). Direction
is primary: `toast-to-pms ≠ mews-to-pos`.

## Two labels per page

Each test page gets **both**:

1. **Membership tag — the same on every page:** `obi-general-test`. This keeps the page in the index
   and inside locks 0–2 (ADR-0020 D0 leaves company/source isolation unchanged). These are general
   guidance pages, not customer-isolated data, so the base scope is correct.
2. **Exactly one routing label** from the table below. This is what Option A hard-filters on.

> Note the two near-identical strings are deliberately different: `obi-general-test` is the
> knowledge-**scope** tag (membership/isolation axis); `obi-general` is the **routing** label
> (content-routing axis).

## Core set — required (launch: Toast ⇄ Mews; proves general / system / direction / isolation)

| # | Page title | Routing label | Marker word (unique) | Served to connections where… |
|---|---|---|---|---|
| 1 | Obi — general help | `obi-general` | golden apples | **every** connection |
| 2 | Toast — system guide | `toast-general` | grapes *(existing)* | Toast is source or target |
| 3 | Mews — system guide | `mews-general` | red bananas *(existing)* | Mews is source or target |
| 4 | Toast → PMS — connection guide | `toast-to-pms` | silver pears | source = Toast, target is a PMS |
| 5 | Mews → POS — connection guide | `mews-to-pos` | bronze plums | source = Mews, target is a POS |

What this proves:
- **Toast→Mews** sees pages 1,2,3,4 (golden apples, grapes, red bananas, silver pears) and **never** page 5.
- **Mews→Toast** sees pages 1,3,2,5 and **never** page 4 — the direction flip.

## Extension A — recommended (Opera Cloud; proves `{target}-general` discriminates PMS products)

| # | Page title | Routing label | Marker word | Served where… |
|---|---|---|---|---|
| 6 | Opera Cloud — system guide | `opera-cloud-general` | copper cherries | Opera Cloud is source or target |
| 7 | Opera Cloud → POS — connection guide | `opera-cloud-to-pos` | amber figs | source = Opera Cloud, target is a POS |

A **Toast→Opera Cloud** chat sees 1,2,6,4 (the connection box `toast-to-pms` is shared across all
PMSes) but **not** page 3 (`mews-general`) — the per-system box is what separates Mews from Opera.

## Extension B — recommended (accounting as target; proves accounting content-gating)

Accounting products are **targets only** — a chat never starts from one, so there is no accounting-product
general page. The accounting connection box (`{source}-to-accounting`) is product-agnostic and carries the
content. The `{target}-general` box the engine emits for an accounting target (e.g. `quickbooks-online-general`)
stays **empty** at launch (content-gated, ADR-0020 D5); the connection still routes on `obi-general` +
`{source}-general` + `{source}-to-accounting`.

| # | Page title | Routing label | Marker word | Served where… |
|---|---|---|---|---|
| 8 | Toast → Accounting — connection guide | `toast-to-accounting` | green kiwi | source = Toast, target is accounting |
| 9 | Mews → Accounting — connection guide | `mews-to-accounting` | blue melon | source = Mews, target is accounting |

## The full catalog (for reference — every valid label form)

> These are the forms the engine *accepts and can emit* — a **superset** of the nine labels the owner
> populates (top of this doc). `quickbooks-online-general`, `xero-general` and `opera-cloud-to-accounting`
> are valid engine labels with **no page** at launch; their boxes stay empty (content-gated, ADR-0020 D5).

- **Products** (canonical id · role): `toast`·pos, `mews`·pms, `opera-cloud`·pms,
  `quickbooks-online`·accounting, `xero`·accounting.
- **`{slug}-general`** is valid for every product above.
- **`{slug}-to-{kind}`** valid kinds are `pos` / `pms` / `accounting`, e.g. `toast-to-pms`,
  `mews-to-pos`, `opera-cloud-to-pos`, `toast-to-accounting`, `mews-to-accounting`,
  `opera-cloud-to-accounting`.
- An unknown system resolves to `[obi-general]` only; malformed labels (`toast-to-hotel`,
  `toast-to-pmss`, a bare slug) are rejected by `is_valid_label`.

## Launch allowlist caveat (live gate today)

The gate's launch allowlist is **POS = Toast, PMS = Mews** only. An **Opera Cloud** token is
refused (401) at the gate until Opera is allowlisted, so the Extension-A pages are routable in the
DB/engine tests but cannot be exercised through a real Opera token yet. Toast + Mews is the path
that works end to end today.
