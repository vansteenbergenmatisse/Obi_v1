# Phase-4 Embed Security Hardening — Final Report

Owner-mandated closed loop: **implement → independent audit → triage → repair → full test suite → fresh independent re-audit → repeat until clean-exit.** This report is written to the mandate's "Final report after the loop" spec. Branch `feat/rag-phase-4-embed-security-hardening`, base `94c0346`, HEAD `0905ad2`.

> **Scope of "done".** This report certifies the **locally-provable core** (deterministic fixtures + self-signed test keys): the loop's clean-exit criteria are met for it. Real **Base** / **Data Hub** production readiness is a **separate external gate** and is explicitly NOT claimed here (§11).

---

## 1. Rounds completed

| Round | What | Outcome |
|---|---|---|
| Wave 0 | Research + requirement-traceability matrix (6 independent researchers + synthesis) | Matrix + 15-item test-contract; 5 mandate premises refuted |
| Impl S1–S5 | Implementation slices (embed lifecycle, prod config guard, identity namespacing, deploy gate, regression coverage) | committed |
| Wave 1 | First independent audit (6 auditors + verify) | 15 confirmed, 1 refuted → repairs R1–R5 |
| Wave 2 | Fresh re-audit (6) | 4 new (2 HIGH) → repairs RW2 |
| SEC-MUT | Targeted mutation testing (~20 boundaries) | all caught except 1 weak test → fixed |
| Wave 3 | Fresh re-audit (5) | 1 MED + LOW → repairs RW3 |
| Wave 4 | Fresh re-audit (5) | 2 LOW → repairs RW4 |
| Wave 5 | Fresh re-audit (5) | CLEAN (consecutive-clean #1, later reset) |
| Wave 6 | Fresh re-audit (5) | 1 LOW (W6-5-L1) → repair SEC-RW6; counter reset to 0 |
| Wave 7 | Fresh re-audit (5) | 1 LOW (W7-A1-1) + 1 disproven-for-v1 hardened → repair SEC-RW7 |
| Wave 8 | Fresh re-audit (5) | 1 LOW (W8-A1-1) → repair SEC-RW8 |
| Wave 9 | Fresh re-audit (5) | **CLEAN** (consecutive-clean #1) |
| Wave 10 | Fresh re-audit (4) | **CLEAN** (consecutive-clean #2 → **EXIT**) |

**11 audit waves** (Waves 0–10), **9 repair rounds** (R1–R5, RW2–RW4, SEC-MUT, SEC-RW6/7/8).

> Waves 0–5 were run by the prior session (recorded in `loop-log.md`, ledger entries SEC-S1…SEC-RW4, and the Wave-5 clean commit `54370d3`). Waves 6–10 and repairs SEC-RW6/7/8 were run this session. Wave 5's clean result was invalidated as consecutive-clean #1 because Wave 6 (the intended #2) surfaced an actionable finding — the counter correctly reset, per the mandate.

## 2. Agents per round (Waves 6–10, this session)

Each wave: **fresh** independent auditors (none implemented the area), code-only conclusions (not given the implementers' rationale), every finding adversarially verified with default-REFUTED. Domains: (1) auth/host-key/prod-config red team; (2) browser/iframe token security; (3) authz + retrieval isolation + Confluence/identity + server-side lifecycle; (4) config/migration/CI/test-infra; (5) cross-cutting completeness critic. Waves 6–9 used 5 auditors; Wave 10 used 4 (config folded with cross-cut). The coordinator re-verified every gate independently and triaged every finding by direct reproduction — never trusting a subagent's "green" claim.

> **Disclosed deviation.** An account spend-limit repeatedly terminated subagents this session (it killed the prior session's entire Wave-6 auditor set mid-run, producing a spurious `clean:true` that was correctly discarded and re-run). Because of it, repairs SEC-RW6/7/8 were performed in the **main window** rather than by separate repair subagents. Independence is preserved by the mandate's fresh re-audit waves that follow each repair (the loopback code's original implementer was the SEC-RW4 subagent, not the coordinator), and each repair was driven failing-test-first with the coordinator reproducing the defect before fixing it.

## 3. Findings from every wave (this session), confirmed vs disproven

All findings this session were **LOW severity, fail-closed, and operator-config-only (not attacker-reachable)** — they were in the backend↔frontend loopback/`.local` host matcher twin, whose divergence violates a stated code invariant. None touched auth, authz, integration isolation, secret handling, page permissions, or stale context in a live-exploitable way.

| ID | Wave | Class | Confirmed? | Evidence | Repair |
|---|---|---|---|---|---|
| **W6-5-L1** | 6 | loopback twin diverges on non-ASCII digits (`str.isdigit()` accepts Arabic/fullwidth/superscript; `int("²")` crashes) | CONFIRMED (coordinator reproduced: `_is_loopback_host("127.0.0.٥")`→True backend / False frontend; `127.0.0.²`→ValueError) | live repro | SEC-RW6 |
| **W7-A1-1** | 7 | loopback twin diverges on whitespace inside brackets (`[ ::1]`, `127.0.0.1 :80`) — backend `.strip()`s the extracted host, frontend did not | CONFIRMED (coordinator: backend loopback=True on all 5 forms, frontend False before fix) | live repro | SEC-RW7 |
| classify_scope note | 7 | same `isdigit()`→`int()` crash class in `permission.py` | **DISPROVEN for v1** (only caller passes `auth.principal`, hardcoded None on all AuthContext branches; body principal inert + numeric-rejected) — hardened proactively anyway | caller trace | SEC-RW7 |
| **W8-A1-1** | 8 | loopback twin diverges on 6 code points where Python `str.strip()` ≠ JS `trim()` (Python-only U+001C–1F,U+0085; JS-only U+FEFF) | CONFIRMED (two independent auditor differentials, 3,779 + 3,137 inputs, converged on the identical 6-char set) | 2× differential | SEC-RW8 |
| W9-A1-OBS | 9 | (observation, **explicitly "NOT a defect"**) parity enforced only by per-side tests, not a mechanized CI differential | NON-ACTIONABLE — twins proven equivalent (~882k inputs, 0 divergences), per-side tests non-vacuous, completeness-critic found no missing test | 3× differential | recorded in `future-ideas.md` |

**Disproven / refuted across the loop:** ISO-AUTH-1 (Wave 1, claimed scope-derivation bypass — disproved from code); FINDING-AUTH7 (re-weighed bounded-safe in Waves 1/2/3/5/6/7/8/9/10 with ingestion-code evidence — parent+child of a page always share tags); the classify_scope note (disproven for v1); W9-A1-OBS (non-actionable, twins proven equivalent). Prior-session refutations are in `loop-log.md`.

## 4. Repairs + regression tests (this session)

| Repair | Commit | Root cause | Fix | Regression tests |
|---|---|---|---|---|
| **SEC-RW6** | `2d23900` | `str.isdigit()` accepts non-ASCII digits → twin divergence + `int()` crash | ASCII-only octet check `o.isascii() and o.isdigit()` at both sites in `platforms.py` (`_is_ipv4_loopback_host`, `_expand_ipv6`) | 6 backend (direct matcher + registry-load) + 1 frontend parity; red-before-green |
| **SEC-RW7** | `ea9f33b` | frontend `isLocalhostDomain` didn't re-trim the extracted host; `classify_scope` had the same `isdigit→int` class | `host.trim()` after extraction in `csp.ts`; `classify_scope` → `isascii() and isdigit()` | 1 frontend (5 malformed forms) + 4 backend classify_scope cases; red-before-green |
| **SEC-RW8** | `8173a0c` | Python `str.strip()` ≠ JS `trim()` on 6 edge-whitespace code points | shared explicit union strip set on both twins (`_EDGE_WHITESPACE`/`_strip_edges` ↔ `EDGE_WHITESPACE`/`stripEdges`), replacing bare `.strip()`/`.trim()` at all host sites | 8 backend + 2 frontend (6 divergent chars leading/trailing/bracketed + a U+200B not-over-stripped pin); red-before-green |

Every confirmed defect has a regression test that goes RED on revert (verified empirically this session and independently re-confirmed by Wave-8/9/10 auditors). The loopback-parity class is now closed **by construction** (shared union set + ASCII-only octet checks), verified by the coordinator's cross-runtime differential: **3,993 inputs → 0 divergences** (149 before SEC-RW8), and independently by Wave-9/10 auditors at 21,740 / 856,643 / 547 inputs → **0 divergences** each.

## 5. Mutation checks

Full targeted mutation testing was run in the prior session (SEC-MUT, commit `1b3097f`): ~20 security boundaries, each deliberately broken one at a time, the guarding test confirmed RED, then reverted. **All boundaries caught except one** — the web-storage WRITE guard (test spied only reads) — which was **found + fixed + re-verified RED**. See `loop-log.md` "Targeted mutation testing". This session's three new controls each carry a revert→red regression test, empirically confirmed (the `int("²")` crash on revert; `[ ::1]`→false without the trim; `127.0.0.1<BOM>`→false without the shared strip), which Wave-8/9/10 auditors independently re-confirmed by revert-simulation.

## 6. Final test commands + results (this session, HEAD 0905ad2)

```
make test-unit         → backend unit 630 passed / 282 deselected · kb unit 23 passed · boundaries OK
make test-db           → backend db 281 passed / 1 xfailed · kb db 18 passed   (local pgvector :5434)
pnpm --filter web test → vitest 288 passed (30 files)
pnpm --filter web typecheck → tsc --noEmit clean
make test-ui           → Playwright embed e2e 4 passed
cd backend && uv run ruff check / ruff format --check / pyright  → clean on touched files
make boundaries        → Boundaries OK
```

The single strict-xfail (`test_delete_marks_the_active_version_superseded`, a Planned worker test) is the one CI-allowlisted exception; every other skip/xfail fails CI by design.

## 7. Requirement-traceability matrix — final status

The full per-requirement matrix is `traceability-matrix.md` (Wave-0 baseline). Final disposition of every gap it identified:

- **Browser/iframe (BIT-1…BIT-10):** all working. Gaps closed — BIT-7 runtime token-string guard (S1), BIT-10 `server-only` trip-wire (S3), CSP shared-helper so CSP + bridge allow-list can't diverge (R3), loopback strip parity (R2/R3/RW2/RW3/RW4/RW6/RW7/RW8).
- **Authorization/isolation (AUTH-1…AUTH-9):** all working. Active-platform gate + per-issuer `allowed_integrations` binding (R2); issuer-namespaced subject `iss\x00sub` (S3); RESTRICTIVE RLS fail-closed on unset GUC (pre-existing, re-proven every wave); AUTH-7 parent-fetch opt-out bounded-safe (documented, `future-ideas.md`).
- **Confluence/identity (CIP-1…CIP-5):** working for v1. `principal` always None → only unrestricted pages; page-principal ACL is app-layer-only (ADR-0019) with a DB backstop mandated before per-principal ACL is ever enabled.
- **Config/migration/CI (CFG-01…CFG-05, MIG-01/02, CI-01…CI-04):** all working. Fail-closed prod trust guard when ENV unset (R1); test/localhost/`.local`/placeholder active platform rejected outside offline (S2/R1/RW3/RW4/RW6/RW7/RW8); migration-0010 deploy-readiness gate (S4); CI skip-guard + push/merge_group triggers (R5/RW2); both DB harnesses live-host-guarded before bootstrap (R4/RW2); FLAKE-1 root-caused and fixed (R4).

Every target requirement has an implementation location and an automated proof (unit/db/frontend/e2e). No mandatory requirement is supported only by documentation.

## 8. Two consecutive clean audit results

- **Wave 9 — CLEAN.** 5 fresh auditors; 3 independent loopback differentials (21,740 + 856,643 + coordinator's 3,993 = ~882k inputs) → 0 divergences; the one observation (W9-A1-OBS) explicitly "NOT a defect", recorded as a deferred optional CI enhancement.
- **Wave 10 — CLEAN.** 4 fresh auditors; independent 547-input differential → 0 divergences; full core re-swept; no actionable finding of any severity.

Two consecutive fresh independent waves with no actionable core finding — the mandate's exit condition.

## 9. Mutation / mandate boundary coverage checklist

Every mandate-listed mutation boundary has a guarding test proven to fail on the mutation: trust OmniBoost-Test-equivalent in prod (the active `test-*.local` entries — CFG-A fail-closed guard); body-integration over JWT (CIP-A1); frontend-supplied principal (CIP-1); server host-key requirement (host-key 503 fail-closed); host-key↔issuer mismatch (issuer-bound JWKS + CIP-A1); postMessage `'*'` (BIT-4); `event.origin`/`event.source` (BIT-5/6); JWT→sessionStorage write (BIT-3/9, the one weak test found+fixed); `Obi.clear()` on company switch (LC-1/4); old in-flight answer after context switch (LC-4/5); integration metadata filter (AUTH-5/6); mews reads toast (AUTH-6); restricted Confluence without a trusted principal (CIP-2); migration-0010 readiness (MIG-02). Plus the three loopback-parity controls added this session.

## 10. Readiness ladder (be precise about what is proven)

- ✅ **Locally proven** — the entire core, via deterministic fixtures + self-signed test keys, all suites green, two clean audit waves, mutation-checked.
- ✅ **Proven through simulated host environments** — Playwright embed e2e against a stub host page; the frontend twin run under the real Node runtime in audit differentials.
- ❌ **Proven in Base staging** — NOT done (external).
- ❌ **Proven in Data Hub staging** — NOT done (external).
- ❌ **Ready for production** — NOT claimed.

## 11. Remaining external staging requirements (owner / platform-dev work)

1. **Data Hub** (`datahub` is the only active platform; committed with a `TODO until 4.x` placeholder issuer, so production boot fails closed by design until real values land): obtain its real issuer URL, JWKS URL, browser domains, token endpoint, and confirm the `allowed_integrations` set (currently `["mews","toast","opera-cloud"]` — an OWNER DECISION built to the design default). Add a `docs/embedding/datahub.md` host-handover pack (only mews/toast/opera-cloud exist today).
2. **Base** does not exist as a platform in this repo. A `base` platform entry (issuer/JWKS/domains/token-endpoint/host-key) must be created before any "real Base staging token" acceptance test can run.
3. Each platform stands up a token endpoint minting a ≤60-min RS256/ES256 JWT with `iss` / `aud=obi` / `sub` / `iat` / `exp` + the all-or-none `company_id`/`company_name`/`integration` trio.
4. **Migration 0010** must be applied and verified in the pre-production environment (the readiness gate `check-deploy-readiness` refuses to expose the reader path until the scope-RLS policies exist). It is inert in the local demo (owner role is RLS-exempt) and mandatory before production DB isolation is relied upon.
5. Verify each platform's real issuer/JWKS/domain/token-endpoint/host-key end-to-end with a real staging token before claiming Base-staging / Data-Hub-staging / production readiness.

## 12. Exact reasons for anything not fully proven

- **Real Base / Data Hub staging** — external credentials and platform-dev cooperation not available in this environment; deliberately out of scope for the local loop per the mandate's external-dependency distinction. Reason: no real issuer/JWKS/domains/token-endpoint/host-key; not invented (rule 12).
- **`datahub.allowed_integrations`** — an owner decision built to the design default `["mews","toast","opera-cloud"]`; reversible config; flag before any real deploy.
- **AUTH-7 optional defense-in-depth** (pass `allowed_scopes` into `fetch_parent_texts` instead of `'*'`) — deferred in `future-ideas.md`; would change intentional ADR-0014 behavior for a confirmed non-vulnerability, so it needs a new ADR + a db test; not taken.
- **Mechanized cross-runtime loopback CI differential** (W9-A1-OBS) — deferred in `future-ideas.md`; the twins are proven equivalent (~882k inputs, 0 divergences) and covered by non-vacuous per-side tests, so this is drift-prevention infra, not a coverage gap; owner to weigh the cross-tree coupling cost.

---

*The locally-provable core is hardened and proven to the mandate's clean-exit. No critical/high/medium finding remains. Real-platform production readiness is a separate, later gate as itemized in §11.*
