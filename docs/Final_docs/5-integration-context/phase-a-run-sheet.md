# Phase A · run sheet (fill-in checklist for substep 8.5.2)

**Status: prepared, not run.** This is the owner's top-to-bottom worksheet for Phase A. It
transcribes the cases from `phase-a-validation-cases.md` into one fillable section per case (1–18),
each carrying the §D.10 seven-step evidence table with **empty** PASS/FAIL and trace-ref cells.
Nothing here is a claim that any case passed — a case counts only when a human records evidence per
step (panel `mi-validate`, plan.md §D.10).

Read `phase-a-validation-cases.md` for the full derivation of every expected result (where each
"expected" line comes from in the design) and the honest gaps. This sheet is the thing you fill in;
that doc is the reference. The seven-step order (never reorder) is: **1 Configuration · 2 Metadata ·
3 Included/excluded page & chunk ids · 4 Reranker results · 5 Answers · 6 Citations · 7 Further
retrieval** (plan.md §D.10, verbatim).

**Badge vocabulary** (widget `message-bubble.tsx`): `general` → "General guide"; `pos` → "For your
POS"; `pms` → "For your PMS"; `accounting` → "For your accounting"; `pair` → "For your integration".

**Where to look:** every answer carries a `trace_id` (`rag_agent/schemas.py`); the trace row
(`retrieval/infrastructure/trace_repo.py`) holds the candidate set, reranked order, and whether a
second read happened. A refusal on the directed path returns a bare HTTP status (400/401) with no
body (`router.py:285-291`). If no trace viewer exists in your environment, read the trace row by
`trace_id` directly and note that in the ref cell.

**How to reach the standalone cases (1–10):** `make up` → `make migrate` → seed the corpus the case
names → `make web-dev`, open the app, pick the named preset in the simulated-context bar
(`standalone-preset-bar.tsx`, reading `standalone_presets.json`). Switching a preset starts a fresh
chat. **How to reach the integration cases (11–18):** the local test-host pages
(`frontend/src/app/test-hosts/*`) mint RS256 directed tokens against `test-*.local` issuers; a
partner-staging leg runs only once that partner's issuer/JWKS/token endpoint exist. Record the two
legs separately — a local PASS never stands in for a partner-staging PASS.

---

## Standalone retrieval cases (1–10)

### Case 1 — General guidance baseline (configuration + general)

- **How to reach this context:** preset **"No preset (general only)"** — company with all three
  slots empty. Connection under test: none (general-only visibility rule).
