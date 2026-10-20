# Phase A · human validation cases (action-plan substep 8.5.2)

**Status: prepared, not run.** This document is the owner's procedure for Phase A. The agent
**prepares the cases and records the evidence**; a human exercises the finished behaviour and
confirms it. Nothing here is a claim that 8.5.2 is done.

Phase A is the human check that closes Step 5 (plan.md §D.10). A person drives the real widget
against known setups with independently-derived right answers, inspects what Obi included and
excluded and why, and only then is the behaviour allowed to count as working. Per design panel
`mi-validate` and §D.10: **never label a manual check as passed without actual human evidence,
recorded.** Phase B (the agent-built automated suite, roadmap Step 6) starts only after a human
confirms Phase A — and its expectations come from the cases below, never from reading the code
under test.

## Where the expected results come from (and where they do not)

Every "expected" line in every case is derived from the **design**, not from the implementation:

- The include/exclude categories come from **plan.md §D.9** (the five concrete examples) and the
  eligibility rules in **§D.4 / §D.5**.
- The slot → visibility → eligibility logic comes from the **context contract**
  (`legacy-three-slot-context-contract.md` §4–§6) and the owner decisions **§D.13 / §D.16**.
- The per-slot attribution vocabulary (`general | pos | pms | accounting | pair`) comes from
  **§D.13 keuze 3** and `legacy-three-slot-context-contract.md` §6.
- The flow types come from **§D.2**; the presets from `knowledge-base/config/standalone_presets.json`.

The worked-example test `backend/app/features/retrieval/tests/test_worked_examples_db.py` encodes
the same §D.9 scenarios at the database level. It is cited here only to pin the **page-intent** of
each example (which category each seeded page represents). The human-validation expectations are
read from the design, not reverse-engineered from that test or from any other code.

## How to run

Phase A runs against the **standalone / test environment**, because a real authenticated
production chat still depends on the Base / Data Hub integration that is deliberately scheduled
**last** (§D.16 item 5 — after Phase A). Two ways to reach the finished behaviour:

- **Local (recommended for most cases).** `make up` (local pgvector on :5434), `make migrate`,
  seed a corpus whose pages carry the "Applies to" records the case needs (see each case), then
  `make web-dev` and open the app. The floating chat widget is mounted globally; in a
  local/dev/test environment it shows the **"Simulated test context — not a real customer
  configuration"** bar with a **preset selector**
  (`frontend/src/features/chat/ui/standalone-preset-bar.tsx`, reading the backend-validated list in
  `standalone_presets.json`). Pick the preset named in the case. Switching a preset starts a fresh
  chat, so two simulated contexts never share a conversation.
- **Against the deployed origin** (`https://obi-web-production.up.railway.app`) using the local
  test-host harness (`frontend/src/app/(site)/test-hosts/*`). Same widget, same contract; still not
  a real Base/Data Hub session.

What to inspect, per answer:

- **Citations + attribution badges** render on each answer in the widget. The badge text maps to
  the attribution enum (`message-bubble.tsx`): `general` → "General guide", `pos` → "For your POS",
  `pms` → "For your PMS", `accounting` → "For your accounting", `pair` → "For your integration".
  This is the inspectable inclusion reason per cited source.
- **Included / excluded page and chunk ids, reranker ordering, and any further retrieval** are on
  the **retrieval trace** for the request. The chat response carries a `trace_id`
  (`rag_agent/schemas.py`), which keys the trace row written by
  `retrieval/infrastructure/trace_repo.py`. Inspect that row (DB / logs) for the candidate set, the
  reranked order, and whether a second read happened. If a one-click trace viewer is not available
  in your environment, read the trace row by `trace_id` directly — note that in the evidence table.

## The order a human follows for every case (§D.10, verbatim sequence)

Walk each case through these seven steps **in this exact order**; the evidence table per case has
one row per step:

1. **Configuration** — set the context (the named preset / slots). Confirm the widget shows the
   simulated-context marker and the right preset; confirm Obi is **visible** (or correctly hidden,
   where the case expects hiding).
2. **Metadata** — confirm the seeded pages carry the "Applies to" records the case lists (and, for
   the metadata-update case, apply the edit and re-sync).
3. **Included / excluded page and chunk ids** — ask the question; from the trace, record which page
   ids were eligible and which were excluded. Compare against the case's expected include / exclude
   lists.
4. **Reranker results** — confirm the reranker only re-ordered **eligible** evidence and never
   reintroduced an excluded page (§D.6).
5. **Answers** — confirm the answer behaviour matches (answers from applicable evidence, or
   refuses / asks for missing configuration where the case expects that; never invents a
   connection).
