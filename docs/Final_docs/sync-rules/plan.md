# Sync rules — make the vector store match the eight rules

> **REOPENED 2026-10-13** — the "CLOSED / fully done" status below is superseded by the active-work
> block immediately following (target-enablement gate + consolidated integration verification). The
> historical CLOSED record is kept intact beneath it. Start here.
>
> **UPDATE 2026-10-20 — the gate is on the SOURCE, not the target.** ADR-source-system-decides-widget-eligibility
> (owner, 2026-10-20) supersedes which endpoint the Task 5 gate checks: `enabled_targets` is renamed
> **`enabled_sources`** (same value, `mews`, `toast`, `opera-cloud`), `TargetNotEnabledError` →
> **`SourceNotEnabledError`**, reason `target_not_enabled` → **`source_not_enabled`**. An unknown or
> disabled source → 403 (visibility probe `visible:false`); the target is never checked, and an
> unknown target routes on `[obi-general, {source}-general]`. The Task 5 text below records what was
> built on 2026-10-13 and is kept as written; read "target" in its gate wording as "source" for
> current behaviour. Current status per gate: `widget-target-enablement-hide.md` (frontend) and
> `5-integration-context/phase-a-validation-cases.md` Case 18. How a partner integrates:
> `docs/Final_docs/1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md`.
>
> **Removed docs cited below.** `sync-rules/test-proof.md`, `sync-rules/path-b-audit.md`,
> `0.2-agent-quality/`, `0.4-design-review/` and `5-integration-context/jasper-reply-draft.md` were
> deleted on 2026-10-20. Mentions of them in the historical sections are kept as provenance; the
> ledger entries remain the record of what they proved. Old `apps/web` / `apps/automation` paths
> mean `frontend/` / `backend/`.

---

## Active work block — target-enablement gate + consolidated integration verification (2026-10-13)

> **EXECUTION STATUS 2026-10-13 — Tasks 0–5 code+docs SHIPPED; only the human pass remains.**
> Driven as four parallel agents (Tasks 2/3/4 + Task 5 backend) then two sequential (Task 5 frontend,
> Task 5e). Done: **Task 0** (plan recorded); **Task 2** `phase-a-run-sheet.md` (Cases 1–18);
> **Task 3** `partner-activation-patch.md` (both partners, 5 blanks each, verify sequence);
> **Task 4** `decision-memo.md` §6 routing/visibility capture; **Task 5** the target-enablement gate —
> `enabled_targets` config + loader rule 6b, `TargetNotEnabledError`→**403** (precedence 400→401→403),
> read-only `GET /chat/visibility`, frontend load-time hide (`__OBI_ENABLED_TARGETS__` decode) +
> `/chat/visibility` probe + the 4th `obi:hidden` message, 13 backend + 19 frontend unit tests, the
> `widget-hidden-when-target-disabled` e2e spec (signed-key-gated, proven locally with a throwaway key),
> the `securing-http-and-llm-endpoints` review (no gaps), and **ADR-widget-hides-via-visibility-probe** amending ADR-directed-source-target-routing-labels D4/D5 +
> doc sync (`context-contract.md` §4/§8.4, `catalog.md`, `decision-memo.md` §7, Case 18 flipped to a
> live gate). `make check` green (boundaries 0 · backend 1555 +1 xfail · kb 53); retrieval routing
> UNCHANGED so rule 11 owes no gold-set number; no migration; reversible (empty/absent `enabled_targets`
> ⇒ inert). **NOT done (per owner "not the testing"):** Task 1 (Option B local-harness verification,
> both legs) and the **single consolidated human-validation pass** (Phase A Cases 1–10 + integration
> 11–18 local-leg incl. the now-live Case 18). Those are the human/manual legs; the build that makes
> Case 18 a live gate is in place, so the pass can now run once. Ledger + progress-log carry one entry
> per task.

### Context

Obi is code-complete and live in production (ADR-routing-labels-sole-content-axis Path B, directed `source → target` routing). The
remaining tail is human/partner: Phase A human validation, then Base + Data Hub partner integration
(0/5 facts confirmed from each partner today).

This block does four things the owner asked for, plus one build the owner decided to pull forward:

1. **Option B local-harness verification** — prove our embed → token → directed-routing → isolation
   path works end-to-end on our own side, so that when a partner's staging comes up any failure is
   unambiguously theirs. Owner chose **both** legs: automated Playwright smoke *and* the manual
   real-gate leg.
2. **Phase A run-sheet** — turn `phase-a-validation-cases.md` (Cases 1–18) into a standalone
   fill-in checklist so the owner can work the gating step top to bottom.
3. **Pre-staged `platforms.json` activation patch** — a paste-and-go diff per partner (filled as far
   as the facts allow, five blanks marked) + the verify sequence, so activation is minutes not fresh
   work when a partner replies.
4. **Capture the routing/visibility clarification** the owner gave into the decisions record, because
   it resolves open §D intent and one of its assertions ("QuickBooks target → widget hidden") is not
   yet built.
5. **Build the target-enablement visibility gate** (owner decided to scope now) — the selected
   connection's target (and source) product must be in a configurable *enabled* set, else the widget
   hides and the gate refuses, mirroring the legacy slot-form allowlist hide. This flips Phase A
   Case 18 from "decision-dependent, not a gate" into a real gate and amends ADR-directed-source-target-routing-labels D4/D5.

#### Owner instructions governing this block (2026-10-13)
- **Recorded here as the authoritative plan**, word for word (this block is Task 0's output).
- **Implement in full, 100%, word for word** — the whole of Tasks 0–5 ships; nothing is deferred except
  the parts physically blocked on partner facts (the Cases 11–18 *partner-staging* legs; 0/5 facts from
  each today).
- **Consolidate the human testing into a single pass.** Some human validation (Phase A) was always
  required; the new Case 18 gate adds more. Do it **once, after Task 5 ships** — Phase A Cases 1–10 plus
  the real-gate integration Cases 11–18 (now including the live Case 18 gate) in one sitting — so no
  case is run twice. See "Human testing — one consolidated pass" below.
- Work the CLAUDE.md loop (one substep, failing-test-first, ledger + progress-log, `make check`), but
  proceed through the plan without stopping for a go-ahead between every substep ("rock and roll");
  still pause at the §13 compaction points (every 2 substeps) and before the Task 5 security review.

#### Routing model — confirmed against code (the owner's description is correct)

`product_catalog.build_labels(source, target)` (`backend/app/platform/config/product_catalog.py:137-157`)
yields exactly four labels:
`[obi-general, {source}-general, {target}-general, {source}-to-{target.role}]`.

The connection label is **source-product → target-*role*** (`toast-to-pms`), not source→target-product;
the target product's own docs ride the separate product-level `{target}-general` label. Consequences
for content coverage:

- `toast → mews` → `[obi-general, toast-general, mews-general, toast-to-pms]`
- `toast → opera-cloud` → `[obi-general, toast-general, opera-cloud-general, **toast-to-pms**]` — reuses
  the **same** `toast-to-pms` connection pages as toast→mews. Only **new** content needed:
  `opera-cloud-general` (Opera's own software docs).
- `mews → quickbooks-online` → `[obi-general, mews-general, quickbooks-online-general, **mews-to-accounting**]`
  — needs **both** new `quickbooks-online-general` docs **and** `mews-to-accounting` connection pages
  (no `*-to-accounting` pages exist yet).

So the "content long-pole" is small for a same-role target (opera-cloud as PMS reuses toast-to-pms) and
real only for (a) each target product's own `-general` docs and (b) a brand-new target *role*
(accounting), whose `{source}-to-accounting` connection pages don't exist.

### Task 0 — Record this plan in the authoritative sync-rules plan
Done by this block: this plan is written verbatim into `docs/Final_docs/sync-rules/plan.md` with the
REOPENED pointer above. Discoverable from the top of the file. No ledger entry for Task 0 itself; ledger
entries begin with the first code/doc deliverable (Tasks 2+).

### Task 1 — Option B local-harness verification (both legs)
Runs **fully local** (not against prod). Two legs, recorded separately per the cases doc.

**1a. Automated smoke (fast).** `pnpm test:e2e` in `frontend/` (`package.json:13` → `build:obi &&
playwright test`; webserver `next dev --port 3100`). Covers, all with a **mocked** `/api/chat`:
`widget-mounts.spec.ts`, `connection-switch.spec.ts`, `citation-attribution.spec.ts`,
`standalone-presets.spec.ts`. Proves the widget, switch-reset, attribution rendering. Does **not** touch
the real token gate.

**1b. Real-gate manual leg (Cases 11–18 local).**
- Prereq — local RS256 test keys (gitignored, per `docs/embedding/obi-embed-local-test-keys.md`):
  generate `TEST_OBI_PRIVATE_KEY_{NONE,MEWS,TOAST,OPERA}` via openssl into `frontend/.env.local`, or
  the mint route returns 503. Public keys serve from `/api/test-hosts/jwks/[issuer]`.
- Stack: `make up` → `make migrate` → seed a corpus carrying the labels each case needs (locate the
  seed path during execution) → `make web-dev`. Point both apps at
  `knowledge-base/config/platforms.local.json` via `PLATFORMS_PATH` (test issuers
  `test-{mews,toast,opera,none}`, all `active: true`, RS256).
- Walk Cases 11–18 through the real gate via `/test-hosts/toast` (`toast→mews`),
  `/test-hosts/opera-cloud` (`opera-cloud→toast`), `/test-hosts/connection-switch`, `/test-hosts/multi`,
  `/test-hosts/none`; mint API `/api/test-hosts/[name]/obi-token?form=directed`.
- Record evidence (Network status, `trace_id`, console) in the run-sheet's Cases 11–18 "Local harness"
  column. A local PASS is not a partner-staging PASS — leave partner columns N/A.
- Case 18 becomes a real pass/fail gate after Task 5 — run it in the consolidated pass.

### Task 2 — Phase A run-sheet
Create `docs/Final_docs/5-integration-context/phase-a-run-sheet.md` (none exists; the cases doc only
embeds a blank template at `phase-a-validation-cases.md:466-504`). One section per case (1–18): exact
question(s), preset / directed token, connection under test, expected include/exclude + attribution
badges, and the §D.10 seven-step evidence table with empty PASS/FAIL + trace-ref cells. Cases 11–18 get
the per-environment (local / Base / Data Hub) table. Pure transcription from the cases doc + a one-line
"how to reach this context" per case. Carries the doc's honest gaps (Case 7 not preset-expressible, 9b
gate-only, 8/10 need corpus+sync).

### Task 3 — `platforms.json` activation patch (pre-staged, not applied)
Do **not** write placeholder entries into `knowledge-base/config/platforms.json` — a registry entry
needs a real `issuer`+`jwks_url` or the backend fails to load. Produce
`docs/Final_docs/5-integration-context/partner-activation-patch.md`: the exact per-partner JSONC block
(from `partner-facts.md`), five blanks marked, plus (a) the **accounting-integrations-map** note (a hub
that vends `quickbooks-online`/`xero` needs that id added to the top-level `integrations` map or the
registry won't load), (b) the verify sequence (JWKS reachable → endpoint mints a conforming directed JWT
→ vend rights → flip `active:true` → redeploy BE+FE → drop the temporary `obi-test` issuer → run Cases
11–18 partner-staging leg).

### Task 4 — Capture the routing/visibility clarification
Append to `docs/Final_docs/5-integration-context/decision-memo.md` (cross-link `plan.md` §D R2/R5): the
confirmed label model, the content-coverage consequence above, and that target-enablement hide is being
built (Task 5), citing this as the resolution of the open §D intent. Append-only; names the design
panel / §D item it serves.

### Task 5 — Target-enablement visibility gate (BUILD)
**Headline finding:** there is **no existing frontend hide to reuse**. `loader.ts init()` (L248-258)
mounts the launcher + iframe unconditionally; an off-allowlist token today yields a bare 401 that
`restart()`s the open thread — launcher stays visible, user opens it and gets a refused turn. `plan.md`
§D.18 item 4 confirms "no target-enablement eligibility gate today — widget hiding is frontend UX over
the backend 401." The backend gate shape is reusable (mirror slot-form `SlotNotOnAllowlistError`); the
**frontend hide is net-new**.

**5a. Config (recommended).** New global flat field in `knowledge-base/config/product_catalog.json`:
`"enabled_targets": ["mews", "toast", "opera-cloud"]`. Enabled iff listed; QuickBooks goes live by not
being listed. **Absent ⇒ all enabled** (backward-compatible, reversible, load-bearing default). Loader:
add validation rule "6b" in `product_catalog.py` `load_product_catalog` (mirror the rule-6 allowlist
loop L336-350): every id a real canonical product; store `enabled_targets: frozenset[str]`, materialize
"absent ⇒ all ids". Flat (not role-keyed) because a directed target can be PMS or accounting. Rejected:
extending `launch_allowlist` (slot-era, role-keyed); per-platform `enabled_targets` (exceeds owner's
product-global intent — kept as the §D R3/R4 extension). `enabled_sources` omitted by default.

**5b. Backend gate (`auth_context.py`, `router.py`).** New `TargetNotEnabledError(AuthContextError)`
(after `SlotNotOnAllowlistError`, ~L103); message never leaks the product id (rule 10). New check in
`_build_directed_context` **after check 4 (vend rights, L209-217)**, so precedence stays: unknown target
→ 400 before search (checks 1-2) → vend violation → 401 (check 4) → not-enabled → 403 (new); update the
docstring's "allowlist (5) LAPSES" absolute. Router `_resolve_auth_context` (L284-291): add a
`TargetNotEnabledError` branch **before** the generic `AuthContextError` catch → HTTP 403 body
`{"error": "integration not available", "reason": "target_not_enabled"}` (403 keeps it off the 401 renew
path and distinct from the 400 fail-closed family; proxy forwards status+body verbatim,
`route-handlers.ts` L130-136); add optional `reason` to the `Error` schema in
`packages/contracts/src/openapi/chat.yaml`. New read-only `GET /chat/visibility` on `router.py`, auth by
the same `X-Obi-Token` via `_resolve_auth_context`: `{"visible": true}` or `{"visible": false, "reason":
"target_not_enabled"}`; 400/401 hard failures propagate as today; document in `chat.yaml`.

**5c. Frontend hide (recommended: load-time, no flash).** `loader.ts`: inject `__OBI_ENABLED_TARGETS__`
at build via esbuild `--define` from `product_catalog.json` (exactly how `__OBI_ORIGIN__` works, L29-34,
in `build:obi`). In `init()`, before mounting, fetch the token once and **decode `target_system`**
(display-only, same non-trust posture as `decodeExpMs` L75-85); if the decoded target isn't enabled,
return without mounting (no launcher, no iframe). The trust-bearing fetch still happens fresh at click.
Server-authoritative cross-check: `embed-frame.tsx` calls `GET /chat/visibility` on token receipt; if
`visible:false`, it posts a **new 4th frame→host `obi:hidden` message** and the loader `destroy()`s.
Conventions this bends (authorize in ADR-widget-hides-via-visibility-probe): (1) one eligibility-only token fetch at `init` in
addition to the click fetch; (2) a 4th `ObiMessage` type (`chat-client.ts` L49-57 and
`packages/contracts/src/iframe-messages.ts` flag it as needing its own ADR). Fallback (named, not
chosen): click-time destroy — simpler, flashes then vanishes.

**5d. Tests (`test_<stage>_<behavior>`; each names its panel) — no DB/migration, no gold-set number.**
Retrieval untouched (label hard-filter / ADR-directed-source-target-routing-labels D5 unchanged), so rule 11's before/after-number clause
does not trigger — state in ADR + ledger. Catalog loader unit (`test_product_catalog.py`): parses
`enabled_targets`; rejects unknown id; absent ⇒ all. Gate unit (new `test_mi_gate_directed.py`): refuses
disabled target; allows enabled; precedence guards (unknown target still 400; vend violation still 401 —
both before enablement). Router unit: disabled → 403 + `reason` + no product id in body (rule 10);
visibility probe reports hidden. Frontend unit (`features/embed/tests/`): hides when decoded target not
enabled; mounts when enabled. e2e (new `widget-hidden-when-target-disabled.spec.ts`): disabled-target
host stub ⇒ launcher count 0 (needs a `/test-hosts/*` stub minting a `target_system:
"quickbooks-online"` token; same signed-key caveat as `widget-mounts.spec.ts`).

**5e. ADR + doc sync.** New **ADR-widget-hides-via-visibility-probe "Target-Enablement Widget Eligibility in the Directed Path"**
amending ADR-directed-source-target-routing-labels D4/D5: partially reverses the allowlist lapse for *widget eligibility only*; retrieval
routing unchanged; backend 403 is authority, frontend hide is UX; authorizes the init fetch + the 4th
`obi:hidden` message. Sync `context-contract.md` §4/§8.4, `decision-memo.md`, `catalog.md`; flip
`phase-a-validation-cases.md` Case 18 to a live pass/fail gate.

**5f. No migrations.** Pure config + gate + router + one GET + frontend loader. Reversibility (rule 11):
remove/empty `enabled_targets` ⇒ feature inert ⇒ today's behavior, no code revert.

### Human testing — one consolidated pass (no case run twice)
All human validation runs **once, after Task 5 ships**, driven by the Task 2 run-sheet: Phase A Cases
1–10 (retrieval/eligibility against the seeded/preset corpus) **plus** integration Cases 11–18
local-harness leg **including the now-live Case 18 gate** (unsupported **source** ⇒ widget hidden +
403 `source_not_enabled`, per ADR-source-system-decides-widget-eligibility; the target is never checked).
Record every case's evidence; a case is PASS only with human evidence on file (panel `mi-validate`,
§D.10). The **only** human testing that cannot fold in now is each partner's **staging leg of Cases
11–18** (needs that partner's issuer/JWKS/token endpoint — 0/5 facts today); those columns stay N/A
until a partner replies.

### Execution order (CLAUDE.md loop; proceed without a go-ahead between substeps; pause at §13 compaction points)
**0 (record plan) → 2 (run-sheet) → 3 (activation patch) → 4 (decision capture) → 1a (automated smoke)
→ 5 (build the gate, with its security review) → consolidated human-testing pass (Phase A 1–10 +
integration 11–18 local, Case 18 live).** Doing the build before the human pass is what lets the pass
cover Case 18 live and run only once. Partner-staging legs follow whenever facts arrive.

### Verification (whole block)
- `make check` green (boundaries 0 · backend suite · kb suite); ruff + pyright clean on touched files
  (whole-repo counts never rise above baseline, ADR-features-import-only-through-public-root D1).
- Task 1a: `pnpm test:e2e` green. Task 1b: Cases 11–18 local-leg evidence recorded in the run-sheet.
- Task 5 is an **endpoint + gate change** → run the `securing-http-and-llm-endpoints` review and the
  `obi-secure-phase`/security-review step before done; new unit/e2e tests green; **no** gold-set number
  (retrieval untouched — state in ADR); no migration.
- Each finished substep: failing-test-first, panel/`today` flip, component docs where touched, ledger +
  progress-log entries. Proceed without a go-ahead between substeps; pause at §13 compaction points,
  before the Task 5 security review, and before anything outward-facing/hard-to-reverse.

### Open sequencing note
Task 5 pulls §D work **ahead** of Phase A, which the plan otherwise sequences last. Accepted by owner.
Phase A Case 18 re-runs as a gate once Task 5 ships, and ADR-directed-source-target-routing-labels is amended.

---

## Historical record — the CLOSED sync-rules plan (pre-2026-10-13)

Status: **code + tests complete (approved); tag behaviour verified live; Supabase at migration head
(0014) as of 2026-09-25** — §13 **all 6 steps done and green**; `make check` green (backend 940 + 1
xfailed, kb 43, boundaries 0). The two live scripts are **written** (`page_state.py` tested by
`test_page_state_script.py`; `verify_sync_rules.py` authored). On **2026-09-25** the tag→scope path was
**verified end-to-end against live Supabase via
the localhost:3100 widget**: scope-correct retrieval + isolation (toast→"grapes"/Toast Testpage,
mews→"red bananas"/Mews Testpage, no cross-leak), and the **Q-B empty-tags census came back clean
(0 active chunks with `tags=[]`)**. On **2026-09-25** Supabase was **brought to migration head**:
`alembic upgrade head` applied **0013 + 0014** (current before `0012`, after
`0014_chunk_scope_fail_closed (head)`), and both live proofs passed — 3d: as `rag_reader`, empty tags
are visible to **no** scope while mews/toast/operacloud/general each return 2 and `*` returns 8; 3e:
reconciliation ran every 15s with drift 0 / errors 0 and the `reconciliation_run.cursor` error is
**gone**. Also on **2026-09-25** the **live sync-rules runner passed its automated leg** on the real
prod test pages (no staging exists; owner-authorized): `verify_sync_rules.py --no-manual` drove rules
**2/3/4/5/7 + rule 8 — all PASS**, labels restored, the Toast page rebuilt clean (retain-0: 0 inactive
chunks, 1 version row); output in `backend/sync-rules-run.txt`. **What remains — owner only,
deploy-and-sign-off tail:** ~~(1) bring Supabase to migration head~~ **DONE 2026-09-25**; (2) run the
**two manual live rules** — 1 (trash/restore) + 6 (body/title edit) — the automated leg is **DONE
2026-09-25**; (3) tick the 2.2.4/2.3.1 action-plan checkboxes once (2) is in the PR; ~~(4) reconcile
the stale design-page target-lines~~ **DONE 2026-09-25** (owner go-ahead; 7 panels reconciled to
D1–D4). The **▶ Remaining work checklist** at the top of §0 has the exact commands and gotchas. **The
only tail left is (2) the two manual live rules, then (3) the checkboxes.**

**Update 2026-09-30 — the live webhook is now the delivery path.** The Forge bridge
(`services/obi-confluence-sync/`) was registered, deployed to Forge production and installed on
`omniboost.atlassian.net`; secret parity Forge↔Railway proven by signed curl (200 valid / 401
tampered); worker drain confirmed on Railway (`ENABLE_BACKGROUND_JOBS=true`, job succeeded); and a
real Confluence `label_added` event (unrecognized smoke label on Toast-testpage 2 `1713176590`)
travelled Confluence → Forge → Railway → event ledger → job → correct no-index decision, with the
indexed Toast page byte-identical to baseline. That satisfies `i1-webhook`'s live-proof condition
(see `docs/Final_docs/ingestion/webhook.md`) and means the two manual rules below can — and should —
be driven through the **real webhook** (plain Confluence UI actions, verified with `page_state.py` +
the event ledger) instead of the in-process `verify_sync_rules.py` runner. Each manual leg must also
re-assert **rule 8**: the Mews page `1670971395` stays byte-identical throughout. Full detail in §0's
2026-09-30 block.

**Update 2026-10-05 — the tail above is CLOSED; this plan is fully done.** The "only tail left"
line in the Status paragraph is superseded: on 2026-10-05 the permanent webhook-path runner
(`backend/scripts/webhook_rules_live.py`, built as roadmap substep 4.3) drove **all 8 rules —
including the formerly-manual rules 1 (trash/restore) and 6 (body/title edit) — through the real
Confluence → Forge → Railway → worker path, all PASS** (~11 s/leg, zero residue, rule-8 witness
fingerprint identical; output in `backend/webhook-rules-live-run.txt`; a real restore-API bug was
caught and fixed on the first run — ledger "4.3-addendum"). The **2.2.4 / 2.3.1 action-plan
checkboxes are ticked** (substep 4.8, citing the 2026-09-30/10-05 webhook proofs). Roadmap **Step 4
(test foundation, absorbing §15.2 golven 0–4) is complete end to end** (substeps 4.1–4.8, see
`docs/Final_docs/plan.md`). **Step 5 has started:** §D.0 — the scope-restamp fix closing the
2026-10-03 findings A+B — is done (commit `41fc248`, ledger "D.0"), the owner decided the **§15
keuzes 1–4** plus the archive rule and rule-8 cap in decision round 1 (`plan.md` §D.13), and the
deferred checks X3–X6 were run and recorded (`plan.md` §D.14). Still open, owner-side: the
DB-password rotation window (runbook `plan.md` §D.15) and the obi-resync label cleanup. Nothing in
THIS file remains to execute — it stays as the record of the eight-rule work and the home of the
§15 decision pointers; the forward plan is `docs/Final_docs/plan.md` §D.

**Update 2026-10-05 (later) — Step 5 moved again; this file stays closed.** The owner's parallel
batch ran (archive-caught-by-lightweight-sweep proven by test; `obi-resync` verified already
clean; the §D.1 contract + product catalog designed in `docs/Final_docs/5-integration-context/`;
§D.6 rerank-API + §D.9 Jasper research filed there) and **owner decision round 2 landed**
(recorded in `plan.md` §D.16): frontend deploys on **Railway**; the launch allowlist gates
**POS/PMS only** (O4 closed); §D.11's `toast-opera` example was proven to exist nowhere and is
**removed** (O8 closed — note for readers of §5.7/§D.11 prose here and in plan.md: that value was
illustrative, never real); the **DB-password rotation is the immediate owner action**; Base/Data
Hub integration (O7, the Jasper reply) is deliberately **last**, after Phase A; the nine
unlabeled real pages stay unlabeled until Phase A. Everything forward-looking lives in
`plan.md` §D — this file remains the eight-rule record only.

**Update 2026-10-06 (build complete bar the owner tail) — the §15 keuzes are now code; this file stays the record.** The
§15 decisions these pages pointed at (keuzes 1–4, the three-slot contract, the launch allowlist) are
built: Step 5's Phase 8 ran autonomously through **every agent-doable substep — 8.1.1–8.4.2 plus
8.5.1 (thirteen substeps)** — the product-catalog loader, the three-slot token/Citation contract
(legacy `integration` claim kept forever), the gate's five slot checks, the "Applies to" schema,
chunk applicability (migration 0015, restamp-no-re-embed), the deterministic matcher, in-SQL
eligibility filtering, context-aware reranking and answer prompt, per-slot source attribution, the
standalone presets, the widget carrying the extended context, and the five §D.9 worked examples
reproducing their exact include/exclude lists. The **eight sync rules this file documents stayed
green and unmodified throughout** (the regression suite is the gate on every one of those substeps),
and applicability is a *relevance narrowing on top of* membership + access — it never widens what a
label or RLS allows. `make check` green (boundaries 0 · backend 1229 + 1 xfailed · kb 51), pyright
43, `pnpm test:e2e` 6 specs, eval at the 4.5 floor + a new `mixed_connection` gold stage. **Only the
owner tail remains in Phase 8:** 8.4.3 (frontend deploy to Railway), 8.5.2 (Phase A human
validation), 8.5.3 (the Jasper reply) — plus the §D.15 DB-password rotation. Detail and status live
in `plan.md` §D / §A row 5 and the ledger entries 8.1.1…8.5.1 — not here.

**Update 2026-10-09 — 8.4.3 is DONE and the owner tail is now just human + send; this file still stays the record.** The
"only the owner tail remains" line above is superseded in one place: **8.4.3 (frontend deploy to Railway) is done.** The
frontend is live as the Railway service **`obi-web`** at `https://obi-web-production.up.railway.app`, serving `/obi.js`
(the deployed origin baked into the bundle) and `/embed` (whose `frame-ancestors` CSP is computed from the active
`platforms.json` domains); the deploy is codified as `scripts/deploy-frontend.sh` (it hides the backend-only repo-root
`railway.json`/`Dockerfile`/`.dockerignore` during upload so Railway builds the web workspace, not the backend image) and
re-proven 7/7 by the new `frontend/scripts/embed-check-live.mjs` (output in
`docs/Final_docs/5-integration-context/embed-check-8.4.3-run.txt`). Runbook: `docs/runbooks/railway-frontend-deploy.md`;
canonical embed origin recorded as decision `obi-js-url` (the Railway host for now, `obi.omniboost.com` deferred). **The
eight sync rules this file documents were not touched** — 8.4.3 is a deploy of the existing frontend, no ingestion/retrieval
code changed, `make check` still green (boundaries 0 · backend 1240 + 1 xfailed · kb 51). The two remaining Phase-8 items
are now **prepped and owner-gated**: 8.5.2 (Phase A human validation) has its case doc
`docs/Final_docs/5-integration-context/phase-a-validation-cases.md` (10 cases, humans run it), and 8.5.3 (the Jasper reply)
has its draft `docs/Final_docs/5-integration-context/jasper-reply-draft.md` (owner edits + sends; the working obi.js URL now
exists). Operational tails: §D.15 DB-password rotation, and a **temporary `obi-test` embed allow-list**
(`platforms.json` domains = the Railway host) to remove at real integration. Detail + status: ledger entries `8.4.3`,
`8.4.3-addendum`, and `8.5.2 / 8.5.3 prep + housekeeping` (2026-10-09), and `plan.md` §D / §A row 5 — not here.

**Update 2026-10-12 — owner decision round 3; the rule-5 question that lived against THIS file is
resolved (fix-code).** The round's forward calls are recorded in `plan.md` §D.17 (DB-password
rotation **deflagged** — not needed now, moved to future work; Base and Data Hub always have exactly
**two** systems, a `source` and a `target`, superseding the "up to 3 / max 2" note; the `obi.js`
script `src` stays the Railway **web** host for the test phase, with `obi.omniboost.com` before
go-live; the Jasper reply corrected — earlier threads gave the **backend** host as the origin, but
the script `src` is the web host, and the sample `toast-opera` token is refused with a 401). The one
call that belongs to this file: the owner picked **fix-code** on the open `live-0.5.3-cm-docs`
decision (rule 5 vs shipped code). **Nothing to change** — the membership gate this file built in
§13 step 2 (`ingest_decision.resolve_scopes`: `if not recognized_labels: return set()` → `delete`)
plus step 6's first-tag positive guard already make the code conform to never-bend rule 5 (published
+ a recognized tag to be indexed; losing the last recognized tag removes the page; roots decide
nothing), and step 3 retired `scope_state` (ADR-scope-state-materialized-as-tags). The lone wording nuance — rule 5 says
last-tag-loss *"deactivates"* while the code *purges* — is the deliberate D1/D4 choice (kill
rollback, retain 0), not a divergence to fix. `docs/plan/decisions.md`'s `live-0.5.3-cm-docs` row is
closed on this pick. Step 6 (Phase B automated-test expansion) still starts **only after Phase A
human-validation evidence is in** (§D.17 item 6). This file stays the eight-rule record.

