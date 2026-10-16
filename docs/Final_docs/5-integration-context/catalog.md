# The central product catalog · `knowledge-base/config/product_catalog.json`

**What it is:** THE single canonical registry of software products for the integration context
(§D.1: "canonical product identifiers, aliases (incl. legacy values like `toast-opera`), roles
(pms/pos/accounting/…), and supported connection types" — note: `toast-opera` was an *illustrative*
example only; §4 below (O8) records it exists nowhere and `legacy_aliases` is empty). It is a data
concern, so it lives in
`knowledge-base/config/` beside the tag map and the platform list (root `CLAUDE.md`, "Where a
new file goes" rule 1; §D.12 item 2).

**The one rule above all: nothing else may define a product.** A product id, role, alias, or
supported connection type exists in exactly this file or not at all. No backend constant, no
frontend list, no prompt text, no test fixture defines one — they read (or will read) this file.
This mirrors the standing rule for tags and platforms (`knowledge-base/CLAUDE.md`: "nothing else
may define a tag or platform").

**Loader wired (substep 8.1.1, 2026-10-05):** `backend/app/platform/config/product_catalog.py`
reads and validates this file at startup (fail-fast via a `Settings` model validator, the
knowledge_scopes.py pattern), enforcing §3 below — one red-first unit test per rule in
`backend/app/platform/config/tests/test_product_catalog.py`. The gate does not consume it yet
(§6 items 2 onward; substep 8.1.3).

**Loader extended for directed routing (substep 9.1.1, Option A / ADR-0020):** the same catalog
now also resolves a directed `source → target` connection into the four ordered Confluence label
boxes. `product_catalog.py` gains three members on `ProductCatalog`:
`resolve_system(name)` (lenient, case- and whitespace-insensitive match on canonical id, alias or
display name; an unmatched value → `None`, a clear miss — distinct from the strict gate resolver
`resolve`, which is left unchanged); `build_labels(source, target)` →
`[obi-general, {source.slug}-general, {target.slug}-general, {source.slug}-to-{target.kind}]`
(slug = the resolved canonical id; kind = the **target** product's role; an unknown source OR
target yields `[obi-general]` alone, never a wildcard); and `is_valid_label(label)` (accepts only
`obi-general`, `{slug}-general`, `{slug}-to-(pos|pms|accounting)` with a catalog slug — rejects
`toast-to-pmss`, `toast-to-hotel`, unknown slugs). The module constant `GENERAL_LABEL = "obi-general"`
names the always-present box. These are routing **labels**, not products — the §3 reserved-name
rules gate product ids, never these boxes. Unit-tested in
`backend/app/platform/config/tests/test_connection_routing.py` (the five worked examples, the
unknown-system fallback, the malformed-label rejections). Retrieval still does not consume them —
the chunk `labels` column, the chat session and the hard filter are later Option A substeps
(9.1.2+). **How we know it works:** 25 red-first-then-green unit assertions; `make check` green.

## 1 · Division of labor with the existing registries

| File | Owns | Does NOT own |
|---|---|---|
| `knowledge_scopes.json` | the knowledge-scope **tags** (incl. `obi-general-test`, reserved `classified`) | products |
| `platforms.json` | trusted JWT issuers + the **integration→scope map** + per-platform vend rights | products, scope tags |
| `product_catalog.json` | **products**: canonical ids, roles, aliases, connection types; the launch allowlist | scope tags, issuers, the integration→scope map |

The catalog deliberately does **not** duplicate the integration→scope map — `platforms.json`
already owns it (`platforms.json:10-14`), and one concept gets one source. The coupling is by
id: `toast`, `mews`, `opera-cloud` here equal the integration keys there, and the loader must
cross-check that (§6).

**Why `general` is not in the catalog:** `general` is a knowledge scope
(`obi-general-test`, `knowledge_scopes.json:4`), not a software product — no customer "runs"
general, no slot can hold it, it joins eligibility unconditionally (§D.13 keuze 2: general
guides are always eligible). Putting it in the catalog would make it a valid slot value, which
is wrong. The call: it stays in `knowledge_scopes.json` only.

## 2 · Fields

Top-level keys:

- **`_readme`** — the operator-facing summary, same convention as the sibling configs.
- **`products`** — an object keyed by **canonical id**. Per product:
  - `label` — human-readable display name.
  - `role` — exactly one of `pos` | `pms` | `accounting` (the three §D.13 slot roles). One role
    per product at launch; a vendor's second product with a different role gets its **own
    canonical id** (§D.1: "distinguish different products from the same vendor where
    necessary" — exactly why `opera-cloud` is its own id, not an "opera" variant).
  - `aliases` — alternative single-product spellings that resolve to this id.
  - `connection_types` — which connection families (keys of the top-level `connection_types`)
    this product can take part in.
- **`connection_types`** — the §D.2 connection families: `roles` (the two roles a connection of
  this type joins) and `directions` (the §D.2 flow directions it can carry; `pos-pms` carries
  `pos_to_pms` and `pms_to_pos` as two directions of ONE connection). A connection type in a
  product's list means "supported", never "exists for a given customer" — real connections are
  §D.4's territory.
- **`legacy_aliases`** — legacy **compound** claim values mapping to the **list** of canonical
  ids they expand to (§D.11's "map to canonical ids"). Distinct from per-product `aliases`,
  which are one-to-one.
- **`launch_allowlist`** — the §D.13 visibility decision: per POS/PMS role, the product ids
  allowed at launch (`pos: [toast]`, `pms: [mews]`). A **filled** POS/PMS slot outside this list
  hides Obi; an **empty** slot never does. Data, not code, so widening the launch set later is a
  config edit plus its test. Governs the **slot** token only.
- **`enabled_targets`** — **optional flat list** (ADR-0022, substep 9.5 / Task 5): the product-global
  set of targets enabled for the **directed** token path (shipped `["mews", "toast", "opera-cloud"]`).
  A directed `source → target` whose **target** is not in this list is refused — backend **403**
  (`TargetNotEnabledError`, after vend rights) and `GET /chat/visibility` → `visible:false` so the
  widget hides. **Absent ⇒ all products enabled** (feature inert, backward-compatible). Data, not
  code; reversible with no migration (remove/empty ⇒ today's content-gated behavior). This is the
  directed-path analogue of `launch_allowlist`; it does **not** touch retrieval routing (ADR-0020 D5).

## 3 · Validation rules (what the loader enforces at startup — built in 8.1.1)

In the fail-fast style of `load_recognized_knowledge_scopes`
(`backend/app/platform/config/knowledge_scopes.py`) — a bad entry stops the backend before it
can mis-scope anyone, each failure naming the offending entry:

1. Every canonical id and alias is a short lowercase slug (letters, digits, hyphens); no
   silent lowercasing.
2. Canonical ids are unique; aliases are unique across the **whole** file (per-product aliases
   plus `legacy_aliases` keys) and never collide with any canonical id.
3. Every `role` is one of `pos` | `pms` | `accounting`.
4. Every `connection_types` entry on a product is a key of the top-level `connection_types`,
   and the product's `role` appears in that connection type's `roles`.
5. Every `legacy_aliases` value is a non-empty list of existing canonical ids, at most one per
   role (an expansion can never put two products in one slot).
6. `launch_allowlist` lists only existing canonical ids whose `role` matches the list they sit
   in.
6b. `enabled_targets` (optional; ADR-0022) — when present, every entry is an existing catalog
   canonical id; stored as a frozenset; an unknown id stops the backend at boot. Absent ⇒ all
   products enabled (no validation, feature inert).
7. The reserved names never appear anywhere in this file: `classified`,
   `obi-general-test`/`general`, and any `obi-*` scope-tag spelling (scope tags live in
   `knowledge_scopes.json` only).
8. Cross-check against `platforms.json`: every key of its `integrations` map is a canonical id
   (or alias) in this catalog — the two files may never disagree on what an integration claim
   value means.

Since substep 8.2.1 the loader also validates and **exposes each connection type's §D.2 flow
directions** (`ProductCatalog.connection_directions`: non-empty, unique, lowercase underscore
tokens) — the "Applies to" schema (`applies-to-authoring.md`,
`backend/app/features/ingestion/domain/applicability.py`) validates authored directions against
this one vocabulary, never a copy.

## 4 · How aliases resolve

Resolution happens once, before any validation or allowlist check, at the gate:

1. The incoming value is matched against canonical ids first.
2. No match → matched against per-product `aliases` → resolves to that one canonical id
   (e.g. `operacloud` → `opera-cloud`).
3. No match → matched against `legacy_aliases` → expands to its list of canonical ids, each
   filling the slot of its role. **The map is empty today** (see the O8 decision below) — this
   step is the mechanism held ready for a real legacy compound value, not a populated path.
4. Still no match → **unknown value, fail closed: 400 before any search** (§D.11). Never a
   fallback, never a fuzzy match.

**O8 CLOSED — `toast-opera` does not exist (owner decision round 2, 2026-10-05).** The value
appears nowhere in this repo — not in `knowledge_scopes.json`, not in `platforms.json`, not in
any code, token fixture, or tag (verified by whole-repo search, 2026-10-05). Its only
occurrences are plan.md's own prose, where it was introduced as an *illustrative example* of
what a legacy value could look like ("e.g. legacy values like `toast-opera`", §D.1 line ~190)
and carried into §D.11 — an invented placeholder describing the alias mechanism, never an
observed datum. The real observed legacy spelling is `operacloud` (per-product alias, evidence
above). Decision: the compound is **removed from the catalog**; `legacy_aliases` stays `{}` as
a documented mechanism. If a platform ever vends a real compound value, it is added then, with
its evidence named.

**Alias policy:** aliases are **evidence-based only**. `operacloud` is included because that
spelling exists in repo data (the scope tag `obi-operacloud-test`, `knowledge_scopes.json:6`,
and §15's own example `knowledge_scopes: [toast, operacloud]`, sync-rules/plan.md:1031). No
invented shorthands (`qbo`, `quickbooks`, …) — an alias is added when a real legacy value is
found in a token, a config, or an owner statement, and the addition names its evidence.

## 5 · How to add a product

1. Add one entry under `products`: canonical id (lowercase slug), `label`, one `role`,
   `aliases` (usually empty), and its supported `connection_types`. Nothing else in the
   codebase defines the product.
2. If the product's docs get a knowledge scope: add the tag to `knowledge_scopes.json` and the
   integration→scope mapping to `platforms.json` — those files keep owning those concepts
   (today no scope tags exist for the accounting products; open item O9 in
   `decision-memo.md`).
3. If customers should see it at launch in a POS/PMS slot: add it to `launch_allowlist`
   (an owner decision, like every visibility change).
4. Once the loader exists: restart to pick the file up (same operational note as
   `platforms.json` in `handover/tag-administration.md`), and every addition lands with its
   test (never-bend rule 11).

## 6 · Implementation TODO

- ~~A loader/validator module in `backend/app/platform/config/` (pattern:
  `knowledge_scopes.py`), enforcing §3 at startup and exposing the catalog to the gate~~ —
  **done, substep 8.1.1 (2026-10-05)**: `product_catalog.py`, exported from the platform
  config root, fail-fast via `Settings._require_valid_product_catalog`.
- The gate change consuming it (slot membership + role agreement + allowlist + alias
  resolution) — see `decision-memo.md` §4.
- The `platforms.json` cross-check (§3 rule 8) wired into the same startup validation.
- Tests red-first per behavior, including the §D.9 example matrix.