6. **Citations** — confirm every sentence cites a real included source and every included source is
   backed; confirm the per-slot attribution badge on each citation matches the expected reason.
7. **Further retrieval** — if a second read happened, confirm it stayed within the two-read cap
   (never-bend rule 8) and passed the same backend eligibility (§D.7); confirm it never pulled an
   excluded page.

Record **PASS/FAIL per step with evidence**. If a case fails, fix the problem, re-run the whole
case, and record both the first failure and the re-run (fix-and-repeat is required by §D.10 and
panel `mi-validate`).

---

## The cases

Presets referenced below are the exact ids in `standalone_presets.json`. "No preset" is the
selector's **"No preset (general only)"** option. Expected attribution badges are given in the
widget's label form.

### Case 1 — General guidance baseline (configuration + general)

Covers: **general guidance**, the configuration step, the visibility rule for an all-empty context.

- **(a) Context:** No preset (general only) — company with all three slots empty.
- **(b) Questions:** A general question that general guidance answers (e.g. "What is Obi?" /
  "How do I get started?"); then a connection-specific question with no matching slot (e.g. "Why
  are my Mews invoices missing in QuickBooks?").
- **(c) Expected included vs excluded:** Included — only **general** pages. Excluded — every
  software, connection, and workflow page (no slot is filled, so nothing slot- or pair-specific is
  eligible). Derived from `legacy-three-slot-context-contract.md` §5 (general always; slot/pair guides only for
  filled slots / real pairs).
- **(d) Expected citations + attribution:** Every citation badge reads **"General guide"**
  (`general`). No `pos`/`pms`/`accounting`/`pair` badges appear.
- **(e) Expected behaviour:** The general question is **answered** from general guidance. The
  connection-specific question is **not answered with connection instructions**: Obi serves the
  applicable general guidance and **asks for the missing configuration** rather than broadening to
  every Mews/QuickBooks page (§D.4). Derived from §D.4 (serve general + ask; never broaden).

### Case 2 — POS → PMS, two systems (§D.9 example 2)

Covers: **flow type POS→PMS**, two-system context, shared single connection (both directions).

- **(a) Context:** preset **`pos-to-pms`** — slots `pos: toast`, `pms: mews`, `accounting: null`.
- **(b) Question:** "Why are Toast room charges missing in Mews?"
- **(c) Expected included vs excluded:** Included — **general**, **Toast** (software), **Mews**
  (software), and the **Toast/Mews connection** guidance (both the POS→PMS room-charge direction and
  the PMS→POS guest-info direction — two directions of the one connection). Excluded — all
  accounting guidance (QuickBooks, Xero), the Mews/QuickBooks and direct Toast/QuickBooks pair
  guides, Mews/Xero, and any Opera Cloud guidance. Derived from §D.9 example 2 + §D.2 (one
  connection, two directions) + `legacy-three-slot-context-contract.md` §5.1.
- **(d) Expected citations + attribution:** general → **"General guide"**; Toast page → **"For your
  POS"** (`pos`); Mews page → **"For your PMS"** (`pms`); Toast/Mews connection page(s) → **"For your
  integration"** (`pair`).
- **(e) Expected behaviour:** Answers from the POS→PMS connection evidence, naming which system each
  fact comes from (§D.7). No accounting content appears.

### Case 3 — PMS → POS, two systems (§D.9 example 3)

Covers: **flow type PMS→POS**; confirms the two presets that share slots behave identically on
eligibility and differ only by display label.

- **(a) Context:** preset **`pms-to-pos`** — slots `pos: toast`, `pms: mews`, `accounting: null`
  (same slots as Case 2; the `flow_type` label is the only difference).
- **(b) Question:** "Why is Mews guest information unavailable in Toast?"
- **(c) Expected included vs excluded:** Included — **general**, **Toast**, **Mews**, and the
  **Toast/Mews connection** guidance (the enabled PMS→POS guest-info direction, plus the POS→PMS
  direction of the same connection). Excluded — Mews/Xero and Opera Cloud guidance; all accounting
  pairs. Derived from §D.9 example 3 + §D.2.
- **(d) Expected citations + attribution:** general → "General guide"; Toast → "For your POS"; Mews →
  "For your PMS"; the Toast/Mews connection page(s) → "For your integration" (`pair`).
- **(e) Expected behaviour:** Answers from the enabled PMS→POS direction. **Cross-check against Case
  2:** the same page ids are eligible as in Case 2 (eligibility is slot-driven, not label-driven) —
  record this equivalence as evidence.

### Case 4 — PMS → Accounting, two systems (§D.9 example 1)

Covers: **flow type PMS→Accounting**, two-system context; the headline §D.9 example-1 exclude list.

- **(a) Context:** preset **`pms-to-accounting`** — slots `pos: null`, `pms: mews`,
  `accounting: quickbooks-online`.
- **(b) Question:** "Why are my Mews invoices missing in QuickBooks?"
- **(c) Expected included vs excluded:** Included — **general**, **Mews** (software), **QuickBooks
  Online** (the customer's accounting guidance), and the **Mews/QuickBooks connection** guidance.
  Excluded — **Mews/Xero** guidance, unrelated **Toast room-charge** (Toast/Mews) instructions, bare
  **Xero** and bare **Toast** guidance (no POS slot). Derived from §D.9 example 1 (explicit
  include/exclude) + §D.4.
- **(d) Expected citations + attribution:** general → "General guide"; Mews → "For your PMS"
  (`pms`); QuickBooks → "For your accounting" (`accounting`); Mews/QuickBooks connection → "For your
  integration" (`pair`).
- **(e) Expected behaviour:** Answers from the Mews→QuickBooks accounting evidence; no Xero content;
  no room-charge content.

### Case 5 — POS → Accounting, two systems + the Toast→QuickBooks honesty clause

Covers: **flow type POS→Accounting**, and the §5.2 rule that a direct POS–Accounting pair is **not**
derivable from slots alone at launch.

- **(a) Context:** preset **`pos-to-accounting`** — slots `pos: toast`, `pms: null`,
  `accounting: quickbooks-online`.
- **(b) Question:** "Why aren't my Toast sales reaching QuickBooks?"
- **(c) Expected included vs excluded:** Included — **general**, **Toast** (software), **QuickBooks
  Online** (software/accounting). Excluded — the **direct Toast/QuickBooks connection** guide (the
  launch slots-only token cannot express a real POS→Accounting connection — §5.2), all Mews guidance,
  and any pair needing Mews. Derived from `legacy-three-slot-context-contract.md` §5.1–§5.2 (POS–Accounting not derived
  from slots; §D.2 "Toast + Mews + QuickBooks does not automatically have a direct
  Toast→QuickBooks connection").
- **(d) Expected citations + attribution:** general → "General guide"; Toast → "For your POS";
  QuickBooks → "For your accounting". **No `pair` badge should appear** (no eligible connection
  guide).
- **(e) Expected behaviour:** This is the honesty case. Obi answers from general + Toast + QuickBooks
  and, where the question truly needs the direct connection, **names the missing configuration and
  does not surface a Toast/QuickBooks connection guide or invent a connection** (§D.4, §5.2). Verify
  no Toast/QuickBooks pair page is included.

### Case 6 — Three systems: multiple connections + workflow binding (§D.9 example 4)

Covers: **three-system context**, **multiple connections**, **workflow bindings**, and the §D.9
example-4 exclude.

- **(a) Context:** preset **`three-system`** — slots `pos: toast`, `pms: mews`,
  `accounting: quickbooks-online`.
- **(b) Question:** "Why are restaurant charges not reaching QuickBooks?"
- **(c) Expected included vs excluded:** Included — **general**, **Toast**, **Mews**, **QuickBooks**
  (each slot guide), the **Toast/Mews connection**, the **Mews/QuickBooks connection**, and the
  **three-system Toast→Mews→QuickBooks workflow** guide (same-instance binding). Excluded — the
  **direct Toast/QuickBooks** guide (that connection does not exist — §D.9 example 4, §5.2). Derived
  from §D.9 example 4 + §D.4 (workflow must match the real connected path).
- **(d) Expected citations + attribution:** general → "General guide"; Toast → "For your POS"; Mews →
  "For your PMS"; QuickBooks → "For your accounting"; both connection pages and the workflow page →
  "For your integration" (`pair`).
- **(e) Expected behaviour:** Answers by walking the two real connections / the workflow, naming each
  system (§D.7). The direct Toast/QuickBooks guide must be absent. If Obi needs a second read to
  stitch the workflow, it must stay within the two-read cap (step 7).

### Case 7 — Cross-match guard: two unrelated connections must not cross-match (§D.9 example 5)

Covers: the headline **cross-matching regression guard** — a property with Toast/Opera Cloud **and**
Mews/QuickBooks must **not** qualify for Toast/Mews guidance just because Toast and Mews are both
present somewhere.

- **(a) Context:** a property whose real connections are **Toast↔Opera Cloud** and
  **Mews↔QuickBooks**, with **no** Toast↔Mews connection. **Note / gap:** this cannot be expressed by
  the launch slots-only token or by any standalone preset — it needs two PMS products and real
  connection records, and Opera Cloud as a PMS is off the launch allowlist (would hide Obi). See the
  gaps section. For Phase A, treat this example as validated by the automated reproduction
  (`test_worked_examples_db.py::test_rt2_example5_two_connections_never_cross_match_toast_mews`) and,
  when §D.3/§D.4 real-connection context is available in the standalone env, re-run it live.
- **(b) Question:** "Why are Toast room charges missing in Mews?" (the Toast/Mews question this
  property must NOT get Toast/Mews answers for).
- **(c) Expected included vs excluded:** Included — **general**, the **Toast/Opera Cloud connection**,
  the **Mews/QuickBooks connection**. Excluded — **every Toast/Mews connection page (both
  directions)**, the **three-system workflow** (needs a Toast/Mews connection), and the bare **Toast**
  and **Mews** software guides (neither is a filled slot). Derived from §D.9 example 5 + §D.4 (AND
  within a rule must match the **same** real connection; separate rules OR; never
  "both products exist somewhere").
- **(d) Expected citations + attribution:** general → "General guide"; the two real connection pages →
  "For your integration" (`pair`). No Toast/Mews `pair` badge may ever appear.
- **(e) Expected behaviour:** Obi answers only from the two real connections and general; it must not
  present Toast/Mews room-charge guidance. **This is the one case that fails loudest if cross-matching
  regresses.**

### Case 8 — Shared pages vs applicability (sharing is a separate axis)

Covers: **shared pages** — provider-sharing labels express sharing; applicability is an additional
relevance restriction on top (§D.3, §D.4).

- **(a) Context:** preset **`pms-to-accounting`** (Mews + QuickBooks). Seed two pages that are
  **shared** to the customer's scope by provider label: one with a **general** "Applies to" record
  (or no record = today's label-only default), and one whose "Applies to" record targets a
  **different** connection the customer does **not** have (e.g. a Toast/Mews room-charge page shared
  into the scope).
- **(b) Question:** any Mews/QuickBooks question from Case 4.
- **(c) Expected included vs excluded:** Included — the shared **general** page (sharing + general
  applicability both pass). Excluded — the shared **Toast/Mews** page (shared, but its applicability
  does not match this customer's connections). Derived from §D.4 ("provider labels continue to
  express sharing; applicability is an additional relevance restriction") and §D.11 (a page with no
  Applies-to record keeps label-only behaviour — the documented default, not a silent wildcard).
- **(d) Expected citations + attribution:** the general shared page cites with badge "General guide"
  (or no badge if it is a label-only page with no attribution); the Toast/Mews shared page must not be
  cited at all.
- **(e) Expected behaviour:** Sharing never widens relevance; an inapplicable shared page stays out of
  the answer. **Requires corpus setup** (two Confluence pages with specific labels + Applies-to
  records) — flag in the evidence table.

### Case 9 — Unknown configuration: serve general + ask, never broaden

Covers: **unknown configuration**, and the out-of-allowlist / hidden-visibility rule.

- **(a) Context (9a — one filled slot):** preset **`pms-to-accounting`** gives two slots; for the
  "missing config" behaviour, use a **one-slot** context — preset **`pos-to-pms`** then ask an
  *accounting* question the customer has no accounting slot for; or use **No preset** and ask a
  connection question. **(9b — hidden, config-only):** a context whose filled PMS slot is
  **Opera Cloud** (a real catalog product, off the launch allowlist). **Note / gap:** no standalone
  preset expresses this; it is only reachable with a crafted token exercising the backend gate, so 9b
  is a **configuration-step** check, not a chat check.
- **(b) Questions:** 9a — "Why are my invoices missing in QuickBooks?" to a context with no accounting
  slot. 9b — attempt to open a session for the Opera-Cloud-PMS context.
- **(c) Expected included vs excluded:** 9a — Included: general + the filled slot's own guidance;
  Excluded: every accounting / connection page the missing slot would unlock. Derived from §D.4 (serve
  general + ask; never broaden to every page that mentions the provider) and `legacy-three-slot-context-contract.md` §3.
- **(d) Expected citations + attribution:** 9a — only "General guide" and the filled-slot badge; no
  accounting/pair badge.
- **(e) Expected behaviour:** 9a — Obi **answers the general part and asks for the missing
  configuration** instead of giving accounting-connection instructions; it never invents the missing
  slot. 9b — **Obi is hidden / the session is refused** (a filled POS/PMS slot outside the allowlist
  hides Obi; the backend gate refuses too — the frontend hiding is UX, not the boundary). Derived from
  `legacy-three-slot-context-contract.md` §4 + §8.4, §D.13 item 3. Unknown (non-catalog) slot values keep **failing
  closed — 400 before any search** (§D.11); verify a malformed/unknown scope is rejected pre-search.

### Case 10 — Metadata update invalidates stale eligibility

Covers: **metadata updates** — an "Applies to" edit updates existing chunks and invalidates stale
eligibility (§D.3 storage/sync, riding the §D.0 restamp route).

- **(a) Context:** preset **`pms-to-accounting`** (Mews + QuickBooks).
- **(b) Procedure:** (1) Seed a page with a **Mews/Xero** "Applies to" record — confirm it is
  **excluded** for this customer (Case 4 logic). (2) Edit the page's "Applies to" record to
  **Mews/QuickBooks** and re-sync. (3) Ask the Case-4 question again.
- **(c) Expected included vs excluded:** After the edit + sync, the page is now **included** (it
  matches the real Mews/QuickBooks connection) and attributed `pair`. Conversely, editing a matching
  page to a non-matching record + re-sync must **drop** it (no stale searchable chunk). Derived from
  §D.3 ("define how a metadata edit updates existing chunks and invalidates stale eligibility") +
  §D.4.
- **(d) Expected citations + attribution:** after the edit, the page cites with badge "For your
  integration" (`pair`); before the edit it is absent.
- **(e) Expected behaviour:** Eligibility tracks the current metadata; no stale chunk survives a
  metadata change. **Requires a real page + a sync pass** — flag in the evidence table; this is the
  one case that exercises ingestion, not just retrieval.

---

## Integration cases — the directed-connection token path (added 2026-10-13, §D.18 item 7)

Cases 1–10 validate retrieval behaviour against seeded/preset corpora. Cases 11–18 validate the
**token boundary** that a real Base / Data Hub session rides on: signature, issuer, audience, expiry,
directed routing, customer switch, embed origin, and eligibility. They exercise the gate and the
widget, not the preset selector.

**Where expected results come from:** the token claim schema
(`packages/contracts/src/token-claims.json`), the verification order (`token_verifier.py:146-217`),
the gate (`auth_context.py:173-230`), ADR-directed-source-target-routing-labels (directed routing), the partner contract
(`directed-routing-partner-reply-drafts.md`), and owner decision round 4 (`plan.md` §D.18).

**How to run — two environments, recorded separately (never merged):**

- **Local harness (runs now).** The test-host pages (`frontend/src/app/test-hosts/*`) mint RS256
  directed tokens against `test-*.local` issuers (`platforms.local.json`) via
  `/api/test-hosts/[name]/obi-token?form=directed`. `/test-hosts/toast` sends `toast → mews`,
  `/test-hosts/opera-cloud` sends `opera-cloud → toast`, and `/test-hosts/connection-switch` drives a
  switch. Use these for Cases 11–18 today.
- **Partner staging (runs when a partner's issuer/JWKS/token endpoint exist).** Re-run every case
  against that partner's own keys, login session and selected customer, with the widget loading on
  their real staging origin. **A local-harness PASS does not count as a partner-staging PASS** —
  record each in its own column.

**Where to look:** the chat response carries `trace_id` (`rag_agent/schemas.py`); a refusal returns
an HTTP status (400/401) with no detail (`router.py:285-291`). Inspect the Network tab for the status
and the token request, the browser console for widget state, and the trace row for the routing labels
and the candidate/excluded sets.

### Case 11 — A valid directed token routes to exactly its connection

Covers: the happy path — a conforming `source → target` token is accepted and answers come only from
that connection's pages; an empty connection box refuses with a reason.

- **Setup:** local harness `/test-hosts/toast` (`toast → mews`, `business_id: B-3075`), `?form=directed`.
  Seed a corpus with pages labelled `obi-general`, `toast-general`, `mews-general`, `toast-to-pms`,
  plus at least one `mews-to-pos` and one unrelated connection page.
- **Action:** open Obi, ask "Why are Toast room charges missing in Mews?"
- **Expected:** the gate accepts the token; the request's routing labels are exactly
  `[obi-general, toast-general, mews-general, toast-to-pms]` (`product_catalog.build_labels`);
  the answer cites only pages carrying one of those labels; no `mews-to-pos` or unrelated-connection
  page appears. If the connection's box has **no** pages, Obi refuses with a reason (content-gated,
  never-bend rule 7), not a wrong-connection answer.
- **Verify:** trace row shows the four labels and the eligible/excluded sets; citations all map to
  eligible pages.

### Case 12 — Token integrity: bad signature, unknown key, expired, wrong audience, wrong issuer

Covers: every token-verification failure returns a bare **401** and no answer (`token_verifier.py`
collapses all failures to `TokenError`; `router.py:290-291`). Expiry stays enforced — the point
flagged for Jasper's expired sample.

- **Setup:** local harness; mint a valid directed token, then produce five variants.
- **Action + Expected (each a row):**
  1. **Tampered signature** (flip a payload byte, keep the signature) → **401**, no search, no answer.
  2. **Unknown `kid`** (sign with a key absent from the JWKS) → **401** (key resolution fails).
  3. **Expired** (`exp` in the past beyond the 60 s leeway) → **401**. Confirm a token 30 s past
     `exp` is still refused.
  4. **Wrong `aud`** (not `"obi"`) → **401**.
  5. **Unknown `iss`** (an issuer not in `platforms.json`) → **401**.
- **Verify:** Network tab shows 401 with no body detail for each; no `trace_id` is issued; the widget
  surfaces its generic error, not an answer.

### Case 13 — Direction is primary: source→target ≠ target→source

Covers: `toast → mews` and `mews → toast` are different connections and the swap resets the chat
(ADR-directed-source-target-routing-labels; `iframe-bridge` scope-change; `answer_service._resolve_directed_routing` re-start).

- **Setup:** `/test-hosts/connection-switch` (drives TOKEN_A `toast → mews`, TOKEN_B
  `opera-cloud → toast`), or mint `toast → mews` then `mews → toast`.
- **Action:** ask a question under direction A; note the labels; switch to direction B mid-session.
- **Expected:** A's labels include `toast-to-pms`; B's labels flip (`mews`/`opera-cloud` general +
  the other direction's `{source}-to-{target.kind}`); the switch **restarts the thread** (messages
  cleared, new `conversationId`); no answer from A carries into B.
- **Verify:** two trace rows with different label sets; the widget thread visibly resets on the swap.

### Case 14 — Compound or unknown system is refused before any search

Covers: the `toast-opera` class of error (Jasper's sample) and any non-catalog id — a **400 before
search**, never a wrong answer.

- **Setup:** local harness; mint a directed token with `source_system: "toast-opera"` (compound),
  then one with `target_system: "not-a-system"`.
- **Action:** open Obi.
- **Expected:** each is **400** ("unknown integration value") *before* any retrieval
  (`auth_context.py:202-207` → `router.py:287-289`). The compound resolves to nothing
  (`legacy_aliases` is `{}`); the unknown id resolves to nothing. No search runs, no answer.
- **Verify:** Network tab 400; no `trace_id`.

### Case 15 — Vend rights and inactive registration

Covers: an issuer may assert only the source/target ids agreed in its `allowed_integrations`, and an
`active: false` platform is denied all scoped access even though its token verifies.

- **Setup:** local harness with a test issuer whose `allowed_integrations` is, say, `["toast"]`.
- **Action + Expected:**
  1. Mint a token asserting a system **not** in that issuer's vend set (e.g. `target_system: "xero"`
     when only `toast` is vended) → **401** (vend-rights violation, CIP-A1, `auth_context.py:209-217`).
  2. Point the harness at an issuer whose registry entry is `active: false` → the token **verifies**
     (step 1 uses `by_issuer`) but the gate denies with `InactivePlatformError` → **401**
     (`auth_context.py:240-242`). This is the backstop that keeps an unverified partner inert until
     the owner flips `active: true`.
- **Verify:** Network tab 401 for both; no answer.

### Case 16 — Customer / connection switch without logging out (Marien's requirement)

Covers: one user, multiple customers; the selection changes without a page reload and the chat resets
so nothing carries across customers (`plan.md` §D.18 item 5; `partner-facts.md` Base section).

- **Setup:** `/test-hosts/multi` (switches the signed-in identity / re-points `Obi.init`), or a page
  that posts a replacement `obi:token` with a different `business_id`.
- **Action:** ask a question as customer A (`business_id: B-A`); without reloading, switch to customer
  B (`business_id: B-B`) and ask again.
- **Expected:** on the switch, Obi **resets the thread** (scope change detected on the changed
  `business_id` → `restart()`); customer B's answer never references customer A's conversation; the
  backend chat-session row is keyed on `(sha256(sub), company_id)`, so B gets its own session.
- **Verify:** the widget thread clears on the switch; two trace rows under two `company_id`s; no A
  content in B's answer. **Record the host trigger used** (re-init vs token-replacement) — this is the
  behaviour to agree with Marien.

### Case 17 — Embed-origin lock (frame-ancestors)

Covers: Obi loads only on a platform's registered embed origins; an unregistered origin is blocked by
the `/embed` `frame-ancestors` CSP (`middleware.ts:51-56` from `activeDomains()`).

- **Setup:** a registered test origin and an unregistered one.
- **Action:** embed the `/obi.js` snippet on each and open the chat.
- **Expected:** the widget iframe loads and functions on the **registered** origin; on the
  **unregistered** origin the browser blocks the frame (CSP `frame-ancestors` violation in the
  console) and the chat does not load.
- **Verify:** console shows the CSP block on the unregistered origin; the response CSP header lists
  only `active: true` platforms' domains. (Only the temporary `obi-test` origin is active today, so a
  partner's origin must be added to its `active` entry before its page can embed.)

### Case 18 — Source-enablement widget eligibility (live pass/fail gate — §D.18 item 4, ADR-source-system-decides-widget-eligibility)

Covers: the owner decision of 2026-10-20 "only the **source** system decides whether Obi shows; the
target is never checked" (ADR-source-system-decides-widget-eligibility, which supersedes the
which-endpoint part of ADR-widget-hides-via-visibility-probe; the probe, 403 render and `obi:hidden`
message stay). **Status: LIVE GATE.** As built: `enabled_sources` (`["mews","toast","opera-cloud"]`)
in `product_catalog.json`; in the directed gate (`auth_context.py`, `_build_directed_context`) an
unresolved source → `SourceNotEnabledError` **403**, a known source the issuer may not vend →
**401**, a vended source not in `enabled_sources` → **403**; a read-only `GET /chat/visibility`
probe; the frontend hide (loader decodes `source_system` + the `obi:hidden` frame→host message).
Retrieval routing (ADR-directed-source-target-routing-labels D5 four-label filter) is unchanged.

- **Setup:** a directed token whose **source** is not a supported system (e.g. Base's real example
  `source_system: "PEP PMS"`, `target_system: "NetSuite"`). The token otherwise verifies.
- **Action:** open Obi.
- **Expected (PASS):** the widget is **hidden** — `GET /chat/visibility` returns
  `{"visible":false,"reason":"source_not_enabled"}`, the loader hides before/at mount (via
  `obi:hidden`), and `POST /chat` for the same connection is refused **403** with body
  `{"error":"integration not available","reason":"source_not_enabled"}` (no product id in the body).
- **Expected (FAIL):** widget mounts / is visible, or `POST /chat` is served (or returns a status
  other than 403), or the body leaks the product id.
- **Control (must also hold):** an **enabled source with any target** — e.g. `toast → mews`, and
  `toast → NetSuite` (unknown target) — is `visible:true` and the session is served; the unknown
  target routes on `[obi-general, toast-general]`. The gate does not over-hide and never checks the
  target.
- **Verify:** record the observed `GET /chat/visibility` body, the `POST /chat` status + body, and
  whether the launcher mounted. **PASS/FAIL gates Phase A** (no longer decision-dependent).

---

## Evidence capture (fill in per case — leave blank until a human runs it)

Copy this block once per case (Cases 1–10). Record the actual observation and a reference to the
trace (`trace_id`) or screenshot for each step. A case is **PASS** only when every step is PASS with
evidence on file. Where a case failed and was fixed, keep the failed row and add a re-run block
below it labelled "RE-RUN after fix".

### Case N — <title>

| # | Step (§D.10 order) | Expected | Observed | PASS/FAIL | Screenshot / trace ref | Notes |
|---|---|---|---|---|---|---|
| 1 | Configuration (preset / slots; visible or hidden) | | | | | |
| 2 | Metadata (Applies-to records present; edit applied where relevant) | | | | | |
| 3 | Included / excluded page & chunk ids | | | | | |
| 4 | Reranker results (eligible-only, no reintroduction) | | | | | |
| 5 | Answers (answers vs refuses/asks; no invented connection) | | | | | |
| 6 | Citations (every sentence cited; attribution badge matches) | | | | | |
| 7 | Further retrieval (≤ 2 reads; same eligibility; no excluded page) | | | | | |

**Case verdict:** ☐ PASS  ☐ FAIL  → if FAIL: problem / fix / re-run reference: ______________

### Integration cases 11–18 — capture per environment (local harness AND partner staging, separately)

Copy this block once per integration case. Each case is recorded **twice**: once on the local harness
(runs now) and once against each partner's staging (when it exists). A local PASS never stands in for
a partner-staging PASS.

| Env | Setup / token variant | Expected (status / labels / behaviour) | Observed | PASS/FAIL | Network / trace / console ref | Notes |
|---|---|---|---|---|---|---|
| Local harness | | | | | | |
| Partner staging — Base | | | | | | |
| Partner staging — Data Hub | | | | | | |

**Case verdict (per env):** Local ☐ PASS ☐ FAIL · Base-staging ☐ PASS ☐ FAIL ☐ N/A · DataHub-staging ☐ PASS ☐ FAIL ☐ N/A

When all cases pass with evidence, file this document with the step (as the 4.4 browser checks were
filed) and only then may the owner tick 8.5.2. Recording the evidence here does **not** by itself
flip the panel or write the ledger — those are separate, owner-gated steps. Case 18 is now a
**live pass/fail gate** (§D.18 item 4, ADR-widget-hides-via-visibility-probe — the eligibility refinement shipped in Task 5) and
gates 8.5.2 like any other case.

---

## Coverage map (8.5.2 "Must be true" → cases)

| Required coverage | Case(s) |
|---|---|
| Two-system context | 2, 3, 4, 5, 8, 9a, 10 |
| Three-system context | 6 |
| Flow type POS→PMS | 2 |
| Flow type PMS→POS | 3 |
| Flow type PMS→Accounting | 4 |
| Flow type POS→Accounting | 5 |
| General guidance | 1 (+ the general leg of every case) |
| Shared pages | 8 |
| Unknown configuration | 1, 9 |
| Multiple connections | 6, 7 |
| Workflow bindings | 6, 7 |
| Metadata updates | 10 |
| §D.9 examples 1–5 | 4, 2, 3, 6, 7 |
| Cross-match guard (Toast/OperaCloud + Mews/QuickBooks ≠ Toast/Mews) | 7 |
| Directed token accepted + routed to its connection | 11 |
| Token integrity (bad signature / unknown key / expired / wrong aud / wrong iss) | 12 |
| Direction is primary (source→target ≠ target→source) | 13 |
| Compound / unknown system refused before search | 14 |
| Vend rights + inactive registration denied | 15 |
| Customer/connection switch without logout (Marien) | 16 |
| Embed-origin lock (frame-ancestors) | 17 |
| Source-enablement widget eligibility (live gate — ADR-source-system-decides-widget-eligibility) | 18 |

## Gaps and assumptions (honest)

1. **§D.9 example 5 (Case 7) is not exercisable through the standalone preset selector.** The
   launch slots-only token holds one product per role, and Opera Cloud as PMS is off the launch
   allowlist (it would hide Obi). The two-PMS, two-connection property needs real connection records
   (§D.1 target shape, `legacy-three-slot-context-contract.md` §9 — deliberately **not** in the launch contract). The
   cross-match guard is reproduced by the automated DB test today; live Phase A validation of it
   waits on §D.3/§D.4 real-connection context landing in the standalone env. Recorded as a gap, not a
   pass.
2. **The out-of-allowlist / hidden case (9b) is a backend-gate check, not a chat check.** No preset
   expresses an off-allowlist filled slot; verifying hiding/refusal needs a crafted token against the
   gate. Treat 9b as a configuration-step assertion.
3. **Cases 8 and 10 need corpus setup** (real Confluence pages with specific provider labels and
   "Applies to" records) and, for Case 10, an ingestion/sync pass. The retrieval-only cases (1–7, 9a)
   can run against a seeded pgvector corpus. The owner decides whether to run 8 and 10 against a live
   Confluence space or a locally-seeded corpus; either is valid as long as the metadata is real.
4. **The nine real Base pages are still unlabelled** (§D.16 item 6) and therefore not indexed, so
   Phase A runs against seeded/preset corpora, not the real Base corpus, until the owner re-labels.
5. **Inspection surface for included/excluded ids, reranker order, and further retrieval** is the
   retrieval trace keyed by the response `trace_id`. If no dedicated trace viewer exists in the
   runner's environment, the human reads the trace row directly (DB/logs) and records the reference —
   the inclusion **reason** per cited source is independently visible on the widget as the attribution
   badge.
6. **Assumption:** the attribution badge labels transcribed here (`"General guide"`, `"For your POS"`,
   etc.) are the current widget strings (`message-bubble.tsx`); if the UI copy changes, the expected
   badge text in the cases must be updated to match, but the underlying enum
   (`general|pos|pms|accounting|pair`) is the design-of-record oracle.
7. **Integration cases 11–18 prove our side on the local harness now; the real end-to-end leg waits
   on partner staging.** The local harness uses our own test keys and `test-*.local` issuers, so a
   local PASS proves the gate/widget behave correctly — not that Base or Data Hub authentication
   works. The partner-staging leg of each case runs only once that partner confirms its issuer, JWKS
   and token endpoint (current per-partner state: `partner-facts.md`). Record the two legs
   separately; do not call a case fully passed on the local leg alone.
8. **Case 18 is a live gate on the source (ADR-source-system-decides-widget-eligibility, 2026-10-20).**
   The gate first shipped on the target (ADR-widget-hides-via-visibility-probe, 2026-10-13); the owner
   then decided only the **source** decides. An unsupported source is refused **403**
   `source_not_enabled` and the widget hides via `GET /chat/visibility` + the `obi:hidden` message; the
   target is never checked. A disabled source that mounts the widget or is served fails the case.
   Retrieval routing (ADR-directed-source-target-routing-labels D5) is unchanged.