**Update 2026-10-13 — ADR-routing-labels-sole-content-axis Path B went LIVE, and the audit follow-up is done; this file stays the
record.** Two things happened today, both captured in detail in §0's `Production cutover 2026-10-13`
block and in the ledger/progress-log. **(1) Production cutover.** With owner go-ahead + a confirmed
Supabase backup, Path B shipped: committed as `3178553`, prod migrated `0014 → 0018` (the two
RESTRICTIVE knowledge-scope policies dropped; `chunk_source_read` + `chunk_labels_read` + RLS
retained — rule 1 intact), and `obi-backend` redeployed on Railway (`/health` → `knowledge_scopes:
[]`, worker draining every 5s). A COMPLETE reconciliation sweep is re-indexing the corpus — it
correctly enqueued the whole `omnidoc` space (1069 pages; `source_scope` row 23 scopes the entire
space) and the deployed, sink-bound worker drains in job-id order, so the nine routing-labelled pages
(the tail jobs) index last. **(2) Audit follow-up (`sync-rules/path-b-audit.md`).** The audit found
no hard code gaps but two test-proof gaps (rules 3 & 4) and ~5 stale operator files; both are now
closed in the working tree. Sync rules **3 & 4** gained end-to-end proof — `test_sync_rules_routing.py`
drives a routing-label change through the real sync path and asserts `chunk.labels` grows/shrinks AND
that retrieval routing flips per connection (proven real by the 0.2.8 revert method). The stale
operator files (`verify_sync_rules.py` / `webhook_rules_live.py` / `smoke_webhook.py` defaults →
routing labels; `verify_directed_routing_live.py` `GATE_SCOPE` → `()`; `verify_knowledge_scope_live.py`
SUPERSEDED banner; `routing-test-labels.md` / `manual-tests.md` / the phase-9 runbook → the
routing-label membership model) are fixed. `make check` green (boundaries 0 · backend 1542 + 1 xfail ·
kb 53). **Owner/worker-owned tail (NOT agent-closable):** the re-sync must finish and the live
isolation proof (`verify_directed_routing_live.py`) must run — once the tail jobs drain, confirm
chunks appear; if they stay 0 the nine pages lack a recognized routing label. **One flagged, not
fixed:** `setup_supabase.py check-deploy-readiness` still asserts the retired `chunk_scope_read`
(fails SAFE); re-speccing it for Path B is its own security substep (banner added meanwhile). The
eight sync rules this file documents were not modified by any of this.