- **Questions:** (1) a general question general guidance answers (e.g. "What is Obi?" / "How do I
  get started?"); (2) a connection-specific question with no matching slot (e.g. "Why are my Mews
  invoices missing in QuickBooks?").
- **Expected included:** only **general** pages. **Excluded:** every software, connection, and
  workflow page (no slot filled → nothing slot- or pair-specific is eligible).
- **Expected citations + badges:** every badge reads **"General guide"** (`general`); no
  `pos`/`pms`/`accounting`/`pair` badge appears.

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | No preset; all slots empty; widget shows simulated-context marker; Obi visible | | | | |
| 2 | Metadata | Seeded general pages present | | | | |
| 3 | Included / excluded ids | Included: general only. Excluded: all software/connection/workflow | | | | |
| 4 | Reranker results | Re-orders eligible evidence only; no excluded page reintroduced | | | | |
| 5 | Answers | General Q answered from general; connection-specific Q not answered with connection instructions — serves general + asks for missing config (never broadens) | | | | |
| 6 | Citations | Every sentence cited; all badges "General guide" | | | | |
| 7 | Further retrieval | If a 2nd read happened, ≤ 2 reads, same eligibility, no excluded page | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

### Case 2 — POS → PMS, two systems (§D.9 example 2)

- **How to reach this context:** preset **`pos-to-pms`** — slots `pos: toast`, `pms: mews`,
  `accounting: null`. Connection under test: Toast/Mews (both directions of the one connection).
- **Question:** "Why are Toast room charges missing in Mews?"
- **Expected included:** **general**, **Toast** (software), **Mews** (software), **Toast/Mews
  connection** (both POS→PMS room-charge and PMS→POS guest-info directions). **Excluded:** all
  accounting (QuickBooks, Xero), Mews/QuickBooks and direct Toast/QuickBooks pair guides, Mews/Xero,
  any Opera Cloud guidance.
- **Expected citations + badges:** general → "General guide"; Toast → "For your POS" (`pos`); Mews →
  "For your PMS" (`pms`); Toast/Mews connection → "For your integration" (`pair`).

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Preset `pos-to-pms`; slots toast/mews/null; marker shown; Obi visible | | | | |
| 2 | Metadata | Seeded pages carry the Applies-to records this case needs | | | | |
| 3 | Included / excluded ids | Included: general, Toast, Mews, Toast/Mews (both directions). Excluded: all accounting, Mews/QB, Toast/QB, Mews/Xero, Opera Cloud | | | | |
| 4 | Reranker results | Eligible-only; no excluded page reintroduced | | | | |
| 5 | Answers | Answers from POS→PMS connection evidence, naming each system's facts; no accounting content | | | | |
| 6 | Citations | general→"General guide"; Toast→"For your POS"; Mews→"For your PMS"; connection→"For your integration" | | | | |
| 7 | Further retrieval | ≤ 2 reads; same eligibility; no excluded page | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

### Case 3 — PMS → POS, two systems (§D.9 example 3)

- **How to reach this context:** preset **`pms-to-pos`** — slots `pos: toast`, `pms: mews`,
  `accounting: null` (same slots as Case 2; only the `flow_type` label differs). Connection under
  test: Toast/Mews.
- **Question:** "Why is Mews guest information unavailable in Toast?"
- **Expected included:** **general**, **Toast**, **Mews**, **Toast/Mews connection** (enabled
  PMS→POS guest-info direction plus the POS→PMS direction). **Excluded:** Mews/Xero and Opera Cloud
  guidance; all accounting pairs.
- **Expected citations + badges:** general → "General guide"; Toast → "For your POS"; Mews → "For
  your PMS"; Toast/Mews connection → "For your integration" (`pair`).

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Preset `pms-to-pos`; same slots as Case 2; marker shown; Obi visible | | | | |
| 2 | Metadata | Seeded pages carry the needed Applies-to records | | | | |
| 3 | Included / excluded ids | Included: general, Toast, Mews, Toast/Mews. Excluded: Mews/Xero, Opera Cloud, all accounting pairs | | | | |
| 4 | Reranker results | Eligible-only; no excluded page reintroduced | | | | |
| 5 | Answers | Answers from the enabled PMS→POS direction. **Cross-check Case 2:** same page ids eligible (slot-driven, not label-driven) — record the equivalence | | | | |
| 6 | Citations | general→"General guide"; Toast→"For your POS"; Mews→"For your PMS"; connection→"For your integration" | | | | |
| 7 | Further retrieval | ≤ 2 reads; same eligibility; no excluded page | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

### Case 4 — PMS → Accounting, two systems (§D.9 example 1)

- **How to reach this context:** preset **`pms-to-accounting`** — slots `pos: null`, `pms: mews`,
  `accounting: quickbooks-online`. Connection under test: Mews/QuickBooks.
- **Question:** "Why are my Mews invoices missing in QuickBooks?"
- **Expected included:** **general**, **Mews**, **QuickBooks Online**, **Mews/QuickBooks
  connection**. **Excluded:** Mews/Xero, unrelated Toast room-charge (Toast/Mews), bare Xero and
  bare Toast (no POS slot).
- **Expected citations + badges:** general → "General guide"; Mews → "For your PMS" (`pms`);
  QuickBooks → "For your accounting" (`accounting`); Mews/QuickBooks → "For your integration"
  (`pair`).

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Preset `pms-to-accounting`; slots null/mews/quickbooks-online; marker shown; Obi visible | | | | |
| 2 | Metadata | Seeded pages carry the needed Applies-to records | | | | |
| 3 | Included / excluded ids | Included: general, Mews, QuickBooks, Mews/QB. Excluded: Mews/Xero, Toast/Mews room-charge, bare Xero, bare Toast | | | | |
| 4 | Reranker results | Eligible-only; no excluded page reintroduced | | | | |
| 5 | Answers | Answers from Mews→QuickBooks evidence; no Xero content; no room-charge content | | | | |
| 6 | Citations | general→"General guide"; Mews→"For your PMS"; QuickBooks→"For your accounting"; connection→"For your integration" | | | | |
| 7 | Further retrieval | ≤ 2 reads; same eligibility; no excluded page | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

### Case 5 — POS → Accounting, two systems + the Toast→QuickBooks honesty clause

- **How to reach this context:** preset **`pos-to-accounting`** — slots `pos: toast`, `pms: null`,
  `accounting: quickbooks-online`. Connection under test: none derivable (a direct POS–Accounting
  pair is **not** derivable from slots alone at launch — §5.2).
- **Question:** "Why aren't my Toast sales reaching QuickBooks?"
- **Expected included:** **general**, **Toast**, **QuickBooks Online**. **Excluded:** the direct
  Toast/QuickBooks connection guide (launch slots-only token cannot express it — §5.2), all Mews
  guidance, any pair needing Mews.
- **Expected citations + badges:** general → "General guide"; Toast → "For your POS"; QuickBooks →
  "For your accounting". **No `pair` badge** (no eligible connection guide).

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Preset `pos-to-accounting`; slots toast/null/quickbooks-online; marker shown; Obi visible | | | | |
| 2 | Metadata | Seeded pages carry the needed Applies-to records | | | | |
| 3 | Included / excluded ids | Included: general, Toast, QuickBooks. Excluded: direct Toast/QB connection, all Mews, any Mews-needing pair | | | | |
| 4 | Reranker results | Eligible-only; no excluded page reintroduced | | | | |
| 5 | Answers | Honesty case: answers from general+Toast+QuickBooks; names the missing config; does **not** surface a Toast/QB connection guide or invent a connection | | | | |
| 6 | Citations | general→"General guide"; Toast→"For your POS"; QuickBooks→"For your accounting"; no `pair` badge | | | | |
| 7 | Further retrieval | ≤ 2 reads; same eligibility; no excluded page | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

### Case 6 — Three systems: multiple connections + workflow binding (§D.9 example 4)

- **How to reach this context:** preset **`three-system`** — slots `pos: toast`, `pms: mews`,
  `accounting: quickbooks-online`. Connections under test: Toast/Mews + Mews/QuickBooks + the
  three-system Toast→Mews→QuickBooks workflow (same-instance binding).
- **Question:** "Why are restaurant charges not reaching QuickBooks?"
- **Expected included:** **general**, **Toast**, **Mews**, **QuickBooks**, **Toast/Mews
  connection**, **Mews/QuickBooks connection**, **three-system workflow** guide. **Excluded:** the
  direct Toast/QuickBooks guide (that connection does not exist — §D.9 example 4, §5.2).
- **Expected citations + badges:** general → "General guide"; Toast → "For your POS"; Mews → "For
  your PMS"; QuickBooks → "For your accounting"; both connection pages and the workflow page → "For
  your integration" (`pair`).

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Preset `three-system`; slots toast/mews/quickbooks-online; marker shown; Obi visible | | | | |
| 2 | Metadata | Seeded pages carry the needed Applies-to records | | | | |
| 3 | Included / excluded ids | Included: general, Toast, Mews, QB, Toast/Mews, Mews/QB, workflow. Excluded: direct Toast/QB guide | | | | |
| 4 | Reranker results | Eligible-only; no excluded page reintroduced | | | | |
| 5 | Answers | Answers by walking the two real connections / the workflow, naming each system; direct Toast/QB guide absent | | | | |
| 6 | Citations | slot badges as above; both connections + workflow → "For your integration" | | | | |
| 7 | Further retrieval | If a 2nd read is needed to stitch the workflow, it must stay within the two-read cap; no excluded page | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

### Case 7 — Cross-match guard: two unrelated connections must not cross-match (§D.9 example 5)

- **How to reach this context:** a property whose real connections are **Toast↔Opera Cloud** and
  **Mews↔QuickBooks**, with **no** Toast↔Mews connection. **GAP (transcribed verbatim):** this
  **cannot be expressed by the launch slots-only token or by any standalone preset** — it needs two
  PMS products and real connection records, and Opera Cloud as a PMS is off the launch allowlist
  (would hide Obi). For Phase A, treat this example as validated by the automated reproduction
  (`test_worked_examples_db.py::test_rt2_example5_two_connections_never_cross_match_toast_mews`) and
  re-run it live only when §D.3/§D.4 real-connection context is available in the standalone env.
- **Question:** "Why are Toast room charges missing in Mews?" (the Toast/Mews question this property
  must NOT get Toast/Mews answers for).
- **Expected included:** **general**, **Toast/Opera Cloud connection**, **Mews/QuickBooks
  connection**. **Excluded:** every Toast/Mews connection page (both directions), the three-system
  workflow (needs a Toast/Mews connection), bare Toast and bare Mews software guides (neither a
  filled slot).
- **Expected citations + badges:** general → "General guide"; the two real connection pages → "For
  your integration" (`pair`). **No Toast/Mews `pair` badge may ever appear.**

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | **Not preset-expressible** — see gap. Reach via real-connection context or the automated DB test | | | | |
| 2 | Metadata | Pages carry Toast/Opera Cloud + Mews/QuickBooks connection records; no Toast/Mews record | | | | |
| 3 | Included / excluded ids | Included: general, Toast/Opera Cloud, Mews/QB. Excluded: all Toast/Mews (both directions), workflow, bare Toast, bare Mews | | | | |
| 4 | Reranker results | Eligible-only; no Toast/Mews page reintroduced | | | | |
| 5 | Answers | Answers only from the two real connections + general; must not present Toast/Mews room-charge guidance. **Fails loudest if cross-matching regresses** | | | | |
| 6 | Citations | general→"General guide"; two real connections→"For your integration"; no Toast/Mews `pair` badge | | | | |
| 7 | Further retrieval | ≤ 2 reads; same eligibility; no Toast/Mews page pulled | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

### Case 8 — Shared pages vs applicability (sharing is a separate axis)

- **How to reach this context:** preset **`pms-to-accounting`** (Mews + QuickBooks). **Requires
  corpus setup** (transcribed gap): seed two pages shared to the customer's scope by provider label
  — one with a **general** Applies-to record (or no record = today's label-only default), and one
  whose Applies-to record targets a **different** connection the customer does not have (e.g. a
  Toast/Mews room-charge page shared into the scope).
- **Question:** any Mews/QuickBooks question from Case 4.
- **Expected included:** the shared **general** page (sharing + general applicability both pass).
  **Excluded:** the shared **Toast/Mews** page (shared, but applicability does not match this
  customer's connections).
- **Expected citations + badges:** the general shared page → "General guide" (or no badge if it is
  a label-only page with no attribution); the Toast/Mews shared page must not be cited at all.

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Preset `pms-to-accounting`; marker shown; Obi visible | | | | |
| 2 | Metadata | **Corpus setup required:** two shared pages with the specific labels + Applies-to records above | | | | |
| 3 | Included / excluded ids | Included: shared general page. Excluded: shared Toast/Mews page | | | | |
| 4 | Reranker results | Eligible-only; inapplicable shared page not reintroduced | | | | |
| 5 | Answers | Sharing never widens relevance; the inapplicable shared page stays out of the answer | | | | |
| 6 | Citations | shared general → "General guide" (or no badge if label-only); Toast/Mews shared page not cited | | | | |
| 7 | Further retrieval | ≤ 2 reads; same eligibility; no excluded page | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

### Case 9 — Unknown configuration: serve general + ask, never broaden

- **How to reach this context:** **9a (one filled slot):** preset **`pos-to-pms`** then ask an
  *accounting* question (no accounting slot); or **No preset** and ask a connection question.
  **9b (hidden, config-only):** a context whose filled PMS slot is **Opera Cloud** (real catalog
  product, off the launch allowlist). **GAP (transcribed verbatim):** no standalone preset expresses
  9b; it is only reachable with a crafted token exercising the backend gate, so **9b is a
  configuration-step check, not a chat check.**
- **Questions:** 9a — "Why are my invoices missing in QuickBooks?" to a context with no accounting
  slot. 9b — attempt to open a session for the Opera-Cloud-PMS context.
- **Expected included (9a):** general + the filled slot's own guidance. **Excluded (9a):** every
  accounting / connection page the missing slot would unlock.
- **Expected citations + badges (9a):** only "General guide" and the filled-slot badge; no
  accounting/pair badge.

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | 9a: one-slot context, Obi visible. 9b: Opera-Cloud-PMS context — **Obi hidden / session refused** (filled off-allowlist slot); backend gate refuses (frontend hiding is UX, not the boundary) | | | | |
| 2 | Metadata | Seeded pages carry the needed Applies-to records | | | | |
| 3 | Included / excluded ids | 9a: Included general + filled slot; Excluded every accounting/connection page the missing slot would unlock | | | | |
| 4 | Reranker results | Eligible-only; no excluded page reintroduced | | | | |
| 5 | Answers | 9a: answers the general part and **asks for the missing configuration**; never invents the missing slot. 9b: session refused. Unknown/non-catalog slot values **fail closed — 400 before any search** (§D.11) — verify a malformed/unknown scope is rejected pre-search | | | | |
| 6 | Citations | 9a: only "General guide" + the filled-slot badge; no accounting/pair badge | | | | |
| 7 | Further retrieval | ≤ 2 reads; same eligibility; no excluded page | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

### Case 10 — Metadata update invalidates stale eligibility

- **How to reach this context:** preset **`pms-to-accounting`** (Mews + QuickBooks). **Requires a
  real page + a sync pass** (transcribed gap) — this is the one case that exercises ingestion, not
  just retrieval.
- **Procedure / questions:** (1) Seed a page with a **Mews/Xero** Applies-to record — confirm it is
  **excluded** for this customer (Case 4 logic). (2) Edit the page's Applies-to record to
  **Mews/QuickBooks** and re-sync. (3) Ask the Case-4 question again.
- **Expected included/excluded:** after the edit + sync, the page is now **included** (matches the
  real Mews/QuickBooks connection) and attributed `pair`; before the edit it is absent. Conversely,
  editing a matching page to a non-matching record + re-sync must **drop** it (no stale searchable
  chunk).
- **Expected citations + badges:** after the edit the page cites with badge "For your integration"
  (`pair`); before the edit it is absent.

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Preset `pms-to-accounting`; marker shown; Obi visible | | | | |
| 2 | Metadata | **Apply the edit + re-sync:** start Mews/Xero (excluded) → edit to Mews/QuickBooks → re-sync | | | | |
| 3 | Included / excluded ids | Before edit: page excluded. After edit+sync: page included; and a matching→non-matching edit drops it (no stale chunk) | | | | |
| 4 | Reranker results | Eligible-only; no stale chunk reintroduced | | | | |
| 5 | Answers | Eligibility tracks current metadata; no stale chunk survives a metadata change | | | | |
| 6 | Citations | After edit: badge "For your integration" (`pair`); before edit: absent | | | | |
| 7 | Further retrieval | ≤ 2 reads; same eligibility; no excluded page | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

---

## Integration cases — directed-connection token path (11–18)

Cases 11–18 validate the **token boundary** a real Base / Data Hub session rides on: signature,
issuer, audience, expiry, directed routing, customer switch, embed origin, eligibility. Each is
recorded **twice** — once on the local harness (runs now) and once against each partner's staging
(when it exists). A local PASS never stands in for a partner-staging PASS; keep the legs separate.
Expected results derive from the token claim schema (`packages/contracts/src/token-claims.json`),
the verification order (`token_verifier.py:146-217`), the gate (`auth_context.py:173-230`),
ADR-directed-source-target-routing-labels, the partner contract (`phase-9-partner-replies.md`), and owner decision round 4 (§D.18).

For each integration case: the **seven-step evidence table** records one run; the **per-environment
table** records the local/Base/Data Hub legs separately.

### Case 11 — A valid directed token routes to exactly its connection

- **How to reach this context:** local harness `/test-hosts/toast` (`toast → mews`,
  `business_id: B-3075`), `?form=directed`. Seed a corpus with pages labelled `obi-general`,
  `toast-general`, `mews-general`, `toast-to-pms`, plus at least one `mews-to-pos` and one unrelated
  connection page. Connection under test: `toast → mews`.
- **Action / question:** open Obi, ask "Why are Toast room charges missing in Mews?"
- **Expected:** gate accepts the token; routing labels are exactly `[obi-general, toast-general,
  mews-general, toast-to-pms]` (`product_catalog.build_labels`); answer cites only pages carrying
  one of those labels; no `mews-to-pos` or unrelated-connection page appears. If the connection's
  box has **no** pages, Obi refuses with a reason (content-gated, never-bend rule 7), not a
  wrong-connection answer.

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Network / trace / console ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | `/test-hosts/toast`, `?form=directed`, `toast → mews`, `business_id: B-3075`; gate accepts token | | | | |
| 2 | Metadata | Corpus labelled obi-general, toast-general, mews-general, toast-to-pms, + ≥1 mews-to-pos + 1 unrelated | | | | |
| 3 | Included / excluded ids | Routing labels exactly `[obi-general, toast-general, mews-general, toast-to-pms]`; no mews-to-pos/unrelated | | | | |
| 4 | Reranker results | Eligible-only; no excluded-label page reintroduced | | | | |
| 5 | Answers | Answers only from the connection's pages; empty box → cited refusal, not a wrong-connection answer | | | | |
| 6 | Citations | All citations map to eligible (labelled) pages | | | | |
| 7 | Further retrieval | ≤ 2 reads; same eligibility; no excluded-label page | | | | |

**Per-environment capture (record separately; local PASS ≠ partner-staging PASS):**

| Aspect | Local harness | Base (staging) | Data Hub (staging) |
|---|---|---|---|
| Status / result | | | |
| Routing labels observed | | | |
| Behaviour / citations observed | | | |
| Network / trace / console ref | | | |
| PASS / FAIL / N/A | | | |

**Case verdict (per env):** Local ☐ PASS ☐ FAIL · Base ☐ PASS ☐ FAIL ☐ N/A · DataHub ☐ PASS ☐ FAIL ☐ N/A

### Case 12 — Token integrity: bad signature, unknown key, expired, wrong audience, wrong issuer

- **How to reach this context:** local harness; mint a valid directed token, then produce five
  variants. Connection under test: token verification (`token_verifier.py` collapses all failures
  to `TokenError`; `router.py:290-291`).
- **Action / variants (each a row below):** (1) tampered signature → 401; (2) unknown `kid` → 401;
  (3) expired (`exp` past the 60 s leeway; confirm 30 s past `exp` still refused) → 401; (4) wrong
  `aud` (not `"obi"`) → 401; (5) unknown `iss` (not in `platforms.json`) → 401.
- **Expected:** every variant returns a bare **401**, no search, no answer, no `trace_id`; the
  widget surfaces its generic error.

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Network / trace / console ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Local harness; valid directed token minted, five variants produced | | | | |
| 2 | Metadata | (n/a — fails before search) | | | | |
| 3 | Included / excluded ids | No search runs; no candidate set | | | | |
| 4 | Reranker results | (n/a — no search) | | | | |
| 5 | Answers | (1) tampered sig → 401; (2) unknown kid → 401; (3) expired → 401 (30 s past exp still refused); (4) wrong aud → 401; (5) unknown iss → 401. No answer | | | | |
| 6 | Citations | No citations; no `trace_id` issued | | | | |
| 7 | Further retrieval | None; widget shows generic error, not an answer | | | | |

**Per-environment capture (record separately):**

| Aspect | Local harness | Base (staging) | Data Hub (staging) |
|---|---|---|---|
| Status per variant (sig / kid / exp / aud / iss) | | | |
| trace_id issued? (expect: no) | | | |
| Widget behaviour observed | | | |
| Network / console ref | | | |
| PASS / FAIL / N/A | | | |

**Case verdict (per env):** Local ☐ PASS ☐ FAIL · Base ☐ PASS ☐ FAIL ☐ N/A · DataHub ☐ PASS ☐ FAIL ☐ N/A

### Case 13 — Direction is primary: source→target ≠ target→source

- **How to reach this context:** `/test-hosts/connection-switch` (TOKEN_A `toast → mews`, TOKEN_B
  `opera-cloud → toast`), or mint `toast → mews` then `mews → toast`. Connection under test:
  directionality + scope-change restart (ADR-directed-source-target-routing-labels; `answer_service._resolve_directed_routing`).
- **Action:** ask a question under direction A; note the labels; switch to direction B mid-session.
- **Expected:** A's labels include `toast-to-pms`; B's labels flip (`mews`/`opera-cloud` general +
  the other direction's `{source}-to-{target.kind}`); the switch **restarts the thread** (messages
  cleared, new `conversationId`); no A answer carries into B.

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Network / trace / console ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | `/test-hosts/connection-switch` (A `toast → mews`, B `opera-cloud → toast`) | | | | |
| 2 | Metadata | Corpus carries pages for both directions' labels | | | | |
| 3 | Included / excluded ids | A labels include `toast-to-pms`; B labels flip to the other direction's set | | | | |
| 4 | Reranker results | Eligible-only per direction; A's eligible set not reused in B | | | | |
| 5 | Answers | Switch restarts the thread (messages cleared, new conversationId); no A answer carries into B | | | | |
| 6 | Citations | Each answer cites only its own direction's labelled pages | | | | |
| 7 | Further retrieval | Two trace rows with different label sets; widget thread visibly resets on swap | | | | |

**Per-environment capture (record separately):**

| Aspect | Local harness | Base (staging) | Data Hub (staging) |
|---|---|---|---|
| A labels / B labels observed | | | |
| Thread reset on swap? | | | |
| Two distinct trace rows? | | | |
| Network / trace / console ref | | | |
| PASS / FAIL / N/A | | | |

**Case verdict (per env):** Local ☐ PASS ☐ FAIL · Base ☐ PASS ☐ FAIL ☐ N/A · DataHub ☐ PASS ☐ FAIL ☐ N/A

### Case 14 — Compound or unknown system is refused before any search

- **How to reach this context:** local harness; mint a directed token with
  `source_system: "toast-opera"` (compound), then one with `target_system: "not-a-system"`.
  Connection under test: the pre-search refusal gate (`auth_context.py:202-207` → `router.py:287-289`).
- **Action:** open Obi.
- **Expected:** each is **400** ("unknown integration value") *before* any retrieval. The compound
  resolves to nothing (`legacy_aliases` is `{}`); the unknown id resolves to nothing. No search
  runs, no answer, no `trace_id`.

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Network / trace / console ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Local harness; token with `source_system: "toast-opera"`, then `target_system: "not-a-system"` | | | | |
| 2 | Metadata | (n/a — fails before search) | | | | |
| 3 | Included / excluded ids | No search; no candidate set | | | | |
| 4 | Reranker results | (n/a) | | | | |
| 5 | Answers | Each → **400** "unknown integration value" before retrieval; compound and unknown both resolve to nothing; no answer | | | | |
| 6 | Citations | No citations; no `trace_id` | | | | |
| 7 | Further retrieval | None | | | | |

**Per-environment capture (record separately):**

| Aspect | Local harness | Base (staging) | Data Hub (staging) |
|---|---|---|---|
| Status (compound / unknown) — expect 400 | | | |
| Search ran? (expect: no) | | | |
| trace_id issued? (expect: no) | | | |
| Network / console ref | | | |
| PASS / FAIL / N/A | | | |

**Case verdict (per env):** Local ☐ PASS ☐ FAIL · Base ☐ PASS ☐ FAIL ☐ N/A · DataHub ☐ PASS ☐ FAIL ☐ N/A

### Case 15 — Vend rights and inactive registration

- **How to reach this context:** local harness with a test issuer whose `allowed_integrations` is,
  say, `["toast"]`. Connection under test: vend-rights (CIP-A1, `auth_context.py:209-217`) and
  inactive-platform denial (`auth_context.py:240-242`).
- **Action / expected (each a row):** (1) mint a token asserting a system **not** in the issuer's
  vend set (e.g. `target_system: "xero"` when only `toast` is vended) → **401** (vend-rights
  violation). (2) point the harness at an issuer whose registry entry is `active: false` → the token
  **verifies** (step 1 uses `by_issuer`) but the gate denies with `InactivePlatformError` → **401**
  (the backstop that keeps an unverified partner inert until the owner flips `active: true`).

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Network / trace / console ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Local harness; issuer `allowed_integrations: ["toast"]`; also an `active: false` issuer | | | | |
| 2 | Metadata | (n/a — denied before/at gate) | | | | |
| 3 | Included / excluded ids | No search for either variant | | | | |
| 4 | Reranker results | (n/a) | | | | |
| 5 | Answers | (1) asserting non-vended system (e.g. `xero`) → **401** (vend-rights). (2) `active: false` issuer → token verifies but gate denies `InactivePlatformError` → **401**. No answer either | | | | |
| 6 | Citations | No citations | | | | |
| 7 | Further retrieval | None | | | | |

**Per-environment capture (record separately):**

| Aspect | Local harness | Base (staging) | Data Hub (staging) |
|---|---|---|---|
| Status (vend violation / inactive) — expect 401 | | | |
| Token verified but gate denied? (inactive case) | | | |
| Network / console ref | | | |
| PASS / FAIL / N/A | | | |

**Case verdict (per env):** Local ☐ PASS ☐ FAIL · Base ☐ PASS ☐ FAIL ☐ N/A · DataHub ☐ PASS ☐ FAIL ☐ N/A

### Case 16 — Customer / connection switch without logging out (Marien's requirement)

- **How to reach this context:** `/test-hosts/multi` (switches the signed-in identity / re-points
  `Obi.init`), or a page that posts a replacement `obi:token` with a different `business_id`.
  Connection under test: per-customer session isolation keyed on `(sha256(sub), company_id)`.
- **Action:** ask a question as customer A (`business_id: B-A`); without reloading, switch to
  customer B (`business_id: B-B`) and ask again.
- **Expected:** on the switch, Obi **resets the thread** (scope change on the changed `business_id`
  → `restart()`); B's answer never references A's conversation; the backend session row is keyed on
  `(sha256(sub), company_id)`, so B gets its own session. **Record the host trigger used** (re-init
  vs token-replacement) — this is the behaviour to agree with Marien.

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Network / trace / console ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | `/test-hosts/multi` or token-replacement; customer A (`B-A`) then customer B (`B-B`), no reload | | | | |
| 2 | Metadata | Corpus serves both customers' scopes | | | | |
| 3 | Included / excluded ids | Two trace rows under two `company_id`s; B's candidate set is B's own | | | | |
| 4 | Reranker results | Eligible-only per customer; no A page in B | | | | |
| 5 | Answers | Thread resets on the switch; B's answer never references A's conversation | | | | |
| 6 | Citations | B cites only B's scope | | | | |
| 7 | Further retrieval | No A content in B's answer. **Record the host trigger used** (re-init vs token-replacement) | | | | |

**Per-environment capture (record separately):**

| Aspect | Local harness | Base (staging) | Data Hub (staging) |
|---|---|---|---|
| Thread cleared on switch? | | | |
| Two trace rows under two company_ids? | | | |
| Host trigger used (re-init / token-replacement) | | | |
| Network / trace / console ref | | | |
| PASS / FAIL / N/A | | | |

**Case verdict (per env):** Local ☐ PASS ☐ FAIL · Base ☐ PASS ☐ FAIL ☐ N/A · DataHub ☐ PASS ☐ FAIL ☐ N/A

### Case 17 — Embed-origin lock (frame-ancestors)

- **How to reach this context:** a registered test origin and an unregistered one. Connection under
  test: the `/embed` `frame-ancestors` CSP (`middleware.ts:51-56` from `activeDomains()`).
- **Action:** embed the `/obi.js` snippet on each and open the chat.
- **Expected:** the widget iframe loads and functions on the **registered** origin; on the
  **unregistered** origin the browser blocks the frame (CSP `frame-ancestors` violation in the
  console) and the chat does not load. The response CSP header lists only `active: true` platforms'
  domains. (Only the temporary `obi-test` origin is active today, so a partner's origin must be
  added to its `active` entry before its page can embed.)

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Network / trace / console ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | `/obi.js` embedded on a registered origin and an unregistered origin | | | | |
| 2 | Metadata | (n/a — embed-boundary check) | | | | |
| 3 | Included / excluded ids | CSP header lists only `active: true` platform domains | | | | |
| 4 | Reranker results | (n/a) | | | | |
| 5 | Answers | Registered origin: widget loads and functions. Unregistered origin: browser blocks the frame (CSP `frame-ancestors` violation), chat does not load | | | | |
| 6 | Citations | (n/a) | | | | |
| 7 | Further retrieval | Console shows the CSP block on the unregistered origin | | | | |

**Per-environment capture (record separately):**

| Aspect | Local harness | Base (staging) | Data Hub (staging) |
|---|---|---|---|
| Loads on registered origin? | | | |
| Blocked on unregistered origin (CSP violation)? | | | |
| CSP header domains observed | | | |
| Network / console ref | | | |
| PASS / FAIL / N/A | | | |

**Case verdict (per env):** Local ☐ PASS ☐ FAIL · Base ☐ PASS ☐ FAIL ☐ N/A · DataHub ☐ PASS ☐ FAIL ☐ N/A

### Case 18 — Source-enablement widget eligibility (live gate — §D.18 item 4, ADR-source-system-decides-widget-eligibility)

- **How to reach this context:** a directed token whose **source** is not a supported system (e.g.
  `source_system: "PEP PMS"`, `target_system: "NetSuite"`). Only the source decides whether Obi
  shows (`enabled_sources` = `mews`, `toast`, `opera-cloud`); the target is never checked. Full case:
  `phase-a-validation-cases.md` Case 18.
- **Action:** open Obi.
- **Expected:** the widget is **hidden**; `GET /chat/visibility` → `{"visible":false,"reason":"source_not_enabled"}`;
  `POST /chat` → **403** `{"error":"integration not available","reason":"source_not_enabled"}` (no
  product id in the body).
- **Control:** an enabled source with any target (`toast → mews`, `toast → NetSuite`) is visible and
  served; the unknown target routes on `[obi-general, toast-general]`.

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Network / trace / console ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration | Directed token whose source is not a supported system | | | | |
| 2 | Metadata | No session starts for the unsupported source | | | | |
| 3 | Included / excluded ids | None — refused before any search | | | | |
| 4 | Reranker results | None | | | | |
| 5 | Answers | Widget hidden; `POST /chat` 403 `source_not_enabled`. Control: enabled source served for any target | | | | |
| 6 | Citations | None for the refused case | | | | |
| 7 | Further retrieval | None | | | | |

**Per-environment capture (record separately):**

| Aspect | Local harness | Base (staging) | Data Hub (staging) |
|---|---|---|---|
| Visibility probe body | | | |
| `POST /chat` status + body | | | |
| Launcher mounted? | | | |
| Network / trace / console ref | | | |
| PASS / FAIL / N/A | | | |

**Case verdict (per env):** Local ☐ PASS ☐ FAIL ☐ N/A · Base ☐ PASS ☐ FAIL ☐ N/A · DataHub ☐ PASS ☐ FAIL ☐ N/A

---

## Honest gaps carried from the cases doc (do not lose these)

1. **Case 7 (§D.9 example 5) is not exercisable through the standalone preset selector.** Needs real
   connection records; Opera Cloud as PMS is off the launch allowlist. Reproduced by the automated DB
   test today; live validation waits on §D.3/§D.4 real-connection context. Recorded as a gap, not a
   pass.
2. **Case 9b (out-of-allowlist / hidden) is a backend-gate check, not a chat check.** No preset
   expresses an off-allowlist filled slot; verifying hiding/refusal needs a crafted token against the
   gate.
3. **Cases 8 and 10 need corpus setup** (real Confluence pages with specific provider labels and
   "Applies to" records); Case 10 additionally needs an ingestion/sync pass. Cases 1–7, 9a run
   against a seeded pgvector corpus.
4. **The nine real Base pages are still unlabelled** (§D.16 item 6) and not indexed, so Phase A runs
   against seeded/preset corpora, not the real Base corpus, until the owner re-labels.
5. **Inspection surface** for included/excluded ids, reranker order, and further retrieval is the
   retrieval trace keyed by `trace_id`; read the trace row directly if no viewer exists. The inclusion
   reason per cited source is independently visible on the widget as the attribution badge.
6. **Badge labels** transcribed here are the current widget strings (`message-bubble.tsx`); if the UI
   copy changes, update the expected badge text — the enum (`general|pos|pms|accounting|pair`) is the
   design-of-record oracle.
7. **Integration cases 11–18 prove our side on the local harness now; the real end-to-end leg waits on
   partner staging** (current per-partner state: `partner-facts.md`). Record the
   two legs separately; never call a case fully passed on the local leg alone.
8. **Case 18 is a live gate on the source** (ADR-source-system-decides-widget-eligibility, 2026-10-20).
   An unsupported source must hide the widget and be refused 403 `source_not_enabled`; the target is
   never checked. A disabled source that mounts the widget or is served fails the case.

---

Recording evidence here does **not** by itself flip the design panel or write the ledger — those are
separate, owner-gated steps. When all non-deferred cases pass with evidence, file this sheet with the
step (as the 4.4 browser checks were filed); only then may the owner tick 8.5.2.