**Update 2026-10-13 (roadmap + routing knowledge, owner-confirmed).** Two clarifications recorded in
the closing **"Laatste items (owner)"** section below. **(1) Phase order:** Phase A human testing
comes first, and **immediately after** it comes the full A-Z platform integration into **Base
(Marien)** and **Data Hub (Jasper)** — stand everything up end to end, which explicitly includes
contacting both partners and collecting the five facts Obi needs (issuer, JWKS URL, exact embed
domains, each customer's source+target ids, and a token endpoint). The send-ready directed-contract
emails already exist in `5-integration-context/phase-9-partner-replies.md`. **(2) Source/target
routing axis:** the source systems Obi accepts are exactly `mews`, `opera-cloud`, `toast` (a chat
starts from one of these); targets are tagged too and the target *narrows* the results (the source's
whole eligible set is fetched, then the target picks the relevant directional slice, e.g.
`toast-to-pms`); accounting products (`quickbooks-online`, `xero`) are targets only. Partners send
ids, not role labels — Obi derives POS/PMS/accounting from the id; a compound like `toast-opera` is
refused. Launch allowlist today is Toast (POS) + Mews (PMS); Opera Cloud later.

**Update 2026-10-13 (later) — the technical verify tail is PROVEN LIVE; two lines in the cutover
block above are superseded.** Following owner go-ahead, all five remaining technical verify items
were run **read-only against production Supabase on 2026-10-13** and all passed. This supersedes the
2026-10-13 cutover block's "**Owner/worker-owned tail (NOT agent-closable)**" and "**One flagged,
not fixed**" lines.

- **Re-sync tail drained (item 1).** Jobs `1249–1261` (13 × `sync_page`) are all `succeeded`,
  attempts 1, zero errors / dead-letter. The nine routing-labelled pages each now carry **2 active
  chunks**, one routing label each: `1713176590` toast-general · `1748238338` mews-general ·
  `1748434948` toast-to-pms · `1748434956` opera-cloud-general · `1748664352` toast-to-accounting ·
  `1748697100` mews-to-accounting · `1749123082` obi-general · `1749319690` mews-to-pos ·
  `1749352478` opera-cloud-to-pos. (Four other pages in the same batch — `1725005829`,
  `1725792258`, `1730838570`, `1741619205` — succeeded with 0 chunks because they carry none of the
  nine routing labels; they are not members, not part of the nine.)
- **Live isolation proof PASS (item 2).** `verify_directed_routing_live.py --source toast --target
  mews --mirror` → exit `0`, both directions, connected as the non-owner **`rag_reader`** role (RLS
  enforced, not an owner bypass), non-vacuous (5 other-connection pages correctly hidden each way),
  zero mismatches. `toast→mews` sees {toast-general, mews-general, toast-to-pms, obi-general};
  `mews→toast` flips (`mews-to-pos` visible, `toast-to-pms` hidden). §D Stage 9 Task 4's live-proof
  leg is satisfied.
- **Readiness gate — re-spec already shipped + live READY (item 3) — CORRECTION.** The cutover
  line "One flagged, not fixed … still asserts the retired `chunk_scope_read`" is **wrong for HEAD**.
  The re-spec is committed in `8025d24`: `check_deploy_readiness` no longer asserts the retired
  `chunk_scope_read` / `curated_knowledge_entry_scope_read`; it asserts the Path B backstop
  (`chunk_source_read` PERMISSIVE/SELECT + chunk RLS enabled + the curated reader policy) and only
  *reports* the fail-open `chunk_labels_read` routing axis, with a 4-case test
  (`test_deploy_readiness_check.py`) green in `make check`. Run live 2026-10-13:
  `setup_supabase.py check-deploy-readiness` → rc `0` READY ("the Path B tenant backstop is in
  place … reader path safe to expose"; host password masked `***`, no secret leaked).
- **source_scope allow-list SAFE (item 4).** All 5 active rows carry empty `tags=[]` — ids 10
  (`1671069719`), 11 (`1670971395`), 12 (`1672314881`), 13 (`1670873122`), 23 (space `701857803`).
  None authorizes zero routing labels, so no wrongful-deletion risk. Extends the earlier
  id=23-only check to all five active rows.
- **Sweep CQL length SAFE (item 5).** The reconciliation label-discovery CQL over the current
  catalog (`all_routing_labels()` = 21 labels) builds a **464-character** `label in (...)` clause
  (`confluence_client.py:259-260`) — far under Confluence Cloud's multi-thousand-char limit. The
  historical 400 was the invalid `space.id` field, not length (already fixed to a label-only CQL).
  Live-corroborated: the sweep that enqueued jobs `1249–1261` ran this exact CQL and all 13 jobs
  succeeded, no 400.

**Net:** the whole **technical verify tail (items 1–5) is closed and proven live**. What remains is
the **human / partner tail only** — Phase A human validation first, then the A-Z Base + Data Hub
integration (the five facts from Marien + Jasper; the directed-contract emails are send-ready in
`5-integration-context/phase-9-partner-replies.md`, pending only the `[OWNER: name]` and the
pick-one JWKS-test-option placeholders), and the optional `obi.omniboost.com` DNS switch. `make
check` green (boundaries 0 · backend 1542 + 1 xfail · kb 53). These checks were run by an agent in
this session, read-only, with owner authorization; no writes, no labels created, no secrets printed.

**§14 (Execution appendix)** inlines the exact test harness, the current + target RLS DDL, the
counting embedder, the naming/docstring/coverage/proof formats, and the CI xfail mechanics — so a
fresh-context agent can execute from this file alone, without re-deriving them from the tree.
Line numbers elsewhere in this doc are anchors as of writing; trust the named symbols/panel ids over
the numbers, and grep the live tree if they drift.

---

## 0. Execution status (updated 2026-09-25) — read this first on resume

Owning action-plan substep: **2.2.4** (the §13 series is packaged under it, plus pointers into
2.2.5 / 2.3.1 / 2.4.1 / 3.4.1). Branch: `feat/rag-phase-4-embed-security-hardening`. Everything is
**left uncommitted in the working tree** per the branch's owner-review convention. The running
record is `docs/Final_docs/ledger.md` + `docs/Final_docs/progress-log.md` (one entry per §13 step);
this §0 is the at-a-glance index those entries expand on.

### ▶ Remaining work (the clean-slate checklist) — 2026-09-25

The eight-rule **code, tests and local proof are done and green**; the tag→scope path is **verified
live** (retrieval + isolation through the localhost:3100 widget against Supabase); and **Supabase is
now at migration head (2026-09-25)**. What is left is **owner-only** — staging / a live Confluence
action. Do them in order:

> **→ NEXT ACTION: the OWNER runs the two MANUAL live rules (1 delete, 6 edit).** The **automated**
> live rules **2/3/4/5/7 + rule 8 all PASSED on 2026-09-25** against the real prod test pages
> (Toast `1670873122` scope-a `obi-toast-test`, Mews `1670971395` as the rule-8 side-check), run with
> `--no-manual` (no staging exists yet — owner accepted running on the grapes/bananas prod test pages).
> Output saved to `backend/sync-rules-run.txt`; the page came back healthier than baseline (retain-0
> clean: 0 inactive chunks, 1 version row). Rules **1 (trash/restore)** and **6 (body/title edit)** are
> interactive Confluence-UI steps the owner will run later; only then are 2.2.4/2.3.1 fully ticked.

### ✅ Done 2026-09-30 — Forge webhook bridge deployed, installed and proven live (delivery leg of 2.0.2)

Everything below ran on 2026-09-30; working tree still uncommitted per the branch convention
(`services/obi-confluence-sync/manifest.yml` now carries the real app id, plus the generated
`package-lock.json` — commit both). Runbook followed: `docs/runbooks/obi-confluence-sync-deploy.md`.

- **Registered** the Forge app once (manifest placeholder → real id
  `ari:cloud:ecosystem::app/b36e7d9d-5117-4f7e-a49e-fcdb6ca19118`). En route: the account had no
  Developer Space, so one named **Omniboost** was created, and the Atlassian Developer Terms
  (incl. the beyond-free-allowance billing clause) were accepted.
- **Secret** `CONFLUENCE_WEBHOOK_SECRET` set as an **encrypted Forge production variable** before
  deploy (same value as the Railway service variable; never printed).
- **`forge lint`** clean after `--fix` migrated the deprecated egress entry to the `- address:` form;
  **`forge deploy -e production`** succeeded (app version 2.0.0); **installed** on
  `omniboost.atlassian.net` Confluence (owner, via the install dialog; `forge install list` shows
  production / Up-to-date).
- **Proof 1 — secret parity (signed curl at Railway):** valid HMAC → `200 {"accepted":true,
  event_id:1, job_id:28}`; tampered body, same signature → `401 invalid signature`.
- **Proof 2 — worker drain:** job 28 `succeeded` on Railway (`ENABLE_BACKGROUND_JOBS=true` confirmed
  in effect).
- **Proof 3 — real event end-to-end (label smoke):** owner added the unrecognized label
  `obi-smoke-test-delete-later` to **Toast-testpage 2 (`1713176590`)** in the Confluence UI →
  Forge delivered it (deterministic-hash `delivery_id`) → event_ledger row 2 (`label_added`,
  `origin=0`) → job 29 `succeeded` → worker correctly indexed **nothing** (no recognized label; 0
  `page_source` rows) — the rule-5 negative half observed live through the real webhook. The indexed
  Toast Testpage `1670873122` stayed byte-identical to its pre-test baseline (tags
  `['obi-toast-test']`, 2 active chunks, 1 version row). This is `i1-webhook`'s live proof
  (webhook.md: a real Confluence event → one ledger row + one job within seconds); the panel flip to
  verified is pending with the step-3 checkbox batch. Note: `forge logs` showed nothing despite the
  proven delivery (Atlassian log-ingestion lag) — the ledger is the evidence of record.
- **Consequence for the remaining manual legs:** run rules 1 and 6 as plain Confluence-UI actions and
  let the **live webhook** deliver (stronger evidence than the in-process `verify_sync_rules.py`
  path, which predates the bridge). Verify each with `scripts/page_state.py 1670873122` + the event
  ledger, and re-assert **rule 8** each time: `page_state.py 1670971395` (Mews) byte-identical
  before/after every leg.

**1 · Bring Supabase to migration head (applies 0013 + 0014) — ✅ DONE 2026-09-25.** Was behind by
0013 (`reconciliation_run.cursor`) + 0014 (RLS fail-closed floor). `alembic current` read `0012`
before; `upgrade head` applied both; `current` after = **`0014_chunk_scope_fail_closed (head)`**. Only
`upgrade` was ever run (never-bend rule 1). Q-B census was **0** immediately before; port was the
session pooler (5432, not 6543); owner confirmed a recent backup first. Live 3d proof: as `rag_reader`
(via `get_reader_engine`, both `app.allowed_sources` and `app.allowed_knowledge_scopes` set) empty-tags
chunks visible = **0** under mews/toast/operacloud/general/`*`/unset, while real corpus = 2/2/2/2 per
scope and 8 under `*`. Live 3e proof: reconciliation ran every 15s (drift 0, errors 0,
pages_scanned 4), each job succeeded, **zero** `reconciliation_run.cursor` errors. The steps below are
kept for the record / any future re-run.
  - **Q-B gate first** — census must be run right before 0014 (last run 2026-09-25 was **0**):
    ```
    cd backend && uv run python -c "
    from schema.engine import session_scope
    from sqlalchemy import text
    with session_scope() as s:
        print('empty-tags active chunks:', s.scalar(text('select count(*) from chunk where is_active and cardinality(tags)=0')))
    "
    ```
    **0** → proceed. **>0** → re-tag the legitimately-global pages with `obi-general-test` in
    Confluence and re-sync first; leave the rest (they correctly go dark). Do not auto-mutate.
  - **Gotcha:** `.env` `DATABASE_URL` is **double-quote-wrapped**; the app strips the quotes but raw
    alembic does not (it throws "Could not parse SQLAlchemy URL"). Pass it unquoted, never printing
    the secret:
    ```
    cd backend
    export DATABASE_URL="$(python3 -c "print([l.split('=',1)[1].strip().strip(chr(34)) for l in open('../.env') if l.startswith('DATABASE_URL=')][0])")"
    uv run alembic -c ../knowledge-base/migrations/alembic.ini current       # confirm the gap
    uv run alembic -c ../knowledge-base/migrations/alembic.ini upgrade head  # applies 0013 + 0014
    uv run alembic -c ../knowledge-base/migrations/alembic.ini current       # expect 0014
    unset DATABASE_URL
    ```
    **Only ever `upgrade` on Supabase — never `downgrade` (especially 0009; never-bend rule 1).**
  - Verify the floor is live (as `rag_reader`, expect 0):
    `SET ROLE rag_reader; SET app.allowed_knowledge_scopes='mews'; SELECT count(*) FROM chunk WHERE cardinality(tags)=0 AND is_active; RESET ROLE;`

**2 · Run the live MT-1..MT-7 proof.** ◑ **Automated leg DONE 2026-09-25; manual leg (rules 1, 6)
owner-deferred.** No staging exists, so — with owner sign-off — the automated rules were run on the
real prod test pages with `--no-manual --scope-a obi-toast-test --scope-b obi-mews-test`:
```
cd backend
uv run python scripts/page_state.py 1670873122 | tee baseline.txt
uv run python -u scripts/verify_sync_rules.py --page-id 1670873122 --other-page-id 1670971395 \
    --scope-a obi-toast-test --scope-b obi-mews-test --no-manual --yes | tee sync-rules-run.txt
```
Result: rules **2/3/4/5/7 + rule 8 all PASS**, labels restored, page rebuilt clean (retain-0). Pre-flight
verified live first: OpenAI embeddings OK (3072) and Anthropic OK (the earlier stale key is fixed), so
rebuilds fully contextualize+embed. The contextualizer degrades to metadata-only on an `AnthropicError`
(never aborts a rebuild), so a stale Claude key could not have left the page purged. **Still owner-only:**
rules **1** (trash then restore the page in Confluence) and **6** (edit body, then rename title) — the
two interactive UI steps `--no-manual` skips. Re-run without `--no-manual` to drive them:
    ```
    cd backend
    uv run python scripts/page_state.py <page_id>                     # baseline snapshot
    uv run python scripts/verify_sync_rules.py --page-id <page_id> --other-page-id <other> --yes
    ```
  Auto-drives rules 2/3/4/5/7 via the label API; **pauses** for the manual trash/restore (rule 1) and
  body/title edit (rule 6). `--no-manual` runs only the automated rules. **Save the output → paste in
  the PR** (the CLAUDE.md live-level rule). This output is what unblocks step 3.

**3 · Tick the 2.2.4 / 2.3.1 checkboxes** in `obi-action-plan.html` — only after step 2's output is in
the PR (they name that live proof).

**4 · Reconcile the stale design-page target-lines** on `obi-rag-system-flow.html` — ✅ **DONE
2026-09-25** (owner go-ahead). 17 field edits across 7 panels (`tg-two`, `i4-gc`, `vd-swap`,
`i3-embed`, `i2-rebuild`, `r3-scope`, `tg-filter`) brought simple/steps/tests/settings/note/code text
to D1–D4; `r3-scope` flipped `unverified → built` (0014 applied + verified live). Recorded in
`docs/Final_docs/0.4-design-review/plan-corrections.md` ("TARGET lines RECONCILED"); brief regenerated
(192 panels).

> Also live-confirmed on 2026-09-25 but **not** a sync-rules deliverable: the localhost:3100 widget
> answers end-to-end once a **valid `ANTHROPIC_API_KEY`** is in `.env` (a stale key returned 401 —
> "answer generation failed"). Retrieval/isolation are independent of that key.

### ✅ Done — §13 step 1 (purge_page + rule 1 + rule 7 + restore)

Rules satisfied: **1** (delete/trash/archive → purge), **1b** (delete→restore = first-index full
rebuild), **7** (`classified` label → purge).

- **New code:** `purge_page(session, *, page_id)` in
  `backend/app/features/ingestion/application/versioning.py` (one FK-safe txn: null the deferred
  `active_doc_version_id` → delete `document_version` by page_id [chunks cascade] → delete
  `document` → delete `page_source` [restrictions cascade]); exported from the ingestion feature
  root (`__init__.py`).
- **Routing:** `confluence_sync/application/sync_service.py` now purges from all four delete
  surfaces — `handle_delete_page`, the `meta is None` path, the `classify().is_delete` path, and
  **new** `classified`-label detection on the raw labels via `RESERVED_CLASSIFIED_SCOPE` (matched
  before scope resolution, since `classified` is excluded from the recognized set). `SyncOutcome`
  action renamed `deactivated`→`purged` (no non-test code branches on `.action`).
- **Config:** `RESERVED_CLASSIFIED_SCOPE` re-exported from `app.platform.config` root.
- **Tests (database):** `backend/app/features/confluence_sync/tests/test_sync_rules_delete.py` —
  `test_in2_delete_page_removes_rows`, `test_in2_delete_then_restore_full_rebuilds`,
  `test_in2_classified_label_removes_rows`. Test infra added to `tests/_helpers.py`:
  `CountingEmbedder`, `install_counting_embedder`, `page_row_counts`.
- **Removed** the strict-xfail `test_delete_marks_the_active_version_superseded` (moot: purge deletes
  the version row) and the redundant `test_delete_deactivates_page`, both in `test_worker_sync.py`.
- **Docs/panels:** component doc `docs/Final_docs/ingestion/deletion-and-purge.md`;
  proof `docs/Final_docs/sync-rules/test-proof.md`; corrections appended to
  `docs/Final_docs/0.4-design-review/plan-corrections.md`; coverage rows added to
  `docs/Final_docs/0.5-regression-tests/coverage-map.md`; panel `tg-classified` flipped
  `build→built`, `i2-gone`/`tg-purge` today-lines corrected (status flips batched to step 6); brief
  regenerated.
- **Gate:** `make check` green (backend 931 passed, kb 41 passed, boundaries 0); ruff/pyright clean
  on touched code; whole-repo pyright net-decreased (ADR-features-import-only-through-public-root D1 holds).

### ✅ Done — §13 step 2 (rule 2 + membership gate)

Rules satisfied: **2** (last recognized label removed → purge), **5** (first-seen page with no
recognized label → never ingested). Panels `tg-remove` (build → built), `ks-index` (today-line
updated); `i2-gone` today-line updated (unlabeled trigger now live).

- **New code:** membership gate in `sync_service.handle_sync_page`, right after
  `resolve_knowledge_scope_tags`: `if not scope_result.matched_labels:` → `purge_page` if already
  indexed (`local is not None`), else `SyncOutcome(action="skipped")`. Keys on **matched_labels**
  (recognized labels present), not resolved `tags`, so a conflict page (zero tags this sync) stays
  indexed rather than churning. `SyncOutcome.action` gains `skipped`. The scope-resolution block was
  moved above the restrictions/attachments fetch so the gate short-circuits before that work.
- **Tests (database):** `test_sync_rules_membership.py` — `test_tags_remove_last_recognized_label_removes_rows`,
  `test_tags_unrelated_labels_alone_do_not_keep_page`, `test_in2_untagged_page_never_indexed`,
  `test_tags_recognized_label_present_keeps_page` (guard). Red-today proof + guard-inversion proof in
  `test-proof.md`.
- **Test-infra decision:** the generic DB fixtures (1001/1002/2002/3005/3007/3010) carry only
  unrelated labels, so the gate un-indexes them. The shared `index_page` helper now injects the base
  `obi-general-test` scope **only when a page has no recognized label** (leaving scope-tagging tests
  that set their own recognized label untouched). 14 tests across 12 files were adjusted (explicit
  recognized label on direct `handle_sync_page`/enqueue paths; `'*'` knowledge-scope wildcard on 3
  RLS source-axis tests that relied on the empty-tags floor; premise rewrites for
  scope_tagging_add/reindex/verify_isolation_script). Full list in `plan-corrections.md`.
- **Source_scope coexistence:** roots still sweep+tag but no longer grant membership (a covered page
  needs a recognized label); `test_reconciliation.py`'s two root tests updated accordingly.
- **Gate:** `make check` green (backend 935 passed, kb 41, boundaries 0); ruff/format clean on
  touched files; whole-repo pyright net-decreased (the `index_page` annotation change removed a
  pre-existing `set_version` error; ADR-features-import-only-through-public-root D1 holds).
- **Live proof deferred (owner-blocked):** the `tg-remove`/`ks-index` **live** leg — the staging
  label script — is **not** run (needs staging + `CONFLUENCE_WEBHOOK_SECRET` + Confluence
  site-admin). `tg-remove` was flipped `build → built` on the unit+db proof alone, mirroring step
  1's `tg-classified` flip; the live leg stays outstanding (§9 scripts still unwritten).
- **Deviation — no feature flag:** the gate is **unconditional**. The action-plan 2.2.4 body
  mentions "a cut-over flag with default on," but its own *Must be true* says "always, with no
  feature flag," and never-bend rule 5 is unconditional — built flagless, recorded in
  `plan-corrections.md`. Flip to a flagged cut-over only on owner request.
- **Independently verified (not just self-reported):** step 2 was implemented by a subagent, then
  reviewed against the actual diff and re-run — `make check` green on an independent run; the 14
  adjusted tests were audited for weakened assertions (none found; `test_versioning_swap` is
  strengthened; the 3 RLS tests keep their source-isolation asserts, only the orthogonal scope axis
  is opened); confirmed no code branches on `SyncOutcome.action`, so the new `skipped` is inert.

### ✅ Done — §13 step 3 (drop conflict D4 + rule 4 visibility + rule 3 guard + retire scope_state)

Rules satisfied: **4** (add a recognized tag → union it in, no re-embed, same version; shared tags
visible in each scope), **3** (remove one tag, another stays → metadata-only, no re-embed). Decision
**D4** implemented; `scope_state` retired.

- **Code:** `resolve_knowledge_scope_tags` (`domain/knowledge_scope.py`) now returns **all** matched
  recognized tags — the `conflict` field and the `provider_tags` branch are deleted from
  `KnowledgeScopeResult`. `sync_service.handle_sync_page` drops the `knowledge_scope_conflict`
  warning block; `final_tags` naturally unions both providers. Membership gate unchanged (still keys
  on `matched_labels`, which now equals `tags` for a shared page). `KnowledgeScopeResult` export
  unchanged.
- **`scope_state` retirement:** confirmed **zero code touch points** (no enum, no column, no
  consumer) across `backend/` + `knowledge-base/`; every mention was a test docstring/comment or
  design prose. State stays materialized as `tags` (ADR-scope-state-materialized-as-tags). Retirement is a plan/design act only.
- **Tests (database):** new `test_sync_rules_visibility.py` — `test_tags_add_second_tag_updates_tags_no_reembed`,
  `test_tags_shared_page_visible_in_both_scopes`, `test_tags_general_tag_visible_everywhere` (guard),
  `test_tags_remove_shared_tag_keeps_other_scope`, `test_tags_remove_one_tag_keeps_page_updates_tags_no_reembed`
  (rule-3 guard). Inverted the three two-provider resolver unit tests in `test_knowledge_scope.py`
  (now `..._share_both_scopes_*`) and rewrote `test_ingestion_pipeline.py`'s conflict test to
  `test_two_provider_labels_share_all_scopes_no_conflict_log`. **Removed** the moot
  `test_s_audit_knowledge_scope_conflict_log_line_emitted_on_conflicting_labels` (that audit event no
  longer exists; s-audit's other two log lines keep their own tests). Red-today + guard-inversion
  proofs in `test-proof.md`.
- **Eval (Rule 11):** `make eval` before/after **byte-identical** (only the run label differs) → no
  gold-set regression. Caveat: the bundled baseline ranker doesn't route through knowledge-scope
  resolution, so it can't move on this change — the real visibility proof is the db+retrieval tests.
- **Docs/panels:** `today` lines updated on `tg-two`/`tg-conflict`/`tg-state`/`i2-labels` (status
  flips + target reconciliation batched to step 6, mirroring steps 1–2); corrections in
  `plan-corrections.md` (incl. 2.2.3 retired/absorbed, 2.5.1 re-scoped to the D3 backfill);
  coverage-map rows added; `deletion-and-purge.md` conflict wording corrected; brief regenerated.
- **Gate:** `make check` green (backend **939** passed, kb **41**, boundaries 0); ruff/format clean
  on touched files; whole-repo pyright unchanged (47; the 3 pre-existing `PageHashes bytes|None`
  errors in `sync_service.py` are present at HEAD, outside this diff — ADR-features-import-only-through-public-root D1 holds).
- **Security (RLS/visibility touch):** the change strictly **tightens** isolation — the old
  conflict→empty-tags path let a two-provider page reach *every* scope via the RLS empty-tags floor;
  now it carries real tags and is visible only in its own scopes. The residual empty-tags=public
  floor (any regression to empty tags) is closed defence-in-depth by D3 in step 4. No HTTP endpoint,
  LLM call, or outbound network was modified.

### ✅ Done — §13 step 4 (RLS floor fail-closed D3 + read-path overlap D4)

Rules satisfied: cross-cutting **3.4.1 / r3-scope** (empty tags visible to no scope; read paths use
`tags && allowed_scopes` overlap, not equality). Decision **D3** implemented; **Q-A** resolved.

- **Code:** `apply_chunk_scope_rls` (`knowledge-base/schema/schema.py`) drops the
  `OR cardinality(tags) = 0` clause — `chunk_scope_read` is now pure `'*'` opt-out **OR** `tags &&
  string_to_array(scope_guc)`; docstring rewritten to the fail-closed posture. `apply_curated_scope_rls`
  **unchanged** (curated keeps its floor, D3). New migration
  `knowledge-base/migrations/versions/0014_chunk_scope_fail_closed.py` — self-contained raw DDL (so
  the downgrade restores the pre-0014 with-floor policy even though the helper is now floor-less),
  `down_revision = 0013_reindex_progress`. The DB test harness applies RLS via
  `schema.apply_chunk_scope_rls` (`db_harness.py:146`), not alembic, so the schema edit is what the
  sec tests exercise; the migration round-trip is proven separately by the KB alembic-chain test.
- **Tests:** 2 new db tests in `test_customer_isolation_backstop.py` —
  `test_sec_empty_tags_visible_to_no_scope` (red today: `assert 18 == 0`; green after) and
  `test_sec_read_paths_use_overlap_not_equality` (green-today guard, inversion `&&`→`=` confirmed
  red then restored). The moot `test_scope_rls_untagged_chunk_is_global_visible_under_any_scope`
  (asserted the removed floor) was **rewritten in place** into the fail-closed test. 2 new
  reversibility tests in `knowledge-base/tests/test_migration_0014_chunk_scope_fail_closed.py`.
  Proofs in `test-proof.md`.
- **Q-A resolved (corrects the step-1 §0 note):** the flag default is **False** in both code and the
  test env — the step-1 "runs True" note was a misread (retrieval tests pass `True` directly to the
  `HybridRetriever` constructor, not via env). RLS fail-closed is flag-independent; the app-layer
  flag stays default-False, its flip deferred to PLAN 10.7's operator `.env` (`test_settings.py:49-51`).
  No default change. Eval before/after byte-identical (fixture ranker runs under `'*'`, can't move).
- **Docs/panels:** `r3-scope`/`i2-labels` today-lines updated (status flips + target reconciliation
  batched to step 6 — `r3-scope`'s target still names the retired `scope_state='ok'` conjunct, not
  edited in place); `plan-corrections.md` step-4 section; `coverage-map.md` rows; brief regenerated.
- **Gate:** `make check` green (backend **940**, kb **43**, boundaries 0); ruff/format clean on the 3
  touched files; whole-repo pyright unchanged at **47** (ADR-features-import-only-through-public-root D1 holds).
- **Security (RLS touch):** strictly **tightening** — dropping an `OR` clause only reduces
  visibility; empty tags now reach no scope; unset GUC still denies; `'*'` opt-out kept for the
  trusted eval/parent path only; curated untouched; RLS `ENABLE`d, never disabled/forced. No HTTP
  endpoint, LLM call, or outbound network modified.
- **Live/Q-B deferred (owner-blocked):** applying 0014 to Supabase + the pre-deploy empty-tags
  backfill audit (Q-B) need the owner; the `r3-scope` **live** leg stays outstanding.

### ✅ Done — §13 step 5 (rule 6: no reuse + title rebuild + retain 0)

Rules satisfied: **6** (a rebuild embeds the whole page, no vector reused). Decisions **D1** (retain
0, kill rollback) and **D2** (attachments deferred, strict xfail) implemented. Panels `i3-embed`,
`i2-rebuild`, `i4-gc`, `vd-swap` today-lines updated (status flips batched to step 6).

- **Code:** `versioning.py` — `DEFAULT_RETAIN_SUPERSEDED` 2→0; `_resolve_children` re-embeds every
  child (dropped `diff_chunks`/reuse); removed the `old_children` threading, `reusable_active_children`,
  `_pipeline_config_matches`, and `rollback_to`. `sync_service.py` — `ChangeClass.title_changed`
  added to `_REBUILD_CLASSES` (a rename rebuilds; safe on `uq_document_version_idem` — a title edit
  bumps `cf_version`). `ingestion/__init__.py` + `FEATURES.md` — reuse/rollback dropped from the
  public surface. `.github/workflows/ci.yml` — attachment strict-xfail added to the test-db
  allow-list (dead `test_delete_marks_the_active_version_superseded` name removed).
- **Tests (database):** `test_sync_rules_rebuild.py` — `test_in3_body_edit_reembeds_every_chunk_no_reuse`,
  `test_in3_title_change_reembeds_every_chunk`, `test_in3_rebuild_deletes_old_version_rows_immediately`,
  `test_in3_attachment_edit_reembeds_page` (**strict xfail**, needs 2.4.1). Ripple rewrites (not
  weakened): `test_versioning_gc.py` (retain 0), `test_versioning_swap.py`, `test_worker_sync.py`
  (vd-swap + `count_versions==1`), `test_reindex.py`, `test_attachment_wiring.py`. Retired:
  `test_pipeline_reuse.py`, `test_versioning_rollback.py`, `test_reuse_guard_disables_on_config_change`.
- **Deviation (cut-depth):** removed the dead reuse *wiring* but **retained** the pure `chunk_diff`
  domain leaf + its test (now unused, deferred removal). `rollback_to` removed outright (retain 0
  leaves no target; rule 11 forbids an untested exported fn). Status flips batched to step 6.
- **Gate:** `make check` green (backend 935 passed + 1 xfailed, kb 43, boundaries 0); ruff/format
  clean on touched files; whole-repo pyright net-decreased 47→44 (ADR-features-import-only-through-public-root D1 holds). See §0 ledger.

### ✅ Done — §13 step 6 (rule 5 positive guard + rule 8 invariant + finalise)

Rules satisfied: **5** positive half (first recognized tag on an untagged page → full build; the
negative half landed in step 2), **8** (a change to one page never touches another's rows).

- **Tests (database):** `test_in2_first_relevant_tag_full_build` (panel ks-index) added to
  `test_sync_rules_membership.py`; `test_in2_change_never_touches_other_pages_rows` (panel vd-swap) in
  the new `test_sync_rules_isolation.py`. Both green-today guards, each proven real by the 0.2.8
  revert method (rule 5: invert the membership gate; rule 8: drop the `page_id` scope on the version
  delete in `purge_page`) — production-file checksums matched before/after (no residue). Proofs in
  `test-proof.md`. No production code changed.
- **Docs finalised:** `coverage-map.md` + `test-proof.md` step-6 sections; **created**
  `manual-tests.md` (MT-1..MT-7, each mapped to its automated mirror + `verify_sync_rules.py` live
  coverage, honest that the live scripts are owner-blocked/unwritten); `plan-corrections.md` step-6
  section recording the batched status flips + everything deliberately left undone.
- **Design-page statuses flipped** (`obi-rag-system-flow.html`, via `panel.py`): `i2-gone`,
  `tg-purge`, `i2-labels`, `i3-embed`, `i2-rebuild`, `tg-two` → **built**; `tg-conflict`/`tg-state`
  (retired) + `tg-deactivate` (narrowed) today-lines finalised. Brief regenerated (192 panels).
- **Gate:** `make check` green (backend 937 passed + 1 xfailed, kb 43, boundaries 0); ruff/pyright
  clean on the touched test files; whole-repo pyright unchanged at 44 (ADR-features-import-only-through-public-root D1 holds).
- **Deliberately NOT done (owner-blocked / workflow-constrained) — see the step-6 ledger entry:**
  design-page **target** lines left stale (workflow forbids editing a target line; tracked in
  `plan-corrections.md`); `tg-conflict`/`tg-state` status unchanged (no `retired` status word);
  action-plan checkboxes for 2.2.4/2.3.1 **not ticked** (each names a live proof that is owner-blocked);
  the live scripts + Q-B backfill + 0014-to-Supabase remain outstanding.
  - **→ Update (2026-09-25):** most of this tail has since been cleared — **0014 applied to Supabase**,
    **Q-B census clean**, **target lines reconciled** (owner go-ahead; 7 panels), and the
    **verify_sync_rules.py automated leg passed** on prod. Only the **two manual live rules (1 delete,
    6 edit)** and the **2.2.4/2.3.1 checkboxes** remain. See §0.

### Cross-cutting deliverables still outstanding (§9, §12)

- **Scripts (live level):** `backend/scripts/page_state.py` (read-only page dump) and
  `backend/scripts/verify_sync_rules.py` (staging runner, MT-1..MT-7). ✅ **Written (2026-09-24).**
  `page_state.py` is tested (`test_page_state_script.py`, 3 db tests) and runs against any DB, no
  secrets. `verify_sync_rules.py` mirrors `verify_knowledge_scope_live.py`: it auto-drives the
  label-based rules (2/3/4/5/7) via the v1 label API and prompts for the physical trash/restore
  (rule 1) and body/title edit (rule 6); it refuses the offline fixture and requires `--yes`. Like
  its sibling live script it has no hermetic test (network + credentials). **Automated leg RUN
  2026-09-25** on the real prod test pages (owner-authorized; no staging): `--no-manual --scope-a
  obi-toast-test --scope-b obi-mews-test` → rules **2/3/4/5/7 + rule 8 all PASS**, labels restored,
  page rebuilt clean (retain-0); output in `backend/sync-rules-run.txt`. The script is self-contained
  (no API server / worker / webhook needed — it enqueues+drains jobs in-process), so
  `CONFLUENCE_WEBHOOK_SECRET` is **not** needed to run it. **Still outstanding:** the two manual rules
  **1** (trash/restore) and **6** (body/title edit) — interactive Confluence-UI steps, owner-run.
- **`docs/Final_docs/sync-rules/manual-tests.md`** (MT-1..MT-7 human procedures) — ✅ **written
  (step 6).** Each MT maps to its automated mirror + whether `verify_sync_rules.py` covers it live;
  it flags that the two live scripts below are unwritten/owner-blocked. **Running** the procedures
  live still needs staging (below).
- **Migration `0014`** — ✅ **written (step 4) and APPLIED to Supabase (2026-09-25)**:
  `0014_chunk_scope_fail_closed.py`, reversible, round-trip proven by
  `knowledge-base/tests/test_migration_0014_chunk_scope_fail_closed.py`. `alembic upgrade head` moved
  the live DB from `0012` → `0013` → `0014 (head)`; Q-B census was 0 first; 3d/3e live proofs passed
  (see §0 Remaining-work #1). The fail-closed floor is now live on production.
- **CI xfail allow-list (§14.8):** ✅ **done (step 5).** `.github/workflows/ci.yml`'s test-db
  allow-list now names `test_in3_attachment_edit_reembeds_page` (the D2 strict xfail); the dead
  `test_delete_marks_the_active_version_superseded` name was removed, and the test-unit guard now
  allows no xfail (that suite has none). Remove the attachment name when 2.4.1 lands (it will XPASS).

### Open questions status

- **Q-A (enable `enable_knowledge_scope_filtering`).** ✅ **Resolved (step 4): no default change.**
  The step-1 "test env runs True" note was a **misread** — the code default *and* the test-env
  default are **False** (`settings.py:281`; `test_settings.py:56-57`; `conftest.py` never sets it).
  Retrieval tests pass `True` directly to the `HybridRetriever` constructor, not via env. RLS
  fail-closed is the flag-independent security boundary; the app-layer flag stays default-False, its
  flip deferred to PLAN 10.7's operator `.env` (`test_settings.py:49-51`). Eval byte-identical.
- **Q-B (empty-tags backfill before the floor flip).** ✅ **Resolved at deploy (2026-09-25).** The
  census run immediately before `alembic upgrade head` returned **0 active chunks with `tags=[]`**, so
  no backfill was needed; 0014 was then applied and the live 3d proof confirmed empty tags are visible
  to no scope. No auto-mutation occurred.
- **Q-C (substep packaging).** Resolved: executing the §13 series one step at a time.

### Corrections/discoveries from steps 1–2 that affect later steps

- **D4 correction already applied:** `purge_page` **deletes `page_source`** (panels
  `tg-purge`/`tg-classified` as worded said "keep page_source with state classified" — that rested
  on the retired `scope_state`). Steps 2's rule-2 purge and the restore path both rely on
  `page_source` being gone → `get_local_state` returns `None` → first index. Logged in
  `plan-corrections.md`. This resolves the "fix the code to match rule 5" arm of the
  `live-0.5.3-cm-docs` decision-needed in `docs/plan/decisions.md`.
- **Boundary fix to §14.3:** the counting-embedder seam the appendix suggests (monkeypatch
  `ingestion.application.services.build_embedding_provider` from a confluence_sync test) **fails
  `make boundaries`** (cross-feature deep import). The legal seam used instead — reused by steps
  5/6 — is `install_counting_embedder` in `_helpers.py`: patch `build_ingestion_services` in the
  `sync_service` namespace and swap the embedder via `dataclasses.replace`.
- **Step 2 — the gate keys on `matched_labels`, not resolved `tags` (step 3 must preserve this):** a
  two-provider **conflict** page resolves to zero `tags` today yet still carries recognised
  `matched_labels`, so it stays indexed rather than being purged and immediately re-indexed. When
  step 3 drops the conflict branch (conflict resolves to *both* tags), **keep the discriminator on
  `matched_labels`** — the gate stays correct and never churns a legitimately-shared page.
- **Step 2 — three RLS tests + one script test now lean on the empty-tags floor (step 4 must
  revisit):** `test_force_rls_managed_postgres`, `test_reader_rls_reconcile` and `test_retrieval_eval`
  open the orthogonal knowledge-scope axis with the `'*'` wildcard (they assert **source**-axis
  isolation only), and `test_verify_isolation_script` **forces empty tags via SQL** to still hit the
  script's legacy untagged-corpus branch. When step 4 makes the RLS floor fail-closed (D3) and runs
  the Q-B empty-tags backfill, **re-examine all four** — the forced-empty-tags branch may become
  unreachable and the `'*'` opt-outs may need a real per-scope value.
- **Step 2 — `SyncOutcome.action` gained `skipped` (first-seen unlabeled); step 1 added `purged`.**
  No non-test code branches on `.action` (verified), so both are safe additive labels; the
  worker/event surfaces just record them.

---

## 1. Context — why this change

Three facts, all verified in code with file:line, drive this work:

1. **"Remove the last tag" is an active cross-scope leak today, not a cosmetic state.** The chunk
   RLS policy has an *empty-tags-means-public* floor — `chunk_scope_read` includes
   `OR cardinality(tags) = 0` (`knowledge-base/schema/schema.py:116-123`, floor on line 120). Because
   `enable_knowledge_scope_filtering` defaults to **False** (`backend/app/platform/config/settings.py:281`,
   wired `backend/app/main.py:77-88`), the app-layer overlap predicate is skipped and **RLS is the only
   scope gate**. So an active chunk with `tags=[]` is returned to *every* scope (mews, toast,
   operacloud, general). A Toast page whose last tag is removed becomes readable by Mews users today.

2. **Delete/trash/archive only hides, it does not remove.** `deactivate_page`
   (`backend/app/features/ingestion/application/versioning.py:402-416`) sets `is_active=False` and
   leaves every chunk, version, document and registry row on disk. "Hidden" chunks still carry their
   vectors and text.

3. **Restore-from-trash is already broken.** `page_restored`/`page_unarchived` are subscribed and
   route to `sync_page` (`schemas/events.py:22-23`, `event_service.py:93-104`), but the handler takes
   the metadata-only branch (`status_changed` ∉ `_REBUILD_CLASSES`, `sync_service.py:36-43,188-196`)
   and **never re-sets `is_active=True`** — only `stage_and_activate` (`versioning.py:344`) and
   `rollback_to` (`versioning.py:440`) do. A restored page stays dead until a body edit or pipeline
   bump forces a rebuild.

The owner specified eight rules for what the vector store must do on each Confluence change, and
settled four design decisions (§2). Intended outcome: **the database contents exactly match the eight
rules, empty-tags can never be reached on an active chunk, and the RLS floor is fail-closed so the
leak cannot recur.**

---

## 2. Decisions taken (owner-confirmed)

| # | Decision | Effect |
|---|---|---|
| D1 | **Kill rollback (retain 0).** | Rule 6 deletes the page's old `document_version` rows in the same txn as the swap; chunks cascade. `i4-gc` retain changes 2→0; substep `2.4.3` rollback is retired. |
| D2 | **Attachments deferred, tracked by a strict xfail.** | Rule 6 rebuilds on **body + title** now. Attachment-only rebuild is blocked by the version-identity collision (`sync_service.py:44-55`) and belongs to existing substeps **2.2.1** (fingerprint incl. attachment manifest) + **2.4.1** (version uniqueness on document+fingerprint, migration 0011). Write the attachment-swap test now, marked **strict xfail** with reason "needs 2.4.1", so it flips to passing when 2.4.1 lands and nobody forgets. |
| D3 | **Flip the chunk RLS floor to fail-closed.** | Remove `OR cardinality(tags) = 0` from `chunk_scope_read`. Empty tags → visible to no scope. Curated floor (`curated_knowledge_entry_scope_read`, `schema.py:143-151`) stays as-is (operator-authored, intentionally global). |
| D4 | **Drop the conflict rule entirely.** | Two+ platform tags on one page is *legitimate sharing*, enforced by plain overlap (`tags && allowed_scopes`). `[mews,toast]` → visible in mews and toast, not operacloud. `[general,toast]` → visible everywhere (general is seeded into every user's scopes). "Public" is the explicit `general` tag, **never** empty tags. This retires `scope_state`; rewrites what `3.4.1` checks (§7). |

---

## 3. The model after this change (so the rules cohere)

- **Membership** (is the page in the index at all): the page is published/current **and** carries at
  least one recognised knowledge-scope tag from `knowledge-base/config/knowledge_scopes.json`
  (the canonical allowlist — mews, toast, operacloud, general; `classified` is reserved and excluded
  from the offerable set, `knowledge_scopes.py:36,42,69-76`). Folder roots / `source_scope` do **not**
  decide membership (per substep 2.2.4).
- **Visibility** (which scopes can retrieve it): plain overlap `chunk.tags && allowed_scopes`, applied
  identically at the RLS layer and every app read path. **Empty tags overlap nothing → visible to
  nobody** (D3). "Everyone" is expressed as the explicit `general` tag, which is in every user's
  allowed scopes.
- **No conflict concept.** Multiple recognised tags = shared across those scopes.
- **No unreachable empty-active state.** Rules 1/2/5/7 guarantee every active chunk carries ≥1
  recognised tag; D3 makes the floor fail-closed as defence-in-depth if that ever regresses.

---

## 4. Confirmed ground truth (today's behaviour, file:line)

| Area | Today | file:line |
|---|---|---|
| Delete/trash/archive | soft: `is_active=False`, rows stay | `versioning.py:402-416`; route `event_service.py:81-92` → `sync_service.py:263-265` |
| Remove a tag (incl. last) | metadata-only: `chunk.tags` rewritten, rows stay active | `sync_service.py:188-196,268-302`; class `labels_changed` `change_detection.py:193-194` |
| Add a tag (≥1 exists) | metadata-only, same version id, no re-embed | same as above |
| Two provider tags | conflict → zero label tags → (floor) **public** | `knowledge_scope.py:29-30`; `sync_service.py:108-115`; floor `schema.py:120` |
| First tag / first index | full build, all children embedded | `change_detection.py:140-144` → `sync_service.py:145` → `stage_and_activate` |
| Body edit | rebuild, but **reuses** unchanged-chunk vectors via `diff_chunks` | `chunk_diff.py:56-113`; `versioning.py:149-184` |
| Title edit | metadata-only (`title_changed` ∉ rebuild set) | `change_detection.py:189-190`; `sync_service.py:36-43` |
| Attachment edit | metadata-only; cannot stage a new version at same cf_version | `sync_service.py:44-55` |
| Old versions | retain 2 superseded, older cascade-deleted | `_gc_superseded` `versioning.py:378-399` |
| `classified` label | **no delete path** — only a reserved scope name in config | `knowledge_scopes.py:36`; `platforms.py:33` |
| RLS floor | empty tags = visible to all; flag-off = RLS-only | `schema.py:116-123`; retriever `retriever.py:129-147` |
| Read paths use overlap? | yes (`&&`) at RLS + app (flag-on) + curated | `search_repo.py:79-97`; `curated_knowledge_repo.py:25-40` |
| Restore-from-trash | re-stamps `page_status=current`, never re-activates | `sync_service.py:268-302` (no `is_active` write) |
| Whole-page hard-delete helper | **does not exist** | grep clean; only `_gc_superseded` deletes rows |
| FK topology for a purge | `chunk.doc_version_id`→`document_version` ON DELETE CASCADE; `page_restriction.page_id`→`page_source` ON DELETE CASCADE; `document_version.document_id`→`document` **no** cascade; `page_source.active_doc_version_id`→`document_version` UNIQUE deferrable pointer | `models.py:262,174,203,114-118` |

**Purge order (single txn), reused by rules 1/2/7:** null `page_source.active_doc_version_id` →
`DELETE FROM document_version WHERE page_id=X` (chunks cascade) → `DELETE FROM document WHERE
page_id=X` → `DELETE FROM page_source WHERE page_id=X` (page_restriction cascades). `event_ledger`
rows are left as audit history (no FK to page_source).

---

## 5. New/changed code (the shared building blocks)

1. **`purge_page(session, *, page_id)`** — new function in `versioning.py`, next to `deactivate_page`.
   Ordered single-txn delete above. Returns whether a row existed. Exported through the ingestion
   feature root so `confluence_sync` reaches it at the boundary.
2. **Rebuild-trigger widening** — add `ChangeClass.title_changed` to `_REBUILD_CLASSES`
   (`sync_service.py:36-43`). Attachment stays out until 2.4.1 (D2).
3. **Remove vector reuse** — `_resolve_children` (`versioning.py:149-184`) stops consulting
   `diff_chunks` for embedding reuse; every child is contextualised + embedded on every rebuild
   (substep **2.3.1**).
4. **retain 0** — `stage_and_activate` calls `_gc_superseded(..., retain=0)` (or purges the
   just-superseded version) so no superseded rows survive the swap (D1; `versioning.py:254,378-399`).
5. **classified purge** — in `handle_sync_page`, detect the reserved `classified` label explicitly
   (before scope resolution) and call `purge_page`; return a `purged` outcome (rule 7).
6. **last-tag / no-tag purge** — in `handle_sync_page`, after `final_tags` is computed: if an
   already-indexed page ends with no recognised tag → `purge_page` instead of metadata-only (rule 2 +
   membership). First-index with no tag → never indexed (rule 5 requires a tag).
7. **drop conflict** — `resolve_knowledge_scope_tags` (`knowledge_scope.py:24-31`) returns all matched
   recognised tags, no `conflict` flag; delete the conflict branch and the `knowledge_scope_conflict`
   warning (`sync_service.py:108-114`). `scope_state` is not introduced.
8. **RLS floor flip** — new migration `0014_chunk_scope_fail_closed.py` DROP/CREATE `chunk_scope_read`
   without the `cardinality(tags)=0` clause; mirror in `schema.py:116-123` so the harness DDL matches.
   Curated policy untouched.
9. **delete_page → purge** — `handle_delete_page` (`sync_service.py:263-265`) and the `meta is None`
   path (`sync_service.py:87-91`) call `purge_page` instead of `deactivate_page` (rule 1). Restore then
   works for free: with `page_source` gone, a later `page_restored`/sweep sees `local is None` →
   first-index full build (documented + tested, §6 rule 1b).

**Open recommendation (§11 Q-A):** also set `enable_knowledge_scope_filtering=True` so the app read
paths enforce overlap alongside RLS ("every read path uses overlap", D4). Gated behind an eval run
(Rule 11).

---

## 6. Per-rule plan

Format: **today** (file:line) · **change** · **files** · **test-first** (name · level · red/green today
· outcome asserted) · **risk** · **panels** (keep/changed/new).

### Rule 1 — Delete / trash / archive → delete its rows
- **Today:** soft deactivate (`versioning.py:402-416`).
- **Change:** route DELETE_EVENTS and the `meta is None` path to `purge_page` (§5.9).
- **Files:** `versioning.py` (+`purge_page`), `sync_service.py:87-91,263-265`, ingestion root export.
- **Test-first:** `test_in2_delete_page_removes_rows` · **db** · **red today** (rows remain) · asserts
  `chunk`, `document_version`, `document`, `page_source` counts for the page are **0** after a
  `delete_page` job through the fixture gateway. Docstring `panel i2-gone · rule 1`.
- **Rule 1b (restore):** `test_in2_delete_then_restore_full_rebuilds` · **db** · restore after purge →
  `local is None` → fresh version + `embed calls == child count`, page retrievable again.
- **Risk:** irreversible; a spurious trash webhook deletes real work (mitigated: restore re-indexes
  from Confluence, the source of truth). Detection latency if webhook is down (only the 14-day
  complete sweep catches an orphan) — pre-existing.
- **Panels:** `i2-gone` **changed**; `p2-s2_2-close-i2-gone` **changed**; `tg-purge`,`tg-deactivate`
  **new→built**; substep **2.2.4** **changed**.

### Rule 2 — Remove the last relevant tag → delete its rows (same as rule 1)
- **✅ Built (§13 step 2, 2026-09-24).** As-built differs from the spec below: the gate fires on
  `scope_result.matched_labels` **before** `final_tags` (not a post-`final_tags` branch), and the
  tests are `test_tags_remove_last_recognized_label_removes_rows` +
  `test_tags_unrelated_labels_alone_do_not_keep_page` in `test_sync_rules_membership.py`, docstring
  `panel tg-remove · rule 2` (not `tg-purge`). `knowledge_scope.py` was **not** changed. Panel
  `tg-remove` flipped build→built. See §0.
- **Today:** metadata-only, rows stay active with `tags=[]` → **leaks** (floor).
- **Change:** if an indexed page ends with no recognised tag → `purge_page` (§5.6).
- **Files:** `sync_service.py` (post-`final_tags` branch), `knowledge_scope.py`.
- **Test-first:** `test_tags_remove_last_relevant_tag_removes_rows` · **db** · **red today** · asserts 0
  rows for the page after `gateway.set_labels(id, [])` + sync. Docstring `panel tg-purge · rule 2`.
- **Risk:** a transient empty-label read from Confluence would purge a live page; mitigate by trusting
  only the authoritative label list per sync (already fetched fresh) and re-index on restore.
- **Panels:** `tg-remove` **new→built**; `i2-gone` **changed**; substep **2.2.4** **changed**.

### Rule 3 — Remove one relevant tag, another stays → update tags, no re-embed, same version id
- **Today:** already metadata-only and correct (`sync_service.py:188-196,299-301`).
- **Change:** **keep**; lock it in.
- **Test-first:** `test_tags_remove_one_tag_keeps_page_updates_tags_no_reembed` · **db** · **green today
  (guard)** · asserts `active_version(id)` unchanged **and** embed-call counter == 0 **and**
  `chunk.tags` == remaining set. 0.2.8 proof reverts the `chunk.tags` UPDATE (`sync_service.py:299-301`).
- **Panels:** substep **2.2.5** **keep/confirm**; `tg-change`,`tg-retag` **keep**.

### Rule 4 — Add a relevant tag when one exists → update tags, no re-embed, same version id
- **Today:** a **second provider** tag triggers conflict → `tags=[]` → public.
- **Change:** drop conflict (§5.7). Any added recognised tag is unioned in; metadata-only.
- **Files:** `knowledge_scope.py`, `sync_service.py:108-115`.
- **Test-first (behaviour, red today):**
  - `test_tags_add_second_tag_updates_tags_no_reembed` · **db** · both tags present, same version id, 0
    embed calls. (Red today: conflict → `tags=[]`.)
  - `test_tags_shared_page_visible_in_both_scopes` · **db+retrieval** · `[mews,toast]` found in mews and
    toast, **not** operacloud. (Red today: public → also found in operacloud.)
  - `test_tags_general_tag_visible_everywhere` · `[general,toast]` found under every scope.
  - `test_tags_remove_shared_tag_keeps_other_scope` · `[mews,toast]` − toast → mews-only, 0 embed calls.
- **Risk:** changes retrieval visibility of currently-conflicted pages → **eval before/after required**
  (Rule 11).
- **Panels:** `tg-two`,`tg-conflict`,`tg-state` **changed/retired**; `i2-labels`,`2.2.3`,`2.5.1`
  **changed**; recorded in `plan-corrections.md` (§8).

### Rule 5 — First relevant tag on an untagged page → full build
- **◑ Partly built (§13 step 2, 2026-09-24).** The **negative** half — the no-tag→no-index gate — is
  built: a first-seen page with no recognised label returns `SyncOutcome(action="skipped")` and
  writes no rows, proven by `test_in2_untagged_page_never_indexed` (panel `ks-index`). The
  **positive** guard `test_in2_first_relevant_tag_full_build` (first tag → full build, embed calls ==
  child count) is still **deferred to step 6** per §13.
- **Today:** already a full build on first index.
- **Change:** **keep**; ensure the no-tag→no-index gate (zero recognised tags → never first-indexed).
- **Test-first:** `test_in2_first_relevant_tag_full_build` · **db** · **green today (guard)** · version
  created **and** embed-call counter == child-chunk count. Plus `test_in2_untagged_page_never_indexed`
  (no rows when first-seen with no recognised tag).
- **Panels:** `ks-index` **keep**; substep **2.2.4** membership clause **changed**.

### Rule 6 — Edit (body / title / attachment) → rebuild whole page, embed every chunk, reuse no vector
- **Today:** body reuses vectors (`diff_chunks`); title = metadata-only; attachment can't version;
  retain 2.
- **Change:** remove reuse (§5.3, substep **2.3.1**); add `title_changed` to rebuild set (§5.2); retain
  0 (§5.4, D1). Attachment deferred (D2).
- **Files:** `versioning.py:149-184,254`, `sync_service.py:36-43`.
- **Test-first:**
  - `test_in3_body_edit_reembeds_every_chunk_no_reuse` · **unit/db** · **red today** (reuse → calls <
    count) · embed-call counter == child count after a one-word edit.
  - `test_in3_title_change_reembeds_every_chunk` · **db** · **red today** (title=metadata-only) · embed
    calls == child count after a rename.
  - `test_in3_rebuild_deletes_old_version_rows_immediately` · **db** · **red today** (retain 2) · after
    one edit, superseded/old `document_version` rows for the page == 0, old chunks == 0.
  - `test_in3_attachment_edit_reembeds_page` · **db** · **strict xfail** reason `"needs 2.4.1"` (D2) ·
    new version + full re-embed on an attachment-only change; flips to pass when 2.4.1 lands.
- **Risk:** full re-embed on every rename raises embedding cost (accepted per 2.3.1 — title is in the
  contextualised text, so correctness requires it); retain 0 removes the safety net (D1) — recovery is
  a fresh re-index.
- **Panels:** `i3-embed` **changed→built**; `i2-rebuild` **changed**; `i4-gc` **changed** (retain 0);
  `2.4.3` rollback **retired**; substep **2.3.1** **changed→built**; attachment → **2.2.1 / 2.4.1**.

### Rule 7 — Add `classified` → delete the rows
- **Today:** no path; `classified` is only a reserved config scope.
- **Change:** detect the `classified` label in `handle_sync_page` → `purge_page` (§5.5).
- **Test-first:** `test_in2_classified_label_removes_rows` · **db** · **red today** · 0 rows after
  `gateway.set_labels(id, ["classified", ...])` + sync.
- **Risk:** the config's reserved value must equal the Confluence label spelling — assert against
  `knowledge_scopes.json`.
- **Panels:** `i2-gone` **changed**; `tg-classified` **new→built**; substep **2.2.4** **changed**.

### Rule 8 — A page never touches another page's rows
- **Today:** already per-page.
- **Change:** **keep**; add an explicit invariant guard.
- **Test-first:** `test_in2_change_never_touches_other_pages_rows` · **db** · **green today (guard)** ·
  index A and B; edit **and** delete A; assert B's chunk ids, embeddings, tags, version id are
  byte-identical before/after.
- **Panels:** `vd-swap` **keep**.

### Cross-cutting — RLS floor fail-closed (D3) + read-path overlap (D4)
- **Change:** migration `0014_chunk_scope_fail_closed.py` + `schema.py` mirror (§5.8).
- **Test-first:** `test_sec_empty_tags_visible_to_no_scope` · **db** · **red today** (floor = public) ·
  as `rag_reader`, an active chunk with `tags=[]` returns for **no** scope value. Plus
  `test_sec_read_paths_use_overlap_not_equality` confirming dense/keyword/curated/parent all filter by
  `&&`. Docstring `panel 3.4.1 · D3/D4`.
- **Risk:** any legitimately-global content must now carry the explicit `general` tag; a backfill check
  may be needed before deploy (§11 Q-B).
- **Panels:** substep **3.4.1** **changed** (empty-tags = private + overlap, not public floor).

---

## 7. `scope_state`: retire it

With no conflict state (D4), `scope_state` would only ever hold `ok` → no job. **Drop `scope_state`
from the plan entirely** (no column, no RLS state predicate, no `tg-state` work). **`3.4.1`** now
checks: *empty tags are visible to no scope (fail-closed), and every read path (dense, keyword,
curated, parent) plus the RLS policy filter by `tags && allowed_scopes` overlap, not equality* —
covered by the Rule-4 visibility tests + `test_sec_*`.

---

## 8. Design-page corrections — `docs/Final_docs/0.4-design-review/plan-corrections.md` (new)

One entry per panel/substep the decisions move, each marked **changed/retired** with the reason:
`tg-two` (conflict→legitimate sharing), `tg-conflict` (retired), `tg-state`/`scope_state` (retired),
`i2-labels` (overlap visibility, empty=private), `2.2.3` (labels→tags, no conflict state), `2.5.1`
(shared tags), `i2-gone` (delete not deactivate; classified/last-tag purge), `i4-gc` (retain 0),
`2.4.3` (rollback retired), `3.4.1` (fail-closed floor), `2.3.1` (no reuse). Flip the `today` lines on
`obi-rag-system-flow.html` and the statuses on `obi-action-plan.html` when each substep lands.

---

## 9. Scripts

### `backend/scripts/page_state.py <page_id> [marker]` (new — manual testing)
Read-only session. Prints for one page: **active** and **inactive** chunk counts; the distinct `tags`
on its active chunks; `page_status` and `is_active` summary (*replaces* the requested `scope_state`,
which is being retired — §7, flagged so the substitution is explicit); every `document_version` id
with its `state` and `cf_version`; and, if `marker` is given, the count of the page's chunks whose
`display_content`/`retrieval_content` contains the marker word. No writes, no network. Uses the
read-only pattern from the tests' `_helpers.read()`.

### `backend/scripts/verify_sync_rules.py` (new — live, staging)
Refuses the offline fixture gateway (mirror `run_reconciliation_once.py:41-50`). Runs the Confluence
cases against staging with the owner's test pages, printing pass/fail per rule from `page_state`
readings: add first tag (5), add second/shared tag (4), remove one tag (3), remove last tag (2), edit
body+title (6), delete+restore (1), add classified (7). **Covers manual tests MT-1..MT-7** (§10).
Does **not** cover the attachment case (blocked, D2) or the RLS-floor unit assertion (db-only). Output
goes in the PR per CLAUDE.md live-level rule.

---

## 10. Tests, proof, coverage, CI

**One automated test per rule + manual mirror.** Every rule's fixture-gateway test runs with **no
Confluence** (`FixtureConfluenceGateway` + db harness, `conftest.py` + `_helpers.py`).
`docs/Final_docs/sync-rules/manual-tests.md` (new) lists MT-1..MT-7 as human procedures, each mapped
to its automated test name **and** whether `verify_sync_rules.py` covers it live. Assertions are
**outcomes, never code paths** — "0 chunk rows for this page", "same version id and 0 embed calls",
"embed calls == child count", "found in mews, not in operacloud".

**Embed-call counter.** `FakeEmbeddingProvider` (`embeddings_client.py:55`) has no counter. Add a thin
counting wrapper (increment per text in `embed`) as a test fixture, reused by rules 3/4/5/6.

**Prove each test real (the 0.2.8 way) → `docs/Final_docs/sync-rules/test-proof.md` (new).** For each
test: revert the one line it guards → run → **red** (record the reason), restore → **green**. Red-today
tests (1,2,4,6,7,RLS) already fail on current code — record that as the first half of the cycle;
green-today guards (3,5,8) use the revert step. Format copied from
`docs/Final_docs/0.2-agent-quality/test-writer-check.md`.

**Coverage map → `docs/Final_docs/0.5-regression-tests/coverage-map.md` (edit in place).** One row per
test in the existing columns `| panel | title | test file | test name | level | green |`. Panels:
`i2-gone`, `tg-purge`, `tg-remove`, `tg-retag`, `tg-add`, `i2-labels`, `ks-index`, `i3-embed`, `i4-gc`,
`i2-gone`(classified), `vd-swap`, `3.4.1`.

**CI (0.5.4) + xfail bookkeeping.** All tests land in `make test-unit` / `make test-db`, gated by the
`obi four-level check (0.5.1)` status (`.github/workflows/ci.yml`). Add the attachment strict-xfail
(`test_in3_attachment_edit_*`) to the workflow's xfail allow-list (the `grep -vF` lines) alongside the
existing `test_delete_marks_the_active_version_superseded`; when substep **2.2.4** retires that older
xfail, remove it from the allow-list (it will XPASS → CI red otherwise).

**Rules that cannot be tested automatically (with reason).**
- **Rule 6 attachment rebuild** — testable only as a **strict xfail** until 2.4.1 exists (version
  identity can't represent an attachment-only change today).
- **Live webhook delivery / detection latency** (signing gap; 14-day complete-sweep timing) — not
  unit-testable; covered by `verify_sync_rules.py` against staging, reported in the PR.

---

## 11. Open questions (recommended defaults)

- **Q-A — enable `enable_knowledge_scope_filtering`?** The app layer only applies overlap when this
  flag is **on** (default off; RLS-only today). **Recommend: turn it on** so both layers enforce
  overlap, **gated behind an eval before/after run** (Rule 11). If the eval regresses, ship RLS
  fail-closed alone and keep the flag off.
- **Q-B — backfill of existing empty-tags active chunks before the floor flip.** After D3, any page
  relying on empty-tags=public goes dark. **Recommend:** a one-off audit (list active chunks with
  `tags=[]`) on staging/prod before deploy; re-tag legitimately-global pages with `general`. Report the
  list in the PR; do not auto-mutate.
- **Q-C — substep packaging.** Spans 2.2.4, 2.2.5, 2.3.1, i2-gone, i4-gc, 3.4.1 and touches 2.2.1/2.4.1
  (pointer). **Recommend** the ordered series in §13, one substep + ledger entry at a time.

---

## 12. Deliverables (files created/edited on execution)

**New docs:** `docs/Final_docs/sync-rules/plan.md` (this file), `.../manual-tests.md`,
`.../test-proof.md`; `docs/Final_docs/0.4-design-review/plan-corrections.md`.
**Edited docs:** `docs/Final_docs/0.5-regression-tests/coverage-map.md`; design page
`obi-rag-system-flow.html` + `obi-action-plan.html` statuses/`today` lines; `docs/Final_docs/ledger.md`
+ `progress-log.md` (append per substep); relevant `docs/Final_docs/ingestion/` component docs.
**New scripts:** `backend/scripts/page_state.py`, `backend/scripts/verify_sync_rules.py`.
**New migration:** `knowledge-base/migrations/versions/0014_chunk_scope_fail_closed.py` (+ downgrade).
**Code:** `versioning.py` (`purge_page`, retain 0, no-reuse), `sync_service.py` (rebuild set, purge
branches, classified, drop conflict), `knowledge_scope.py` (drop conflict), `schema.py` (RLS mirror),
ingestion feature root export, `.github/workflows/ci.yml` (xfail allow-list), test files + counting
embedder fixture.

---

## 13. Execution order (each stops at green + ledger entry)

1. ✅ **DONE (2026-09-24)** — **purge_page + rule 1 + rule 7 + restore** (i2-gone; delete/classified
   purge; restore full build). See §0 and the ledger 2.2.4 entry.
2. ✅ **DONE (2026-09-24)** — **rule 2 + membership gate** (last-tag purge + no-tag skip; tg-remove,
   ks-index). See §0 and the ledger 2.2.4 (step 2) entry.
3. ✅ **DONE (2026-09-24)** — **drop conflict + rule 4 visibility + rule 3 guard** (retire
   scope_state; overlap tests). See §0 and the ledger 2.2.4 (step 3) entry.
4. ✅ **DONE (2026-09-24)** — **RLS floor fail-closed (migration 0014) + read-path overlap tests**
   (3.4.1); Q-A resolved (no default change). See §0 and the ledger 2.2.4 (step 4) entry.
5. ✅ **DONE (2026-09-24)** — **rule 6: no-reuse (2.3.1) + title rebuild + retain 0 (i4-gc)**;
   attachment strict-xfail (D2), rollback retired (D1). See §0 and the ledger 2.3.1 entry.
6. ✅ **DONE (2026-09-24)** — **rule 5 positive guard + rule 8 invariant**; finalised coverage-map,
   test-proof, created manual-tests; flipped design-page statuses. Live legs + target-line
   reconciliation + action-plan checkboxes remain owner-blocked. See §0 and the ledger 2.2.4 (step 6).

Before each: read the named panels + the component doc + ledger (CLAUDE.md). After each:
`make check` green, migration reversible, security review for endpoint/LLM/RLS touches, ledger +
progress-log entries, design-page `today` line flipped.

---

## 14. Execution appendix — exact APIs, DDL and formats (so this file stands alone)

> **Path caveat:** older proof docs (e.g. `0.2-agent-quality/test-writer-check.md`) cite
> `apps/automation/...` / `apps/web/...`. The tree has since moved. Trust the **live** layout:
> backend Python is under `backend/app/...`, tests under `backend/app/features/<feature>/tests/`.

### 14.1 DB-test harness (drive the real worker with no network)

All confluence_sync DB tests use `pytestmark = pytest.mark.db` at module top, the `gateway`/`settings`
fixtures from `backend/app/features/confluence_sync/tests/conftest.py` (autouse `_db_isolation`
truncates between tests), and the helpers in `backend/app/features/confluence_sync/tests/_helpers.py`:

```python
# _helpers.py public surface (import from ._helpers)
index_page(gateway, settings, page_id, version)   # seed a page via the REAL sync path
enqueue_sync(page_id, cf_version, key)             # push a sync_page job
enqueue_delete(page_id, status, key)               # push a delete_page job
run_worker(gateway, settings, owner="test")        # drain(...) up to 50 jobs
# worker.run_once(gateway, settings, owner=...) runs exactly one job (used by index_page)
read()                                             # fresh read-only Session (use as: `with read() as s:`)
active_version(page_id) -> DocumentVersion | None  # via PageSource.active_doc_version_id
active_versions_count(page_id) -> int              # DocumentVersion rows in state=active
active_child_chunks(page_id) -> list[Chunk]        # is_active AND kind=child
child_chunks_for_version(doc_version_id) -> list[Chunk]   # all child rows of a version, any is_active
restricted_principals(page_id) -> set[str]         # persisted ACL
count_versions(page_id) -> int                     # all DocumentVersion rows for the page
```

**Fixture gateway** `FixtureConfluenceGateway`
(`backend/app/platform/clients/fixture_confluence_client.py`) — in-memory mutators to express each
scenario (all keyed by int page_id, fixtures never written):

```python
gateway.set_version(page_id, version)      # advance cf version -> triggers a body-edit rebuild path
gateway.set_status(page_id, status)        # "current" | "archived" | "trashed" | "deleted" | "draft"
gateway.set_labels(page_id, [ ... ])       # REPLACES the page's label set (tag add/remove/last/classified)
gateway.set_restrictions(page_id, [ids])   # page read-restriction principals
gateway.set_group_members(group_id, [ids])
gateway.hide(page_id)  / gateway.unhide(page_id)   # get_page_meta/get_page -> None (deletion/lost access)
gateway.set_attachment_content(download_link, data|None)
```

**Scenario recipes (map rules → gateway calls):**
- Rule 1 delete: `index_page(...)`; `gateway.set_status(id,"trashed")` **or** `gateway.hide(id)`;
  `enqueue_delete(id,"trashed",key)`; `run_worker(...)`; assert **0** rows (see 14.2).
- Rule 1b restore: after the delete, `gateway.set_status(id,"current")` / `gateway.unhide(id)`;
  `enqueue_sync(id, version, key)`; `run_worker(...)`; assert a fresh version + full re-embed.
- Rule 2 last tag / Rule 7 classified: `gateway.set_labels(id, [])` (or `["classified"]`);
  `enqueue_sync(...)`; `run_worker(...)`; assert 0 rows.
- Rule 3/4 tag change: `gateway.set_labels(id, [<new set>])`; `enqueue_sync(...)`; `run_worker(...)`;
  assert `active_version(id)` unchanged + counter (14.3) shows 0 embed calls + `chunk.tags` updated.
- Rule 6 body edit: `gateway.set_version(id, v+1)` (a per-version fixture snapshot with changed body);
  Rule 6 title: same with a changed title; assert counter `.texts == len(active_child_chunks(id))`.

### 14.2 Asserting on rows (outcome, never code path)

```python
from sqlalchemy import func, select
from schema.models import Chunk, DocumentVersion, Document, PageSource
with read() as s:
    assert s.scalar(select(func.count()).select_from(Chunk).where(Chunk.page_id == pid)) == 0
    assert s.scalar(select(func.count()).select_from(DocumentVersion).where(DocumentVersion.page_id == pid)) == 0
    assert s.get(Document, ...) is None   # by page_id lookup
    assert s.get(PageSource, pid) is None
```
For "no reuse / embed every child" assert on the **counter** (14.3), not on chunk contents. For
"unchanged" (rules 3/4) assert `active_version(pid).id == version_before` and `counter.calls == 0`.

### 14.3 Counting embedder (there is no built-in counter)

`FakeEmbeddingProvider(dim, model="fake")` (`embeddings_client.py:55`) only exposes `dim`, `model`,
`embed(texts)->list[list[float]]`. Add a thin counting wrapper as a test fixture and inject it by
monkeypatching the build seam `build_embedding_provider` in
`backend/app/features/ingestion/application/services.py` (called by `build_ingestion_services`, which
`handle_sync_page` invokes each run):

```python
class CountingEmbedder:
    def __init__(self, inner):
        self.inner, self.model, self.dim = inner, inner.model, inner.dim
        self.calls = 0   # embed() invocations
        self.texts = 0   # total texts embedded == children (re)embedded this build
    def embed(self, texts):
        self.calls += 1; self.texts += len(texts)
        return self.inner.embed(texts)

# in the test: monkeypatch.setattr(services_mod, "build_embedding_provider",
#     lambda settings: counter)  where counter = CountingEmbedder(FakeEmbeddingProvider(dim=settings.embedding_dim))
```
Tests run with `EMBEDDING_PROVIDER=fake`, `EMBEDDING_DIM=256`, `CONTEXTUALIZATION_ENABLED=false`
(root `backend/conftest.py`). With reuse removed and contextualization off, a rebuild calls `embed`
once with all children — assert on **`counter.texts == child count`**, not `counter.calls`. For a
metadata-only path assert `counter.calls == 0`.

### 14.4 RLS floor flip — exact current vs target DDL

Current `chunk_scope_read` (`knowledge-base/schema/schema.py:116-123`, `apply_chunk_scope_rls`):
```sql
CREATE POLICY chunk_scope_read ON chunk AS RESTRICTIVE FOR SELECT
USING (current_setting('app.allowed_knowledge_scopes', true) = '*'
   OR cardinality(tags) = 0                                             -- << the public floor (remove)
   OR tags && string_to_array(current_setting('app.allowed_knowledge_scopes', true), ','));
```
Target (fail-closed — drop only the middle line; keep the `'*'` opt-out used by the parent-expansion
path, `retriever.py:247-259`, and eval):
```sql
CREATE POLICY chunk_scope_read ON chunk AS RESTRICTIVE FOR SELECT
USING (current_setting('app.allowed_knowledge_scopes', true) = '*'
   OR tags && string_to_array(current_setting('app.allowed_knowledge_scopes', true), ','));
```
Effect: empty tags → `tags && …` is false → denied; unset GUC → `string_to_array(NULL,',')` → NULL →
denied (already fail-closed). **Leave `apply_curated_scope_rls` (schema.py:143-151) unchanged** (D3).
Edit `apply_chunk_scope_rls` in `schema.py` to the target DDL (so the test harness `apply_*` matches),
and add migration `0014_chunk_scope_fail_closed.py`: **upgrade** DROP+CREATE the floor-less policy,
**downgrade** DROP+CREATE the current (with-floor) policy. Both are pure `conn.execute(text(...))`,
mirroring the existing `apply/drop_chunk_scope_rls` shape. RLS is `ENABLE`d but **NOT** `FORCE`d
(ADR-supabase-postgres-store-without-force-rls): the test must read as the non-owner `rag_reader` role for the policy to apply.

### 14.5 Naming + docstring convention (obi-test-writer)

- Name `test_<stage>_<behavior>`; the owner's spec fixes the stages used here: `in2` (delete/index),
  `in3` (rebuild/embed), `tags` (tag ops), `sec` (RLS/security). Match the prevailing prefix of
  sibling tests already in the target test file (grep first — a historical `in2→i2` rename exists;
  the docstring, not the prefix, is the source of truth for which panel is protected).
- Docstring: **line 1** `panel <id> · rule <n>` (e.g. `panel i2-gone · rule 1`); **line 2** the exact
  acceptance sentence being proved. Every regression test names the design panel it protects.

### 14.6 Coverage-map row format (`docs/Final_docs/0.5-regression-tests/coverage-map.md`, edit in place)

Columns: `| panel | title | test file | test name | level | green |`. Test file path is relative to
`backend/` (e.g. `app/features/confluence_sync/tests/test_sync_rules_delete.py`); multiple files
`; `-separated; extra tests summarised `(+N more: nameA, nameB)`; `level` ∈ unit|database; `green` =
`yes`/`no`. Example real row:
```
| `i4-gc` | Garbage collect old versions | app/features/ingestion/tests/test_versioning_gc.py | test_i4_gc_keeps_the_two_most_recent_superseded_versions | database | yes |
```

### 14.7 Proof format (`docs/Final_docs/sync-rules/test-proof.md`, new — the 0.2.8 method)

Per test: run unmodified → revert the **one** line its docstring names → rerun (confirm **red** for the
stated reason) → restore → rerun (confirm **green**); `git status --short` clean after. For red-today
tests (1,2,4,6,7,RLS) the "fails today" run **is** the red half — record it, then record green after
the change. One `### N — <panel>, <level>` block per test with a 3-row table:
```
| Step | Command | Result |
|---|---|---|
| Fails today / Passes today | uv run pytest <path>::<test> -v | FAILED (reason) / PASSED |
| Guard reverted / stub added | same | PASSED / FAILED |
| Restored | same | PASSED; git status clean |
```
Commands run with `DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag` exported
(overrides the root `.env`'s Supabase URL — never edit `.env`).

### 14.8 CI xfail-allowlist mechanics (`.github/workflows/ci.yml`)

Both the `make test-unit` and `make test-db` steps run with `PYTEST_ADDOPTS: "-rsxX"` and a skip-guard
that fails the job on any `SKIPPED`, any `XPASS`, or any `XFAIL` **except** an allowlisted name. The
allowlist is a single `grep -vF` per step (currently only the tg-deactivate test):
```bash
unexpected="$(grep -E '^XFAIL ' "$log" | grep -vF 'test_delete_marks_the_active_version_superseded' || true)"
```
To add the attachment strict-xfail (D2), extend **both** steps (unit ~line 89, db ~line 114) to also
exclude it, e.g.:
```bash
unexpected="$(grep -E '^XFAIL ' "$log" \
  | grep -vF 'test_delete_marks_the_active_version_superseded' \
  | grep -vF 'test_in3_attachment_edit_reembeds_page' || true)"
```
Mark that test `@pytest.mark.xfail(reason="needs 2.4.1", strict=True)`. When substep 2.2.4 lands and
retires the tg-deactivate xfail, remove **its** `grep -vF` line (it will XPASS → CI red otherwise).

## 15 · Open follow-up: meerdere scopes per vraag (POS + PMS tegelijk) — eerst beslissen, dan bouwen

Jasper's veldvraag (2026-10-01): een property draait vaak een POS én een PMS tegelijk (bijv. Toast +
Opera Cloud), maar een vraag draait vandaag onder precies één platform-scope — het token en de
`/chat`-request dragen één `knowledge_scope`-string, die `resolve_allowed_scopes` aanvult met
`obi-general-test`. De datalaag kan het al (pagina's dragen meerdere tags, de zoeklaag filtert op een
scopes-*set*), dus de uitbreiding zit in de token-claim en de gate, niet in de opslag.

**Eerst kort beslissen hoe we dit exact willen** voordat er iets gebouwd wordt — de open keuzes:
1. Lijst in de token-claim (`knowledge_scopes: [toast, operacloud]`) vs. één scope met voorrangsregel.
2. Zoekgedrag bij een lijst: één gefuseerde zoekronde over de unie van scopes, of per scope en fuseren.
3. Wat de citations/trace tonen als bronnen uit verschillende scopes komen.
4. Backwards-compat: blijft de enkelvoudige claim geldig (lijst van één) zodat bestaande platforms niet breken.

Daarna pas implementeren: claim + gate + `resolve_allowed_scopes` een set laten accepteren, met test
per keuze. Status: **BESLIST (owner, 2026-10-05)** — alle vier de keuzes vastgelegd in
`docs/Final_docs/plan.md` §D.13 (drie-slots-token, één gefilterde zoekronde, slot-attributie in de
bronnen, oude tokens = één gevuld slot); de bouw is roadmap-stap 5.

> **Update 2026-10-09 — gesuperseerd voor routing.** Owner koos **Option A (directed source→target
> routing)**. Het slot-model hierboven blijft geaccepteerd maar routet niet meer; zie de sectie
> **"Volgende stap — Option A: directed-connection retrieval routing"** onderaan dit document
> (gefaseerd plan + override-map + ADR-directed-source-target-routing-labels).

### 15.1 · Harde voorwaarde vóór de multi-scope bouw: eerst een rotsvast testfundament

Dit is géén kleine wijziging: meerdere scopes per vraag (bijv. Toast + Mews/Opera tegelijk) raakt
meer dan de token-claim alleen. Bekende implicaties, elk met eigen testbehoefte:
- **Autorisatie/RLS** — de scopes-set in de authorization context stuurt élke databaseread (search,
  rerank-tekst, parent-expansie, curated lookup); een lijst mag nooit breder resolven dan het token.
- **Isolatie** — een Toast+Opera-gebruiker mag nóóit een Mews-only pagina zien; de adversariële
  kant (gemanipuleerde body-scope, onbekende scope in de lijst, lege lijst) moet fail-closed blijven.
- **Retrieval-gedrag** — fusie/ranking over de unie van scopes, deduplicatie als een pagina in twee
  scopes leeft, citations en trace bij bronnen uit verschillende scopes.
- **Caching & limits** — antwoordcache-keys en rate-limits zijn vandaag per (principal, scope);
  een lijst verandert de key-ruimte.
- **Eval** — rule 11 geldt: geen retrieval-wijziging zonder voor/na-cijfer op de gold set.

**Afspraak (owner, 2026-10-02): vóór er ook maar één regel multi-scope-code geschreven wordt, komt
er een rock-solid testsuite** — eerst de huidige single-scope contracten als regressievloer
vastklikken, daarna red-first tests voor het besliste multi-scope-gedrag (§15-keuzes 1–4). De
testscope zelf wordt met de owner afgestemd (vragenronde) en als testplan hier vastgelegd.

### 15.2 · Het testplan (owner-afgestemd 2026-10-02): de regressievloer vóór multi-scope

> **2026-10-05 — waar dit nu leeft:** de golven 0–4 hieronder zijn als substappen 4.1–4.5 in de
> roadmap opgenomen (`docs/Final_docs/plan.md` §A, stap 4); golf 5 is vervangen door roadmap-stap 5
> (het volledige multi-integratie-ontwerp, §D aldaar) + stap 6 (de agent-gebouwde testuitbreiding).
> De §15-keuzes 1–4 worden beslist in het beslismemo van §D.1. Dit blok blijft staan als record van
> de owner-afspraak; de roadmap is leidend voor de volgorde.
>
> **Status 2026-10-05:** golf 0 (= substap 4.1, baselines in `docs/plan/baseline.md`) en golf 1
> (= substap 4.2, audit + 25 gap-dichtende tests + de G14 scope-waarde-fix in
> `docs/Final_docs/4-test-foundation/`) zijn **afgerond**.
>
> **Status 2026-10-05 (later die dag):** golf 2 (= substap 4.3) is **gebouwd** —
> `backend/scripts/webhook_rules_live.py`, de permanente webhook-pad-runner (alleen echte
> Confluence-REST-mutaties, pollt de DB tot de gedeployde keten het werk deed, event-ledger-bewijs
> per leg, rule-8-getuige, labels + body hersteld in een `finally`); de **live run zelf is
> owner-only** (zie de ledger-entry 4.3 "need from you"). Golf 4 (= 4.5) is als before-gate
> bevestigd (byte-identiek aan de 4.1-baseline). Golf 3 (= 4.4) is de owner's browsercheck
> (ledger "4.4 · need from you"); de Playwright-automatisering ervan blijft roadmap-stap 6.
> Ook 4.6–4.8 (verify-state-staart) zijn klaar: live proofs read-only herbevestigd, de laatste
> vier `unverified`-panelen geflipt, en de 2.2.4/2.3.1-checkboxes getickt op het 2026-09-30-bewijs.
>
> **Status 2026-10-05 (slot): STAP 4 VOLLEDIG AFGEROND.** De live run van `webhook_rules_live.py`
> is owner-ordered uitgevoerd en **alle 8 regels PASS** door het echte webhookpad (output
> `backend/webhook-rules-live-run.txt`; de eerste run ving een echte restore-API-bug, gefixt —
> ledger "4.3-addendum"). De owner's browserchecks (golf 3 / 4.4) zijn **gedaan en geslaagd**;
> de screenshot-bewijzen staan in `docs/Final_docs/4-test-foundation/browser-checks-4.4/`.
> Bonus: X1 (Supabase-guards op de 0010/0014-downgrades) is besloten en gebouwd (4 hermetische
> tests; kb-suite 49). Volgende: roadmap-stap 5 — het multi-integratie-ontwerp (§D), op go-ahead.
>
> **Status 2026-10-05 (avond): stap 5 is gestart — §D.0 (de scope-restamp-fix, findings A+B van
> 2026-10-03) is AF** (commit `41fc248`, ledger "D.0"): de handler vergelijkt `cmd.scopes` met de
> gestempelde tags en herstempelt metadata-only; het B-lek is op RLS-niveau dicht bewezen onder
> `rag_reader`; beide sentinel-tests bewust red-first omgeklapt; `make check` + eval groen. X2 is
> ook af en gecommit (`f480b32`).
>
> **Status 2026-10-05 (slot): de §15-keuzes 1–4 zijn BESLIST** in de owner-beslisronde van
> `docs/Final_docs/plan.md` §D.13: (1) token = company-ID + drie slots (POS/PMS uit Data Hub,
> Accounting uit Base; elk slot één systeem of leeg; oude tokens blijven geldig als één gevuld
> slot); (2) één gefilterde zoekronde over general + gevulde slots + de paren die het bedrijf
> écht heeft; (3) elk resultaat toont welk slot het binnenliet; (4) backwards-compat = het
> één-gevuld-slot-pad. Ook beslist: launch-allowlist Toast(POS)/Mews(PMS) — een gevuld slot
> buiten de allowlist verbergt Obi, een leeg slot nooit; archived/draft blijft eruit met purge
> bij statusverlies (rule bevestigd, as-built voldoet); never-bend rule 8 blijft (max 2 extra
> reads). Het beslismemo-deel van §D.1 is daarmee gesloten; de bouw volgt de roadmap.

Owner-keuzes uit de vragenronde: (1) eerst de **regressievloer** — het huidige single-scope gedrag
vastklikken; multi-scope red-first tests wachten op de §15-beslissing; (2) contract **nog niet
beslist** — er komt eerst een kort beslismemo; (3) alle vier de niveaus: unit+database (CI-gate),
een permanent live-webhook-script, browser (Playwright) én eval/gold-set; (4) diepste dekking op
**security & isolatie + sync-correctheid + "werkt het écht"** (end-to-end realiteit boven mocks).

De golven, in volgorde:

- **Golf 0 — baselines bevriezen (vóór élke codewijziging).** `make eval` per stage draaien en de
  cijfers vastleggen (rule 11 heeft een "voor" nodig); `make check`-tellingen noteren
  (nu: boundaries 0 · backend 1015+1xfail · kb 45).
- **Golf 1 — dekkingaudit + gaten dichten (unit + database, de CI-vloer).** Stap 1: audit die élk
  contract mapt op een bestaande test (obi-auditor, lezen-alleen): de 8 sync-regels, event-dedup
  (payload_hash + delivery_id), idempotency-keys-per-event (f8098d0), de autorisatiecontext
  (onbekende scope → 400 vóór search; body/token-conflict → genegeerd + gelogd; elke read onder
  dezelfde context — search, rerank-tekst, parent-expansie, curated), RLS onder béíde rollen,
  antwoordcache-keys per (principal, history, scope), rate-limits. Output: een gatenlijst.
  Stap 2: elk gat red-first dichten met /obi-test-writer. Adversariële diepte verplicht:
  vervalste/afwijkende body-scope, onbekende scope, lege scope, cross-tenant-leespoging onder
  rag_reader, RLS-settings gemanipuleerd binnen een sessie.
- **Golf 2 — het live-webhook-script permanent maken.** De sessie-runner (webhook_rules_live.py,
  alle 8 regels via échte Confluence-mutaties → Forge → Railway → worker, met de Mews-pagina als
  byte-identieke getuige) promoveren naar `backend/scripts/` met dezelfde waarborgen als
  verify_sync_rules.py: STAGING-ONLY-stempel, --yes, labels hersteld in een finally, één commando,
  plakbare output. Dit is de "werkt het écht"-knop die de owner zelf kan indrukken.
- **Golf 3 — browser (Playwright).** Tegen de stub-hostpagina's (bestaande conventie, deterministisch):
  toast-host ziet toast-content; mews-host kan een toast-only pagina níét zien; none-host → nette
  weigering; multi-host = het besliste gedrag (wacht dus deels op §15).
- **Golf 4 — eval.** De gold set per stage als voor/na-poort bij elke retrieval-aanraking; bij
  multi-scope komen er gemengde-scope goldvragen bij (Toast-vraag met Opera-token enz.).
- **Golf 5 — multi-scope red-first.** Geblokkeerd tot de §15-keuzes beslist zijn; start met het
  beslismemo, daarna de falende tests die het besliste contract vastleggen, pas dan implementatie.

Werkwijze per golf: één golf per keer, /obi-change-procedure, ledger-entry bij afronding.

---

## Volgende stap + afsluitende owner-items (toegevoegd 2026-10-09)

**Context.** Op 2026-10-09 is de frontend live gezet op Railway (substep **8.4.3**; zie ledger + progress-log). `obi.js` draait op `https://obi-web-production.up.railway.app/obi.js`. Hieronder de **volgende stap** voor retrieval-routing en daarna de **twee afsluitende owner-items**.

### Volgende stap — Option A: directed-connection retrieval routing (DE volgende stap)

**Dit is DE volgende stap** (toegevoegd 2026-10-09; owner koos **Option A** boven het membership-slot-model, bron: `~/Downloads/Obi page routing Option A ... how Obi picks pages.html`). Het **overschrijft** de slot-/`context.slots`-routing uit `plan.md` §D voor het *routing-gedeelte* (zie Override-map in Stage 0). De acht sync-regels, de RLS-locks 0–2 (company/source-isolatie, `source_scope`) en regel 8 (max twee extra reads) blijven **ongewijzigd** — Option A verandert alleen *welke pagina's* een vraag mag zien, niet de beveiligingsgrenzen.

> **Build status (bijgewerkt 2026-10-12).** **Stage 0 ✅** (commit `0209579` — ADR-directed-source-target-routing-labels + decisions.md + override-map). **Stage 1 ✅** (commit `42448cb` — 4 nieuwe panels `mi-route`/`mi-labels`/`mi-session`/`mi-hardfilter`, 6 bijgewerkt, brief 203→207; action-plan **Phase 9** toegevoegd, substeps `9.1.1`–`9.6.1`; `make check` groen). **Stage 2 ✅** (substep `9.1.1`, commit `099caef` — catalogus-resolver `resolve_system`/`build_labels`/`is_valid_label`; `make check` groen: backend 1265+1xfail · kb 51 · boundaries 0). **Stage 3 ✅** (substep `9.1.2`, commit `8746e71` — ruwe `labels`-kolom + migratie 0016 + restamp-threading; de labels-RLS blijft inert tot 9.4.1 om de retrieval niet te breken; `make check` groen: backend 1270+1xfail · kb 53 · boundaries 0). **Stage 4 ✅** (substep `9.2.1` — `chat_session`-tabel + migratie `0017` gebonden aan geverifieerde `token_subject`+`company_id`; `start_chat_session` lost op + slaat één keer op, `load_chat_session` hergebruikt de rij zonder catalogus-call (regel 8); `build_connection_block` nieuw in `prompt.py`; `make check` groen: backend 1275+1xfail · kb 53 · boundaries 0; `make eval` ongewijzigd). **Stage 5 ✅** (substep `9.3.1` — gerichte `source_system`+`target_system`+`business_id` token-vorm in `token-claims.json`/`token_verifier.py`/`chat.yaml` + drift-tests; gate `_build_directed_context` (resolve source/target, onbekend → 400 vóór search, vend-rechten, slot-role + allowlist vervallen D4/D5; `business_id` → `company_id`, `source_slug`/`target_slug` gedragen); widget-bridge `TokenScope`/`sameScope` krijgen source/target zodat een stille connectie-switch de thread reset; nieuwe `connection` `CitationAttribution`-variant; test-host mint `?form=directed` + nieuwe `connection-switch` test-host-pagina. Levels: backend unit 899+1xfail · kb 29 · DB (`make test-db`) 385+1xfail + kb 24 · `pnpm test:e2e` 7/7 · `make eval` ongewijzigd. `start_chat_session` wiring in `POST /chat` is uitgesteld naar 9.4.1 (daar waar labels/block geconsumeerd worden).) **Stage 6 ✅** (substep `9.4.1`, commit `8ce2098` — `_base_filters` krijgt `AND labels && :session_labels` (bound) door `keyword_search`/`dense_search`/`fetch_rerank_texts`; `app.allowed_labels` GUC in hetzelfde pad als `apply_knowledge_scope` zodat de 0016 RESTRICTIVE policy live wordt; parent-expansie label-exempt; `answer_service._resolve_directed_routing` voedt `session_labels` + `connection_block` uit de chat-sessie, één keer per gesprek; D0-reconciliatie bleek geen code nodig (routing-label + `obi-general-test` indexeert + routet al). Levels: DB 390+1xfail + kb 24 · `make eval` vloer ongewijzigd. mi-hardfilter → unverified.) **Stage 8 ✅** (substep `9.5.2`, commit `534b967` — `connection_routing` gelabelde gold-stage + `evaluate_routing_lift`: routing-off-vs-on recall 1.000→1.000, served_precision 0.167→0.333, served_count 6→3 naar `eval-reports/routing_lift.{json,md}`, geprint door `make eval`.) **Stage 9 ✅** (substep `9.6.1`, commit `6548fc1` — triple-check groen (boundaries 0 · unit 912+kb 29 · DB 392+1xfail+kb 24 · eval vloer+routing-gate · `pnpm test:e2e` 7/7); securing-http-and-llm-endpoints review + isolatie/reversibiliteit op bestand (`5-integration-context/phase-9-*`); Jasper+Marien partner-replies herschreven naar het gerichte contract. De live-tegen-prod isolatierun is **owner-geblokkeerd** (prod leeg + op 0014; 9.5.1 relabel + prod-migrate + re-sync open).) **DE AGENT-DOENBARE ROUTING-ENGINE IS KLAAR (9.3.1–9.6.1 allemaal gecommit).** Tail vóór testen — wat de agent wél/niet kan afmaken: (1) `alembic upgrade head` op Supabase — *productiemutatie; de agent kan dit alleen met expliciete owner-go-ahead + bevestigde recente backup* (0015/0016/0017 zijn additief + veilig: de 0016 label-RLS is inert tot een connectie de GUC zet, 0017 voegt alleen `chat_session` toe; upgrade-only, never-bend regel 1); (2) 9.5.1 relabel = **owner Confluence-werk** (labels owner-attested aanwezig), re-sync geblokkeerd op (1) — agent kan de label→pagina-mapping + backfill (`backfill_labels` CLI bestaat) voorbereiden; (3) live isolatie-spotcheck — geblokkeerd op (1)+(2); agent kan het script klaarzetten; (4) partner-replies versturen = **owner-only** (drafts klaar in `5-integration-context/phase-9-partner-replies.md`); (5) Phase A human-validatie = **human**. Kortom: de engine is af; de tail is een deploy-/content-/sign-off-ketting die bij de owner hoort — het enige dat de agent kan overnemen is (1), en dan (2)-backfill + (3) zodra de relabel staat.
>
> **Production cutover 2026-10-13 (ADR-routing-labels-sole-content-axis Path B — DB + backend LIVE; re-sync in progress).** The
> owner authorized the full cutover and confirmed a recent Supabase backup. Done + verified:
> - **Committed:** Path B = `3178553` (110 modified + 4 new incl. migration `0018`, ADR-routing-labels-sole-content-axis, its
>   runbook). Gates green on this commit: boundaries 0 · unit 1148 (backend) + 29 (kb) · DB 392 + 1
>   xfail (backend) + 24 (kb) · eval floor intact (routing lift served_precision 0.167→0.333,
>   served_count 6→3) · lint/types at baseline (ruff 18, pyright 46+1).
> - **Prod migrated `0014 → 0018`** (explicit `DATABASE_URL`, not `make migrate`). Preflight confirmed
>   `0014` before + `0018` after, pgvector 0.8.2. Permissions verified by direct `pg_policies` read:
>   `chunk` has `chunk_source_read` (PERMISSIVE) + `chunk_labels_read` (RESTRICTIVE), `chunk_scope_read`
>   **dropped**, RLS ENABLEd; `curated_knowledge_entry` scope policy dropped, reader policy kept. Store
>   was empty (0 chunks) at migrate time. NB `scripts/setup_supabase.py check-deploy-readiness` now
>   FAILs because it still asserts the retired `chunk_scope_read` — stale gate, not a real isolation
>   gap (to fix for Path B).
> - **Backend redeployed to Path B** on Railway (`obi-backend`, Dockerfile service) via `railway up`
>   (owner-approved the harness production-deploy guard). `/health` → `knowledge_scopes: []` (was the
>   four `-test` scopes = old image). Background jobs confirmed running (`worker_tick` every 5s), so
>   webhook + sweep now auto-sync going forward.
> - **8-sync-rules audit vs the new tags:** `sync-rules/path-b-audit.md`. All 8 work in code; no hard
>   gaps. Rules 3 & 4 (remove-one-tag / add-a-tag) are **test-proof gaps** — nothing asserts
>   `chunk.labels` shrinks/grows or that routing flips. DB layer consistent (0016/0018).
>
> **Still open at time of writing (unverified — do NOT claim done):**
> - **Re-sync of the nine pages IN PROGRESS.** `run_reconciliation_once.py` ran a COMPLETE sweep that
>   enqueued the **whole `omnidoc` space (1069 pages)** — correct: `source_scope` row 23 scopes the
>   entire space, so every page syncs and only routing-labelled ones index. The deployed `worker_tick`
>   drains in job-id order; the nine labelled pages are jobs **1249–1261** (enqueued last) so they
>   index at the tail (chunks still 0 until the worker reaches them). The one-off script's OWN
>   `drain()` fails `ingestion sink not bound` (no sink outside `app/main.py`) — it was stopped; the
>   deployed worker owns draining. Use webhook/sweep or the deployed worker, not the local script's
>   drain.
> - **Live isolation check PENDING** on the re-sync. `verify_directed_routing_live.py` still hard-codes
>   `GATE_SCOPE = ("obi-general-test",)` — harmless post-0018 (that scope GUC is now a dead no-op; the
>   routing happens on `app.allowed_labels`) but its docstring is stale and should be cleaned.
> - **Stale `-test` references** remain in ~5 operational files (the two verify scripts +
>   `routing-test-labels.md` + `manual-tests.md` + the phase-9 live-test runbook).
>
> **→ Closed 2026-10-13 (audit follow-up).** The two agent-doable items above are done in the working
> tree: (a) the ~5 stale operator files + `verify_directed_routing_live.py`'s `GATE_SCOPE`/docstring
> are fixed, and (b) sync rules 3 & 4 now have the `chunk.labels`/routing-flip test proof
> (`test_sync_rules_routing.py`, 2 tests, proven real by revert). `make check` green (boundaries 0 ·
> backend 1542 + 1 xfail · kb 53). Detail: ledger/progress-log entry "ADR-routing-labels-sole-content-axis Path B audit
> follow-up" + the Follow-up section of `sync-rules/path-b-audit.md`. Still owner/worker-owned: the
> re-sync tail + the live isolation run; and `check-deploy-readiness` is flagged (stale banner) but
> its Path B re-spec is a separate security substep.
>
> **Lokale test — poging 2026-10-12 (geblokkeerd op een Confluence-label, owner-fix).** Doel: de
> hele engine lokaal bewijzen zonder prod (reingest van de echte gelabelde Confluence-pagina's naar
> lokale pgvector + de isolatie-check). Nieuw gereedschap gecommit: het één-commando-isolatiescript
> `backend/scripts/verify_directed_routing_live.py` (commit `b394ca7`, lokaal bewezen: toast→mews +
> mews→toast PASS, en het FAALT correct als RLS omzeild wordt) en de runbook
> `docs/runbooks/phase-9-directed-routing-live-test.md` (commit `ed13ca6`). Status van de poging:
> lokale DB op head (`0017`) ✓; Confluence bereikbaar ✓; de vijf routing-testpagina's gevonden in
> space **`omnidoc`** (space_id `701857803`, alle `current`). **BLOKKER:** elke pagina draagt **alleen
> haar routing-label** (`obi-general` / `toast-general` / `mews-general` / `toast-to-pms` /
> `mews-to-pos`) en **mist de basis-membership-tag `obi-general-test`** — site-breed draagt géén
> pagina `obi-general-test` (CQL-check: 0 resultaten). Gevolg (bewust ontwerp): (a) discovery
> (`list_pages_by_label` over de herkende scope-set) vindt ze niet → de reconciliatie-sweep gaf
> `pages_scanned=0`; (b) ook bij directe sync weigert de membership-gate ze (geen herkend
> scope-label). Dit strookt met de handover-spec `routing-test-labels.md` ("**twee labels per
> pagina**: `obi-general-test` plus precies één routing-label") en ADR-directed-source-target-routing-labels D0: het routing-label is
> toegevoegd, de basis-membership-tag niet. **Owner-fix (geen code):** voeg het label
> **`obi-general-test`** toe aan elk van de vijf pagina's (en aan eventuele Extension-A/B-pagina's),
> zodat elke pagina `obi-general-test` + haar routing-label draagt. **Bewezen dat die fix volstaat:**
> met het correcte schema lokaal geseed (`tags=[obi-general-test]` + één routing-label per pagina)
> gaf het script `RESULT: PASS` in beide richtingen — geen codewijziging nodig. Alternatief (wél een
> *beslissing*, geen fix): als de routing-labels de membership-tag moeten **vervangen** (een pagina
> zonder `obi-general-test`), is dat een engine-wijziging (een routing-label verleent dan
> membership); de handover-spec zegt echter `obi-general-test` behouden. `mi-hardfilter` blijft
> **unverified** tot de pagina's gelabeld zijn en de lokale run groen is. Niets aan Supabase/prod
> geraakt; lokale DB leeg gelaten.

> **Owner go-ahead 2026-10-12 (decision round 3, `plan.md` §D.17) — BUILD THE FULL ROUTING ENGINE AUTONOMOUSLY.** The owner authorized building the entire agent-doable engine end to end in one run: **`9.2.1` (chat-start/session) → `9.3.1` (token + gate + widget) → `9.4.1` (hard-filter `labels && session_labels`) → `9.5.2` (eval before/after) → `9.6.1` (triple-check + partner-reply drafts)**. **The two review gates (before `9.3.1` and before `9.4.1`) are WAIVED by explicit owner instruction** — do NOT stop to ask between substeps; keep the per-substep `/obi-change` rigor (failing test first, `make check` + `make eval` green, panel flip, ledger + progress-log per substep), but run them back-to-back. **Report to the owner ONLY when the whole engine is done**, and at that point tell them exactly what to test. Each substep is still its own atomic commit + ledger entry.
>
> **`9.5.1` (relabel the corpus) is the owner's parallel content task** — the owner is creating separate Confluence test pages carrying the routing labels (scheme handed over 2026-10-12; see the label set below / `docs/Final_docs/sync-rules/routing-test-labels.md`). Every test page carries the base membership tag **`obi-general-test`** (so it is indexed and passes locks 0–2) **plus exactly one routing label** from the box scheme. The engine build must make the ingestion + membership path recognize a page that carries a routing label + the base scope so these pages index and route without a per-integration `obi-*-test` tag — fold that reconciliation into `9.3.1`/`9.5`-adjacent config, keeping locks 0–2 unchanged (ADR-directed-source-target-routing-labels D0). Until the relabel lands, `9.4.x` DB-tests seed labels directly (hermetic), so the build does not block on the owner's pages.
>
> DB-password-rotatie (§D.15) staat op *niet nu nodig* (`docs/future-ideas.md`).
>
> **Corpus reset + relabel (2026-10-12, owner-ordered).** The live Supabase vector store was
> **wiped** to start the Option A relabel clean: it held exactly **1 page / 2 chunks**, now
> `chunk = document_version = document = page_source = 0` (raw FK-safe delete as DB owner, via the
> production purge order; `curated_knowledge_entry` was already 0 and is left intact, `event_ledger`
> audit history untouched; RLS never disabled). **The owner reports (owner-attested) that all
> routing labels are created and linked to their pages** (`9.5.1`, the scheme in
> `routing-test-labels.md`). **Re-ingestion is deliberately NOT done yet and is blocked on two
> things:** (1) prod is at migration **0014** — the `labels`/`applicability` columns (0015/0016) and
> `chat_session` (0017) are **not applied to Supabase**, and ingestion now writes `labels`, so a
> re-sync would fail until the owner runs `alembic upgrade head` on Supabase (never-bend rule 1:
> upgrade only); (2) the routing engine is still being built (`9.3.1`/`9.4.1`). So the empty DB is
> the expected state until the engine is done, prod is migrated to head, and the relabelled pages
> are re-synced — then the owner tests. The hermetic `9.x` tests seed labels directly, so the build
> is unaffected by the empty live store.

> **Path B — the knowledge-scope `-test` axis is RETIRED (ADR-routing-labels-sole-content-axis, 2026-10-12). DONE in code, green locally; prod + Confluence pending.** The owner chose Path B over keeping `obi-general-test` as a hidden base tag: every Obi `-test` tag is removed from code, config, validation, docs and the DB RLS, and **routing labels are now the sole content axis**. Index membership is **published + ≥1 recognized routing label (`obi-general` / `{slug}-general` / `{slug}-to-{kind}`, from `product_catalog.json`) + not `classified`**; `classified` stays the delete signal; company/source isolation (`chunk_source_read` / `app.allowed_sources`) is unchanged. **Landed:** ADR-routing-labels-sole-content-axis (supersedes ADR-knowledge-scope-tagging-and-filtering in full, completes ADR-directed-source-target-routing-labels D0) + ADR-knowledge-scope-tagging-and-filtering / ADR-directed-source-target-routing-labels annotations + `decisions.md` row `scope-axis-retirement`; `knowledge_scopes.json` → `classified` only; `platforms.json`/`platforms.local.json` scope lists emptied; boot/validation, auth (`allowed_scopes=()`), retrieval (scope GUC opted out to wildcard), curated, router body-scope, ingestion membership (`ProductCatalog.all_routing_labels()`) and discovery all rewired; reversible migration **`0018_retire_knowledge_scope_rls`** drops the two RESTRICTIVE scope policies (`chunk_scope_read`, `curated_knowledge_entry_scope_read`), downgrade re-applies them. **Tests passed locally (final, after the Task-2 cleanup below):** boundaries 0 · `make test-unit` backend 1148 + kb 29 · `make test-db` backend 392 (+1 xfail) + kb 24 (migrates local DB through 0018) · `make eval` floor + routing lift UNCHANGED (before == after) · frontend tsc clean + e2e 7/7 · ruff 18 (= baseline) · pyright 46 (= branch pre-work; net-zero — recorded `baseline.md` refreshed 43→46). Working tree UNCOMMITTED (branch convention). **Still PENDING (owner-gated):** the production `alembic upgrade head` on Supabase (prod reportedly at 0014; a read-only preflight from the build env was blocked by the "Production Reads" guard — unverified from here) and the Confluence relabel/re-sync. See ledger + progress-log entry "ADR-routing-labels-sole-content-axis · Retire the knowledge-scope `-test` tags".

> **Next agent tasks (do in this order; dependencies noted). Keep this list's status current as each lands.**
> 1. **Docs + design-page sync (doable now).** Update the remaining docs and the design-page HTML to describe the new tagging system (routing labels = membership + content axis; scope axis retired). Targets: `docs/Final_docs/retrieval/scope-enforcement-read-path.md` (full rewrite — a retirement banner is already on it), `docs/Final_docs/ingestion/routing-labels.md` (now also the membership axis), `ingestion/deletion-and-purge.md` + `ingestion/webhook.md` + `retrieval/eligibility-filtering.md` + `retrieval/auth-context-gate.md` + `retrieval/rerank.md` (drop/repoint scope references), and the design-page panels that mention the knowledge-scope axis. **Status: DONE (2026-10-12).** All 7 component docs updated (`scope-enforcement-read-path.md` fully rewritten; `routing-labels.md` now documents routing labels as the membership axis; `deletion-and-purge.md`/`webhook.md`/`eligibility-filtering.md`/`auth-context-gate.md`/`rerank.md` repointed), and the design-page HTML (`obi-rag-system-flow.html`) updated with ADR-routing-labels-sole-content-axis context (well-formed). A couple of `-test` mentions remain only as clearly-marked historical/provenance (e.g. a retired command example with a retirement note).
> 2. **Inert-plumbing cleanup + baseline refresh (doable now; after task 1 or parallel).** Remove the now-unused `knowledgeScope` field from the frontend chat path and the `enable_knowledge_scope_filtering` / `default_knowledge_scope` settings, and update any affected `packages/contracts` types + the OpenAPI `chat.yaml`; rerun `make test-unit` + `make test-db` + `pnpm test:e2e` + `make eval`; then refresh `docs/plan/baseline.md` from fresh verified `ruff`/`pyright` measurements (record the real current counts, noting the pre-existing drift). **Status: DONE (2026-10-12).** Removed `enable_knowledge_scope_filtering` + `default_knowledge_scope` settings (+ the retriever/answer_service/main wiring and `recognized_knowledge_scopes`) and the `knowledge_scope`/`knowledgeScope` plumbing — the backend `ChatRequestBody.knowledge_scope` field is kept only as a deprecated **accepted-and-ignored** field (back-compat, no 400), its validator/ignored-log removed; `packages/contracts` `ChatRequest` + OpenAPI `chat.yaml` + the frontend provider/route-handlers/validation drop it. All gates GREEN after the migration of the scope-filter tests: boundaries 0 · unit backend 1148 + kb 29 · db backend 392 (+1 xfail) + kb 24 · eval floor + routing lift unchanged · frontend tsc clean, vitest chat 192/193 (1 pre-existing untouched `composer.test.tsx` env failure), e2e 7/7 · ruff 18 / ruff-format 1 (= floor) · pyright 46 (= branch pre-work). `baseline.md` refreshed (pyright 43→46, the stale-drift correction). **Note:** both delegated agents (Task 1 docs, Task 2 cleanup) stalled on the background watchdog mid-edit; the work was completed and fully re-verified by hand.
> 3. **Prepare the production migration/deployment runbook (doable now — preparation only).** Write the exact owner steps to take prod from 0014 → head (0015/0016/0017/0018) and deploy: prerequisites (confirmed recent backup; explicit owner go-ahead; never-bend rule 1 — upgrade only, never the 0009 downgrade on Supabase), the explicit `DATABASE_URL`-scoped `alembic upgrade head` command, per-migration notes (0015/0016/0017 additive; 0018 drops the two scope policies — RLS stays enabled), post-migration verification (preflight revision check; `chunk_source_read` + `chunk_labels_read` present; the nine routing-labelled pages index on re-sync), and the rollback path (0018 downgrade re-applies the scope policies; 0015–0017 reversibility). Land it as `docs/runbooks/adr-0021-prod-migration.md`. **Status: DONE (2026-10-12)** — `docs/runbooks/adr-0021-prod-migration.md` written (prerequisites, the explicit `DATABASE_URL`-scoped `alembic upgrade head`, per-migration 0015–0018 notes, post-migration policy-presence verification, re-sync of the nine pages, the `verify_directed_routing_live.py` routing proof, and the 0018-downgrade rollback). No prod contact — preparation only.
> 4. **Production execution + verification (GATED — only on explicit owner authorization).** After the owner authorizes, run the migration/deploy, then verify the nine existing routing-labelled pages index correctly and that retrieval respects the customer's `source → target` connection (the `verify_directed_routing_live.py` isolation run against the live store). **Status: BLOCKED on owner authorization only (tasks 1–3 are DONE); see the owner checklist below.**

> **Owner checklist (parallel — the owner works these while the agent does tasks 1–3).**
> - [ ] Verify the production database's current migration revision and **authorize** the migration/deployment when ready (unblocks agent task 4).
> - [ ] Use the **nine existing routing-labelled pages** (`routing-test-labels.md`) as the first test batch after deployment.
> - [ ] Relabel the remaining Confluence content when ready — a page needs ≥1 correct routing label to become searchable (membership rule above).
> - [ ] Optionally instruct the agent to **commit** the Path B changes (left uncommitted until requested).

**Het model in één alinea.** Elk gesprek is één gerichte connectie: `source_system → target_system` + `business_id`. Bij *chat-start* (één keer per gesprek) lost de backend beide systemen op in de product-catalogus (die al `role`/kind + `connection_types` kent), bouwt exact **4 Confluence-label-"boxes"** — `obi-general`, `{source.slug}-general`, `{target.slug}-general`, `{source.slug}-to-{target.kind}` — schrijft een *connection block* in de system-prompt, en bewaart (business_id, source, target, labels, block) op een sessierij. Elke vraag hergebruikt die sessie (géén nieuwe lookup) en **hard-filtert** hybride search + rerank op die 4 labels, vóór top-k. Een partnerswitch herdraait chat-start en vervangt block + labels. Richting is primair: `toast-to-pms ≠ mews-to-pos`.

**Wat al bestaat (hergebruiken, niet opnieuw bouwen):**
- Catalogus met `role` (=kind pos/pms/accounting), slugs, aliases én `connection_types`/directions — `knowledge-base/config/product_catalog.json`, geladen/gevalideerd in `backend/app/platform/config/product_catalog.py` (nu alleen door de applicability-laag gebruikt, niet door de gate).
- De connection-block-render bestaat al grotendeels: `rag_agent/domain/prompt.py::build_integration_context_block` (~r.339) rendert "Host platform / Connected systems / Active connections and directions".
- Eén filter-chokepoint: `retrieval/infrastructure/search_repo.py::_base_filters` (~193–216) voedt zowel keyword- als dense-search vóór top-k; de `tags && :knowledge_scopes`-overlap (~r.211) is exact het patroon dat we kopiëren.
- `tags text[]` + partiële GIN `ix_chunk_tags_gin WHERE is_active` op `chunk` — Option A's labelkolom is een directe kopie.
- Webhook abonneert al `label_added`/`label_deleted`; ruwe labels worden al opgehaald (`gateway.get_labels`, `command_handler.py:128`).
- **Geen LightRAG/graph-agent aanwezig** — alleen hybride dense+keyword+RRF+rerank. Niets te doen daar.
- Eval: de `mixed_connection` gold-stage + de rerank-lift before/after-harness bestaan al (`app/features/evaluation`).

#### Pivotale beslissingen — vastleggen in Stage 0 (defaults gegeven; "Decision needed" waar owner tekent)
- **D0 · Label-als-scope.** De routing-labels vervangen de per-integratie knowledge-scope-tags als content-routing-as; company/source-isolatie (locks 0–2) ongewijzigd. Gevolg: het Confluence-corpus moet omgelabeld (content-taak, Stage 7). *Default: ja.*
- **D1 · Waar het filter leeft.** Via het bestaande scope/RLS-GUC-pad (**nieuwe `labels`-kolom + RESTRICTIVE RLS-policy gespiegeld op `chunk_scope_read`, gedreven door een nieuwe `app.allowed_labels` GUC**) én de app-laag `_base_filters`-overlap — zodat regel 3 ("geen read losser dan de search") en regel 1 (RLS) gelden. *Default: nieuwe `labels`-kolom + eigen GUC/RLS.* Alternatief (goedkoper, minder schoon): `tags` hergebruiken + bestaande GUC/RLS.
- **D2 · Ongelabelde pagina.** Chunk zonder routing-labels is onzichtbaar zolang een connectie-filter actief is (lege array overlapt niets). *Default: ja (self-gating).*
- **D3 · Labelwijziging.** Een label-only change werkt de `labels`-kolom bij via het bestaande **metadata-only restamp-pad** (labels zijn metadata zoals `tags`; géén re-embed). Wijkt bewust af van de handoff-tekst "re-ingest"; gerechtvaardigd want labels veranderen de embedding niet. *Default: metadata-only restamp.*
- **D4 · Richting-granulariteit.** `{source.slug}-to-{target.kind}` (bron-product → doel-kind). *Default: ja; open: later per partner splitsen (handoff Q3).*
- **D5 · Accounting wordt first-class target.** O4 "accounting inert" vervalt voor routing (`pms-to-accounting`/`pos-to-accounting` zijn geldig). Launch: route als er content/labels zijn, weiger met reden als de box leeg is (content-gated i.p.v. hard uit). *Default: content-gated.*
- **D6 · Mews-side setup.** Leest Toast→Mews ook `mews-to-pos`? *Default: nee (alleen de 4 boxes); open (handoff Q1).*
- **D7 · Eén connectie per gesprek.** Multi-system-klant = één gerichte paar per gesprek; meer = partnerswitch. *Default: ja.*

#### Override-map — elk krijgt een expliciete "SUPERSEDED by Option A (ADR-directed-source-target-routing-labels), 2026-10-09"-noot; nooit stil verwijderen
- `plan.md` §D.1 (drie-slot-token) + §D.13 item 3 (keuzes 1–4) → directed source→target token.
- `plan.md` §D.2 (vier flow-types) → één gerichte route per gesprek.
- `plan.md` §D.3 + 8.2.x (vijf-level "Applies to", migratie 0015, `applicability.py`) → vervangen door label-box routing; applicability-stamp wordt dood-voor-routing (kolom/plumbing blijft als data).
- `plan.md` §D.4 (matcher over slots) → 4-box resolver.
- `plan.md` §D.5 (eligibility-SQL) → label-overlap in `_base_filters`.
- `plan.md` §D.6–§D.8 (rerank-enrich, prompt-block, presets) → connection-block variant.
- `plan.md` §D.11/§D.12 (token-compat, contracts/catalog/migraties).
- `plan.md` §D.16 items 2 & 5 (O4-allowlist; "integratie LAST").
- `5-integration-context/decision-memo.md` O1 (open → gesloten door A), O5 (`context.slots`-shape → aangevuld), O4 (allowlist/accounting → vervalt voor routing); `context-contract.md` §5.2 ("geen connection records at launch").
- `docs/plan/decisions.md:45` (`partner-token-handover`, "not a flat source/target claim").
- `sync-rules/plan.md` §15 keuzes (~r.1084 "BESLIST" slot-model), §A row 5 context, en r.1381 owner-item (a) "company + integratie/slots + scope" → "company + source/target".
- **Blijft ongewijzigd:** de 8 sync-regels, RLS-locks 0–2 + §D access-invarianten, regel 8, lock-0 edge-JWT.

#### Stages (één per keer, `/obi-change`, failing test eerst, stop + ledger na elke substep; Stages 0–1 volledig vóór enige code)

**Stage 0 — Governance & beslissingen (geen code).** ✅ **DONE 2026-10-12 (commit `0209579`).** Schrijf **ADR-directed-source-target-routing-labels "Directed-connection retrieval routing (Option A)"** (`docs/adr/directed-source-target-routing-labels.md`; raakt/supersedeert ADR-knowledge-scope-tagging-and-filtering scope-tagging/filtering, ADR-source-id-row-security-with-reader-writer-roles multi-source tagging+RLS, ADR-scope-state-materialized-as-tags scope-state-as-tags; 0014/0017 blijven). Append-only nieuwe rij in `docs/plan/decisions.md` die `partner-token-handover` supersedeert (partners leveren `source_system`+`target_system`+`business_id`). Leg D0–D7 vast. Werk de override-map-doelen bij met de SUPERSEDED-noot.

**Stage 1 — Design-page panels (geen code).** ✅ **DONE 2026-10-12 (commit `42448cb`).** Design-page `docs/Final_docs/obi-rag-system-flow.html` (lees met `python3 backend/tools/panel.py <id>`): werk `mi-gate`/`mi-contract`/`mi-catalog`/`mi-match` bij; voeg NIEUW toe: `mi-route` (4-box resolver + direction), `mi-labels` (ruwe-labels-kolom + GIN), `mi-session` (chat-start-once + connection block), `mi-filter` (harde labelfilter via RLS/GUC). Markeer `mi-applies` deprecated-voor-routing. Regenereer de brief; zet today-lines. Voeg fase-9-substeps toe in `obi-action-plan.html`.

**Stage 2 — System catalog + label resolver (code; hergebruik).** ✅ **DONE 2026-10-12 (commit `099caef`, substep `9.1.1`).** In `product_catalog.py`: `resolve_system(name)` (naam/slug/alias, case-insensitief) + `build_labels(source,target)` → de 4 geordende boxes. Labelvorm-validatie (`obi-general` / `{slug}-general` / `{slug}-to-(pos|pms|accounting)`). Unit-tests in `test_applicability_schema.py`-stijl (`_reason()==`): de 5 voorbeeldconnecties → exact de juiste 4 labels; onbekend systeem → `[obi-general]`; wijst `toast-to-pmss`/`toast-to-hotel` af. Panels: `mi-catalog`, `mi-route`.

**Stage 3 — Ingestion: ruwe labels op chunks (code + migratie 0016).** ◀ **IN UITVOERING — substep `9.1.2`.** Migratie **0016** (down_revision `0015_applicability_stamp`): `chunk.labels text[] NOT NULL DEFAULT '{}'` + partiële GIN `ix_chunk_labels_gin WHERE is_active` (kopie `0007_knowledge_scope.py`); spiegel op `page_source`; downgrade dropt beide; plus (D1) `app.allowed_labels` GUC + RESTRICTIVE policy gespiegeld op `chunk_scope_read`. Thread `labels=` (ruwe `get_labels`-output) door `versioning.py` chunk-inserts + het metadata-only restamp-pad (`command_handler.py:365`; D3 `labels_changed`); houd `labels` (ruw) gescheiden van `tags` (resolved scope). Writer-backfill-CLI (kopie `scripts/seed_source_scope.py`), idempotent; of hergebruik `reindex.py`. DB-tests: chunk draagt ruwe labels; restamp werkt labels bij zonder re-embed; backfill tweemaal veilig. Panels: `mi-labels`.

**Stage 4 — Chat-start + sessie (code + migratie).** `chat_session`-tabel **gebonden aan geverifieerde `token_subject`+`company_id`** (niet aan caller-conversation_id alleen; spiegel `_idempotency_cache_key`): business_id, source_slug, target_slug, labels, connection_block, updated_at. Chat-start draait één keer (row-exists check): resolve source/target → `build_labels` → `build_connection_block` (nieuw in `prompt.py`) → opslaan; `llm_client.generate` consumeert het opgeslagen block i.p.v. per request te herbouwen. Tests (DB+unit): once-per-chat (spy: tweede vraag roept de catalogus niet aan); sessierij gebonden aan subject (andere subject kan niet lezen/muteren). Panels: `mi-session`, `mi-gate`.

**Stage 5 — Token + gate + widget (code; contracts + verifier samen).** `packages/contracts/src/token-claims.json`: derde optionele vorm `source_system`+`target_system`+`business_id` (≈ `company_id`); `context.slots` + legacy `integration` blijven geaccepteerd maar routen niet meer. Update REQUIRED_CLAIMS drift-test, `chat.yaml`, `token_verifier.py` samen. Gate: checks 1–2 gelden op source/target; check 4 = "mag deze issuer deze source/target venten"; slot-checks 3–5 + launch-allowlist vervallen voor A-vorm. Widget: voeg `source`/`target` toe aan `TokenScope`/`sameScope` (iframe-bridge) zodat een stille token-renewal-switch de thread reset (anders cross-context bleed); breid test-host token-mint + `businessClaims` uit. Nieuwe `CitationAttribution`-variant voor directed source→target. Tests: unit (gate accepteert A-vorm, weigert onbekende source/target met **400 vóór search**), browser (switch reset de thread). Panels: `mi-contract`, `mi-gate`.

**Stage 6 — Retrieval hard-filter (code).** `_base_filters` krijgt `session_labels` → `AND labels && :session_labels` (bound, niet geïnterpoleerd), op exact de plek van de `tags`-overlap; thread door `keyword_search`, `dense_search` én `fetch_rerank_texts`; **niet achter een flag** (hard). Parent-expansion (`fetch_parent_context`) krijgt géén labelfilter (kind al geautoriseerd). Zet `app.allowed_labels` GUC in hetzelfde pad als `apply_knowledge_scope`. DB-tests (exact include/exclude zoals `test_worked_examples_db.py`): een Toast→Mews-sessie krijgt nooit chunks wiens enige label `toast-to-accounting`/`mews-to-pos` is; rerank-input al gefilterd; lege-labels-chunk doet niet mee. Panels: `mi-filter`, `mi-match`.

**Stage 7 — Content-migratie (owner/content-team, parallel).** Confluence-corpus omlabelen naar `obi-general` / `{slug}-general` / `{slug}-to-{kind}`; `knowledge_scopes.json` herschrijven; backfill (Stage 3) draaien. Handwerk aan de content-kant — staat onder "need from you". Tot dit klaar is draait Option A tegen omgelabelde test-pagina's.

**Stage 8 — Eval before/after (verplicht, regel 11).** Breid `mixed_connection` gold-stage uit met labels (of nieuwe dataset in `_DATASET_FILES`); leg before/after vast via `evaluate_rerank_lift`-stijl (routing uit vs aan) naar `eval-reports/`. Geen retrieval-wijziging zonder voor-en-na-getal op de held-out gold-set. Panels: `mi-match`, `mi-filter`.

**Stage 9 — Triple-check + afronding + partner-replies (afsluiting van dit plan).**
- **Triple-check:** `make check` groen (boundaries 0 + backend + kb), `make eval` ≥ floor + het before/after-getal, `pnpm test:e2e` groen; security-review met `securing-http-and-llm-endpoints` op elke token/endpoint-wijziging; live isolatie-run (een Toast→Mews-token ziet nooit een andere connectie); migraties reversibel bevestigd; CI coverage-floor (≥625) gehaald, geen onverwachte skips/xfails.
- **Schrijf dat het gebouwd is:** per substep een ledger-entry (append-only, panel genoemd) + progress-log-entry; flip de design-panel today-lines; update de component-docs onder `docs/Final_docs/ingestion|retrieval`.
- **Schrijf de tests:** elke regression-test noemt zijn design-panel; de 5 voorbeeldconnecties, de validatie-afwijzingen, de exact-include/exclude DB-proof, de spy-test (geen catalogus-call per vraag), de switch-test (precies één connection block) en het eval before/after staan groen in de coverage-map.
- **Schrijf de partner-vragen/antwoorden:** werk de **Jasper**- én **Marien**-drafts om naar het **source/target-contract** (`source_system`+`target_system`+`business_id`), met de juiste obi.js-URL (`https://obi-web-production.up.railway.app/obi.js`), en de vraag welke source/target hun hub per klant vent — klaar voor de owner om te versturen (niet verzonden).

---

### Volgende stap — retrieval-routing per klant-connectie (reconciliatie-brief) — **SUPERSEDED 2026-10-09**

> **SUPERSEDED door "Option A: directed-connection retrieval routing" hierboven.** Deze informele brief was de eerste, ongefaseerde versie van dezelfde routing-gedachte. Hij is vervangen door het gefaseerde Option A-plan (met stages, tests, governance/ADR-directed-source-target-routing-labels en override-map) hierboven. Bewaard als herkomst/context; **niet los uitvoeren**.

**Activatie (één zin):** wanneer deze stap wordt geactiveerd, draaien we de onderstaande prompt en vergelijken we 'm regel voor regel tegen wat er nú al gebouwd is (§D / Phase 8, substeps 8.1.1–8.5.1), om conflicten en gaten te vinden en de prompt werkend te maken — níet om blind opnieuw te bouwen.

> Let op: veel hiervan is al geïmplementeerd in §D / Phase 8 (catalog loader, drie-slot contract, applicability-schema + migratie 0015, deterministische matcher, in-SQL eligibility-filter, context-aware rerank/prompt, per-slot attributie, de vijf worked examples). Deze prompt dient als **onafhankelijke spec** om tegen de huidige implementatie te toetsen; begin met "Step 0: explore first" en post het verschil/conflicten vóór enige wijziging.

````text
# Task: route Obi retrieval by customer connection

You are working in the Obi repo at Omniboost. Obi is a RAG assistant fed by Confluence. Read this whole brief first. Then explore the code. Then post a plan before you edit anything.

## Context you need

- Obi has exactly two workflows: ingestion and retrieval. Keep it that way. Chat start lives inside retrieval.
- A Confluence page enters the index only when it carries a label listed in the `knowledge_scopes` file. Removing its last listed label removes it.
- Any edit to an indexed page deletes the whole page from the vector store. Then the whole page is embedded again. Only published pages count.
- Stack: Postgres with pgvector on Supabase. Hybrid search (vector plus keyword). Cohere rerank. A LightRAG graph agent. The backend runs on Railway.
- Every chat starts with three values: `source_system`, `target_system` and `business_id`. Example: source Mews, target Toast, business ID B-3075.

## The problem

Today one search can return pages for any integration. A Mews to Toast customer can get Toast to QuickBooks steps. We fix this with Confluence labels and a hard filter inside the search.

## Words we use

- System: one product we integrate with, like Toast or Mews.
- Kind: what a system is. One of `POS`, `PMS` or `ACCOUNTING`.
- Slug: the lowercase name used in labels, like `toast` or `opera-cloud`.
- Box: one Confluence label. Every page with that label sits in that box.
- Connection: the source and target pair for one chat.
- Connection block: the part of the system prompt that names the two systems.

## The routing rule

For a connection with source S and target T, Obi may read exactly 4 boxes:

1. `obi-general`
2. `{S.slug}-general`
3. `{T.slug}-general`
4. `{S.slug}-to-{T.kind in lowercase}`

Examples you must support:

| Connection | Kinds | The 4 labels |
|---|---|---|
| Toast → Mews | POS → PMS | obi-general, toast-general, mews-general, toast-to-pms |
| Toast → Opera Cloud | POS → PMS | obi-general, toast-general, opera-cloud-general, toast-to-pms |
| Mews → Toast | PMS → POS | obi-general, mews-general, toast-general, mews-to-pos |
| Mews → QuickBooks Online | PMS → ACCOUNTING | obi-general, mews-general, quickbooks-online-general, mews-to-accounting |
| Toast → QuickBooks Online | POS → ACCOUNTING | obi-general, toast-general, quickbooks-online-general, toast-to-accounting |

Every system above is a real catalog id (`toast`·pos, `mews`·pms, `opera-cloud`·pms, `quickbooks-online`·accounting); the box slug is always the resolved canonical id. Build the real catalog from the labels that exist in Confluence. A box with no pages is fine and returns what exists — the accounting-product general boxes (`quickbooks-online-general`) stay **empty** at launch (content-gated, ADR-directed-source-target-routing-labels D5), so no page is created for them. The owner's live routing-label set is the nine labels in `routing-test-labels.md`: `obi-general`, `toast-general`, `mews-general`, `opera-cloud-general`, `toast-to-pms`, `mews-to-pos`, `opera-cloud-to-pos`, `toast-to-accounting`, `mews-to-accounting`.

## Step 0: explore first

Find these and list them with file paths before you change code:

- The ingestion workflow and the Confluence client it uses.
- How chunks are stored. Table name, columns and indexes.
- The `knowledge_scopes` file and the code that reads it.
- The webhook handler for Confluence events.
- Where a chat starts. Where `source_system`, `target_system` and `business_id` arrive.
- The system prompt builder.
- The hybrid search query. The Cohere rerank call. The LightRAG agent entry point.
- Where a chat session is stored today, if anywhere.

Post a short plan. Wait for approval before you run any migration.

## Step 1: the system catalog

Create one catalog file. Follow the repo's config style. Example: `config/system_catalog.yaml`.

```yaml
systems:
  - name: Toast
    slug: toast
    kind: POS
    aliases: []
  - name: Mews
    slug: mews
    kind: PMS
    aliases: []
  - name: QuickBooks
    slug: quickbooks
    kind: ACCOUNTING
    aliases: [quickbooks online]
```

- Load it once at startup.
- Validate it. Slugs are unique. Kind is one of the three values. Slug matches `^[a-z0-9]+(-[a-z0-9]+)*$`. Fail fast on a bad file.
- Expose `resolve_system(name)`. It returns the system or nothing. Match on name, slug or alias. Ignore case and extra spaces.
- Expose `build_labels(source, target)`. It returns the 4 labels in the order of the routing rule.
- Omniboost may already keep a master integration list with kinds. If you find one, ask before you read from it instead.

## Step 2: ingestion changes

1. Add a `labels text[] not null default '{}'` column to the chunk table. Add a GIN index on it.
2. On ingest, fetch every label of the page from Confluence. Store the full list on every chunk of that page.
3. Make LightRAG respect labels too. Either store the labels on the nodes and edges built from the page. Or store the page id and join to page labels at query time. Pick what fits the current setup. Explain your pick in the plan.
4. Validate each label. Valid forms: `obi-general`, `{slug}-general` and `{slug}-to-(pos|pms|accounting)`, with a slug from the catalog. Log a warning for any other label that sits in `knowledge_scopes`. Never block ingestion on this.
5. Add every routing label to `knowledge_scopes`.
6. A label added or removed on a page must re-ingest that page with the existing whole-page flow. Check that the Confluence webhook sends label events. If it does not, add a scheduled job that compares labels and re-ingests changed pages. Report which one you built.
7. Backfill. Write a one-off script that fetches labels for every indexed page and fills the new column. No new embeddings are needed for this. Make it safe to run twice.

## Step 3: chat start (runs once per chat)

Trigger: the event that starts a chat with `source_system`, `target_system` and `business_id`.

1. Resolve both systems with the catalog.
2. Build the 4 labels with the routing rule.
3. Build the connection block and write it into the system prompt:

```
## Customer connection
- Source system: Mews (PMS)
- Target system: Toast (POS)
- Direction: PMS → POS
- Business ID: B-3075
Answer for this connection only. If the user asks about another system, tell them to pick that partner first.
```

4. Save on the session: `business_id`, `source_slug`, `target_slug`, `labels`, `connection_block` and `updated_at`. Add a Supabase table or columns as needed.
5. Unknown system: log it with the business ID. Set labels to `[obi-general]`. Say in the connection block that the system is unknown.
6. Run this once per chat. Never on each question.

## Step 4: each question (no lookup)

1. Load the session. Read `labels` and `connection_block`. Do not call the catalog. Do not rebuild the labels.
2. Hybrid search: add `labels && :session_labels` (array overlap) to the SQL. Do it for the vector part and the keyword part. Apply it before top-k. Never filter after ranking.
3. Cohere rerank: send only the filtered candidates.
4. LightRAG agent: apply the same label filter to graph retrieval.
5. Build the LLM call from the base system prompt, the saved connection block, the retrieved chunks and the question.
6. The connection block names the two systems so Obi words the answer right. The label filter decides which pages Obi sees. Never use the prompt as the filter.

## Step 5: partner switch

A customer can pick a new partner in the UI. Then:

1. Fire the chat start flow again with the new source and target. Keep the business ID.
2. Replace the connection block in the system prompt. Never append a second block.
3. Replace the saved labels on the session.
4. Same pair as the current one: do nothing.
5. Keep the chat history unless the product owner says otherwise. Add one short system note like "Partner switched to Mews → QuickBooks."

This fires once per switch. Never per question.

## Step 6: logging

- Chat start: log the business ID, both systems, both kinds and the 4 labels.
- Each question: log the session id, the 4 labels, the candidate count before rerank and the chunk count after.
- Warn when a filtered search returns zero chunks.
- Partner switch: log the old pair and the new pair.

## Step 7: tests

- Unit: the 5 example connections return exactly the labels in the table.
- Unit: an unknown system returns `[obi-general]` and logs a warning.
- Unit: label validation accepts the valid forms. It rejects `toast-to-pmss` and `toast-to-hotel`.
- Integration: seed chunks with mixed labels. A Toast → Mews session never returns chunks whose only labels are `toast-to-accounting`, `mews-to-pos` or `opera-cloud-general`.
- Integration: the LightRAG path respects the same filter.
- Spy test: answering a question never calls the catalog.
- Partner switch: the connection block and the labels are replaced. Exactly one connection block remains in the prompt.
- Same pair switch: nothing changes and nothing is logged as a switch.

## Done when

- [ ] The catalog file exists and loads with validation.
- [ ] Chunks carry labels. The backfill ran.
- [ ] Label changes trigger a re-ingest.
- [ ] Chat start saves the labels and the connection block once.
- [ ] Every question filters hybrid search, rerank input and LightRAG on the saved labels.
- [ ] A partner switch refires chat start and replaces the block and the labels.
- [ ] Every test above passes.

## Out of scope

- Partner stamps inside a label. `toast-to-pms` still holds pages for every PMS. A Toast → Mews chat can still see Campspot pages from that box.
- Any change to how pages are chunked or embedded.

## Open questions to raise, not decide

- Should a Toast → Mews chat also read `mews-to-pos` for the Mews side setup?
- Does the production webhook fire when only a label changes?
````

### Laatste items (owner) — deze sluiten de plan af

> **Order (owner-confirmed 2026-10-13).** **Phase A human testing comes FIRST** (the engine is proven
> hermetically + live-isolation; Phase A is the human validation of real content/answers, cases in
> `docs/Final_docs/5-integration-context/phase-a-validation-cases.md`). **Immediately after Phase A**
> comes the full **A-Z platform integration** below: stand everything up to put Obi into the **Base**
> and **Data Hub** test environments, end to end — and that explicitly includes **contacting Jasper
> and Marien** and getting the facts Obi needs from them. Platform integration does NOT run ahead of
> human testing, but it is the very next thing after it.

1. **Phase 4.x / Phase B — platform integration for Base + Data Hub (makes a real production chat
   possible), A-Z.** The embed widget opens but will not authenticate without a trusted per-platform
   token. **Platform ownership:** **Marien owns Base, Jasper owns Data Hub** (one partner, one hub).
   The send-ready contract + the exact emails to Jasper and Marien live in
   `docs/Final_docs/5-integration-context/phase-9-partner-replies.md` (directed `source_system` →
   `target_system` + `business_id` form, ADR-directed-source-target-routing-labels / ADR-routing-labels-sole-content-axis — it supersedes the earlier single-`integration`
   handover the partners already received). Run it in this order:

   **(0) Contact the partners** — send each the directed-contract email (resolve the remaining
   `[OWNER: …]` placeholders first: your name, and the test-JWKS option A/B). The one answer that
   drives routing is **per customer, which product is the source and which is the target**.

   **What Jasper & Marien must each provide (the five facts):**
   - (a) **Issuer string** (`iss`) — their token issuer, an HTTPS URL.
   - (b) **A reachable JWKS URL** — their public keys as JWKS, keyed by `kid`, **RS256 or ES256**
     (never HS256), so Obi verifies the signature. Must stay reachable.
   - (c) **The exact embed domain(s)** — the origins the widget loads on (these lock the iframe's
     `frame-ancestors`; a missing one blocks the embed). Jasper's handover used `www.datahub.be` for
     Data Hub — confirm the real test-env origins per platform rather than assume; the earlier
     `base.omniboost.io` / `datahub.omniboost.io` guesses are UNCONFIRMED.
   - (d) **Each customer's separate `source_system` and `target_system`** (canonical catalog ids).
     This drives routing. `company_id` = their customer id (confirmed OK = `business_id`).
   - (e) **A token-minting endpoint** (obi.js' `tokenUrl`, same origin as the page) that signs the
     directed JWT.

   **Our side, once a platform's five facts are in** (full detail: the "What happens after they
   reply" steps 1-7 in `phase-9-partner-replies.md`): add a `platforms.json` entry (issuer, JWKS URL,
   embed domains, the source/target ids the hub may vend) with **`active: false`**; verify the JWKS is
   reachable and the endpoint mints a conforming directed JWT; confirm vend rights (the issuer may
   assert only the agreed ids); flip **`active: true`**; redeploy backend (registry) + rebuild/redeploy
   frontend (the `frame-ancestors` CSP derives from the active embed domains); remove the temporary
   `obi-test` issuer + its embed allow-list (`obi-test.domains` = the Railway host); run the test
   matrix against the deployed origin and save the output. Entries go active only after verification,
   never on receipt of the email.

   **Source/target knowledge (owner-confirmed 2026-10-13 — the routing axis):** the **source systems**
   Obi accepts today are exactly **`mews`, `opera-cloud`, `toast`** (a chat always starts from one of
   these). **Target systems are also tagged**, and the target is what **narrows the vector results**:
   for a source (say `toast`) Obi's eligible set is all of that source's content (`obi-general` +
   `toast-general` + the `toast-to-{kind}` boxes), and the **actual target** picks the most relevant
   directional slice (`toast-to-pms` for a PMS target, `toast-to-accounting` for an accounting
   target). Accounting products (`quickbooks-online`, `xero`) are **targets only** — never a source.
   Partners send **ids, not role labels**; Obi derives each system's role (POS/PMS/accounting) from
   the id, so the "(POS)/(PMS)/(accounting)" annotation the partners asked about is for human clarity
   only, not a token field. The current launch allowlist is **POS = Toast, PMS = Mews**; Opera Cloud
   is catalog-valid but gate-refused until allowlisted. A property with both a POS and a PMS sends the
   two as a **source + target pair** (never a compound like `toast-opera`, which resolves to nothing
   and is refused 401). For a partner whose user switches customer/integration mid-session (Marien's
   case), the token is session-scoped and the widget refreshes it on a connection switch, which resets
   the chat thread (built in Stage 5).

2. **Own domain `obi.omniboost.com` (optional, cosmetic).** The frontend runs on the Railway host
   `obi-web-production.up.railway.app`; a branded `obi.omniboost.com` needs a DNS change (CNAME to the
   Railway service) by someone with DNS access. Not functionally blocking — the Railway URL works. The
   `obi.js` `src` the partners embed is this web host for the test phase and switches to
   `obi.omniboost.com` before go-live (the only change on their side is that one `src` line).

---

## Integration pre-flight & test phase (owner-side) — added 2026-10-13

> **Why this section exists.** Everything about standing Obi up inside Base + Data Hub used to live
> only in chat. This is the durable home for it: the owner runbook, the failure modes we must prove
> green *before* a partner sends anything, and the accounting-source architecture decision. Scope of
> this write is **plan only** — no code, no agents yet. Statuses marked "per cross-check" come from
> the 2026-10-13 code read (`token_verifier.py` / `auth_context.py` / `product_catalog.py` /
> `platforms.json` / `loader.ts`); they are claims to **re-confirm with file:line in the coverage
> audit** before any are trusted as done.

### A. The three preconditions (a chat only works when all three line up)

1. **Partner-side wiring** — the directed token (`source_system` + `target_system` + `business_id`,
   RS256/ES256, `aud:"obi"`, `exp ≤ 60 min`), the JWKS, and the `<script src>` on the **web** host.
   Covered by the send-ready contract + the two Slack messages.
2. **Our registration + deploy** — nothing a partner sends works until their issuer/JWKS/embed-domains
   are registered in `platforms.json` and the service is redeployed. Until then the gate returns 401
   ("unknown issuer" / inactive) and the widget refuses to load.
3. **Content for the exact connection** — Obi answers only for a `source→target` pair that has
   ingested, routing-labelled pages. An empty box **refuses with a reason** (correct, not an answer).
   `toast↔mews` is proven to have content (see the 2026-10-13 live block); `opera-cloud` and any
   accounting pairs need their pages written, labelled and ingested first.

"100%" needs all three — and even then only per-connection, for pairs that have content.

### B. Owner runbook — per partner, in order

1. Collect the **five facts** (issuer, JWKS URL, embed domains, per-customer source+target ids,
   token endpoint) **+ one test customer with a logged-in test user per connection**.
2. Add a `platforms.json` entry (issuer, `jwks_url`, embed domains, the source/target ids the hub may
   vend) with **`active: false`**.
3. Verify: JWKS reachable (RS256/ES256), the token endpoint mints a conforming directed JWT, and
   **vend rights** match (the issuer may assert only the agreed ids).
4. Flip **`active: true`**, then **redeploy the backend** (new registry entry) **and
   rebuild/redeploy the frontend** (the iframe's `frame-ancestors` CSP is computed from the active
   embed domains — a missing domain blocks the embed).
5. Remove the temporary **`obi-test`** issuer + its embed allow-list from `platforms.json`.
6. Confirm **content exists** for every pair they will test (pages labelled + ingested). Beyond
   `toast↔mews`, check this before the demo or it correctly refuses.
7. Run the **test matrix** against the deployed origin and save the output.
8. *(Optional, later)* `obi.omniboost.com` DNS (CNAME to Railway) + swap the `obi.js` `src`.

**Caveats.** (i) The plan's stated order is **Phase A human validation first** (answer quality);
integration wiring can proceed in parallel but that is the order. (ii) The "accounting is
target-only / source must be PMS-or-POS" rule is **not a hard code check** in the directed gate today
— it is content- and vend-list-enforced. Section D changes how this is handled (configurable, not a
category ban).

### C. Pre-flight stub-partner test matrix (prove green before a real token arrives)

We own the pieces to fake a partner **entirely locally** — a test RS256 keypair, the temporary
`obi-test` issuer, and the `/test-hosts/multi` embed page. The pre-flight phase formalizes a **stub
partner** (fake issuer → stub JWKS → stub token endpoint → stub embed host) and drives the real
`/chat` + embed path with it. **All local/test-only — never prod `platforms.json`, never a deploy.**
This proves *our* side end to end; it cannot prove a partner's real JWKS/domains or content for
pairs that have none.

| # | Failure mode to prove | Status (per cross-check — confirm in audit) |
|---|---|---|
| 1 | Directed happy path (`toast→mews`) returns cited, connection-scoped answers | likely covered |
| 2 | `toast-opera` compound refused before search (as legacy `integration`: 400; as `source_system`: since 2026-10-20 an unknown source → **403 `source_not_enabled`**, widget hidden) | covered; lock the code + status |
| 3 | Legacy `integration`/`company_id` token → general content only, never routes | covered (`token_verifier.py:120`) |
| 4 | Direction flip (`toast→mews` ≠ `mews→toast`) | proven live 2026-10-13 |
| 5 | Empty connection box → refuse-with-reason, not a wrong answer | confirm at /chat level |
| 6 | Unknown issuer / inactive platform → 401, widget refuses to load | covered |
| 7 | HS256 / off-allow-list alg → rejected | covered (`token_verifier.py:158`) |
| 8 | `exp − iat > 60 min` → rejected | covered (`token_verifier.py:176`) |
| 9 | Embed `frame-ancestors`: disallowed host blocked, allowed host loads | browser e2e — confirm/extend |
| 10 | Vend-rights: issuer asserting a non-vended source/target id → refused | **likely new** |
| 11 | Multi-tenant switch: re-point/`clear` → fresh token → fresh chat on new connection | **likely new** (e2e) |
| 12 | End-to-end stub-partner test tying 1–11 together | **new** (the pre-flight test) |

**How it gets built (when scope expands past plan-only):** Agent 1 (read-only) fills the status
column with file:line and flags true gaps; then each missing test and each code fix is **one
`/obi-change` substep** — failing test first, `securing-http-and-llm-endpoints` for anything touching
the gate, `make check` green, ledger + progress-log entry, stop and check in. Nothing touches prod
config or a deploy.

### D. Architecture decision — target-driven visibility, configurable source roles (DESIGN, plan-only)

> **Superseded in part 2026-10-20.** The owner decided that only the **source** system decides widget
> visibility (ADR-source-system-decides-widget-eligibility): the target is never checked, an unknown
> target routes on `[obi-general, {source}-general]`, and an unknown or disabled source hides Obi
> (403 `source_not_enabled`). R2's "the target determines whether the widget appears" and the
> target-enablement wording below are therefore no longer current; the rest of this section is kept
> as the 2026-10-13 decision record.

**Decision (to ratify as an ADR, e.g. ADR-widget-hides-via-visibility-probe, when implemented):** *Obi widget eligibility is
determined by the selected target's enablement on the registered platform, subject to authentication
and access checks. Connection authorization and knowledge routing are enforced separately. Product
categories do not permanently prohibit source roles; supported products and directions are
configurable.*

This supersedes the earlier "hard-reject any accounting-category source" idea. **Do not** add a
permanent ban on `category == accounting` as a source — a future authorized `quickbooks-online →
toast` must be possible by **configuration**, not an architecture rewrite.

**Separate three concerns (today they are conflated):**

- **Widget visibility** — *should Obi appear for this target?* Driven by the target's enablement on
  the registered platform (configurable, per platform).
- **Connection authorization** — *is this user allowed this customer's selected source→target?* From
  the verified token + trusted partner-side data; browser-provided values alone never authorize.
- **Knowledge routing** — *which docs may Obi use?* The directed boxes only
  (`obi-general` + `{source}-general` + `{target}-general` + `{source}-to-{target.kind}`).

**Requirements (R1–R10, from the owner directive 2026-10-13):**

- **R1 · Accounting must be able to become a source.** No permanent category ban. Category
  (PMS/POS/accounting) describes the product; whether it may participate in a connection comes from
  config + the actual authorized integration.
- **R2 · The target determines whether the widget appears** — for the **currently selected
  connection**, not every system the user can reach. A target enabled for Obi on that platform ⇒
  widget appears; an unknown/disabled target ⇒ it does not. An accounting **source** must not by
  itself hide a widget whose **target** is enabled. Registration must distinguish roles: known as a
  product, or supported as a source, does **not** imply enabled as a target.
- **R3 · Keep product support configurable.** Reuse/extend `product_catalog.json` + `platforms.json`
  — do **not** create a competing registry. Represent: canonical product id · display name ·
  category · whether enabled as an Obi **target** on the platform · any source/connection
  restrictions. Adding a future accounting source = registering/enabling a product + connection, not
  deleting a hardcoded ban. Validate/route on **canonical ids**; "QuickBooks Online (accounting)" is
  presentation only.
- **R4 · Base and Data Hub stay independently configurable.** A target enabled on one platform is not
  enabled on the other. Preserve each platform's current support, but do not encode today's offering
  as irreversible. Never infer the platform from the product category — use the registered platform.
- **R5 · Validate the real customer connection on the backend.** Target-visibility is a product
  **availability** rule, not access. The backend must still verify: registered platform · user
  authenticated · the selected customer + connection authorized for that user · source and target
  belong to that connection · target enabled for Obi on that platform · explicit connection
  restrictions satisfied. Customer/source/target come from trusted partner-side data via the token.
  Enforce availability + authorization on the **backend** too, so bypassing the widget's visibility
  logic bypasses nothing.
- **R6 · Retrieval stays tied to the exact `source→target`.** Only {source-general, target-general,
  the explicit `source→target` pair} + all existing customer/access restrictions. Enabling a target
  must not expose every page mentioning it; a future `quickbooks-online → toast` must **not** pull
  `mews→toast` or `toast→mews`. Direction matters. Apply the same restriction through **every**
  retrieval stage, including any graph retrieval.
- **R7 · Missing docs ≠ invalid connection.** A valid, authorized, target-enabled connection with no
  pair-specific pages stays visible and answers from permitted **general** docs; if those can't
  answer, it says so — it must **not** widen to other connections. Handle an **unrecognized source
  id** explicitly: no guessing, no silent substitution, no unrestricted retrieval. A
  target-general-only fallback, if we support one, must be explicit and limited to permitted
  target-general content; otherwise return a clear configuration error until context resolves.
- **R8 · Customer/integration switches.** On a switch: refresh/replace the trusted connection
  context, re-evaluate widget eligibility for the new target, apply the new customer/source/target to
  later requests, and **prevent carry-over** of the previous connection's retrieved content or
  conversation. Supported→unsupported target ⇒ widget becomes unavailable for that connection;
  switching back ⇒ available again once the new context validates.
- **R9 · Tests** (extend existing): supported+enabled target ⇒ eligible; unknown/disabled target ⇒
  hidden; source-only product ≠ auto-enabled target; a valid explicitly-enabled accounting-**source**
  connection accepted; an unsupported accounting-source follows the configured restriction (not a
  category ban); a supported target does not authorize an unrelated customer or fabricated
  connection; retrieval = only permitted general + exact directed pair; reverse/unrelated pairs
  excluded; missing pair docs do not trigger unrestricted retrieval; a customer/integration switch
  updates **both** availability and retrieval context with no carry-over.
- **R10 · Record + report.** This decision is recorded here (ratify as ADR when built). After
  implementation, report: what controls widget visibility · what validates the customer connection ·
  what restricts retrieval · which config change enables a future accounting source · what more is
  needed to add a new target · any remaining limitations.

**Current-state → target-state delta (must be resolved during implementation — flagged, not assumed):**

- **Widget visibility is NOT target-enablement-driven today.** The directed gate **lapses** the
  slot-role check and the launch allowlist for the directed form (`auth_context.py:190-192`); the
  allowlist (POS=Toast, PMS=Mews) gates the legacy/slot path, not the directed one. R2/R5 require a
  new, **configurable target-enablement check per platform** on the directed path (backend-enforced,
  with a matching frontend eligibility signal). This is net-new behavior.
- **There is NO "context-update mechanism" (R8).** The widget bridge is exactly `obi:open` /
  `obi:token` / `obi:clear` (`loader.ts`); a switch today is **new-token → re-init/clear → fresh
  chat** (ADR-directed-source-target-routing-labels D7). R8's "existing context-update mechanism" does **not** exist. Decision needed:
  implement the new-token/re-init path as the context refresh (matches current design) **or** build a
  real `obi:context-update` message. Recorded as a blocker to settle before R8 is built.
- **Source-role support is implicit.** `product_catalog.json` has id/name/category but **no**
  per-product "enabled as target on platform X" or "allowed as source" fields, and `platforms.json`
  has no per-platform target-enablement/vend-restriction map beyond the embed/issuer data. R3/R4 need
  these config fields added (extending the existing files, not a new registry).
- **Vend-rights enforcement** exists at the gate but its test coverage is unconfirmed (matrix row 10).

This section is **design + decision only**. Implementation is a later, separate pass — one
`/obi-change` substep at a time, security-reviewed, each with its test and a before/after gold number
for any retrieval change, ratified as an ADR. Nothing here has been coded.
