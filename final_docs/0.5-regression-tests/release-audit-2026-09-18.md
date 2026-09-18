# Release audit — regression phase 0.5

**Date:** 2026-09-18
**Branch:** `feat/rag-phase-3.5`
**Commit:** `9a9ab3b` (`chore(rag): update Obi agent/skill harness + project docs for the 0.5 workflow`), plus an uncommitted working tree (the `p0-s0_5-reg-system-overview` regression batch + doc updates).
**Working-tree status at audit time:** modified (uncommitted), 9 files — 5 new test files, `coverage-map.md`, `ledger.md`, `progress-log.md`, `future-ideas.md`. No user changes were reset, stashed, or discarded.
**Remote:** `origin → https://github.com/vansteenbergenmatisse/Obi_v1.git`, upstream `origin/main`.

**Overall result: FAIL.** Test 1, 3, 5 PASS; Test 2 FAIL (one blank built-panel row + one stale row); Test 4 BLOCKED (no staging access/confirmation this session). Per the audit rule, a phase with a failing test, a blocked required live result, and an unmet documentation requirement is not a successful regression phase.

| Test | Result | Evidence |
|---|---|---|
| 1 · Complete local harness | **PASS** (with README staleness fixed as evidence, see §1) | 4/4 targets exit 0; floor 823 ≥ 621; deterministic re-run |
| 2 · All built panels covered | **FAIL at audit → RESOLVED** (doc fix 2026-09-18) | 108 built (not 91); `ov-auth` blank + stale `w-scope` row, both corrected in the coverage map |
| 3 · Tests genuinely protect behavior | **PASS** | ~45 regression tests read; every listed check asserted; one documented xfail |
| 4 · Live staging isolation | **BLOCKED** | no `STAGING_*` URL; no this-session staging confirmation; owner-role creds only |
| 5 · CI blocks regressions | **PASS** | existing 0.5.4 proof verified live, read-only |

---

## Test 1 — Complete local harness — PASS

Run 2026-09-18 from the repo root, clean each time (`test-db` starts/stops its own compose Postgres).

| Command | Exit | Result | Wall | pytest-internal |
|---|---|---|---|---|
| `make test-unit` | 0 | 533 passed, 290 deselected | 17s | 15.72s |
| `make test-db` | 0 | 289 passed, 1 xfailed, 533 deselected | 45s | 40.73s |
| `make test-ui` | 0 | 1 passed (Playwright, `widget-mounts.spec.ts`) | 8s | 6.6s |
| `make eval` | 0 | per-dataset recall@5/mrr/hit_rate@5 + rerank-lift table | 1s | — |

- **Coverage floor:** `pytest --collect-only -q` = **823 tests** ≥ CI floor **621** (`ci.yml` step 4). Met with a wide margin.
- **`test-db` did the full cycle:** compose up → wait for pg_isready → re-apply `01-roles.sql` (both roles/policies) → `alembic upgrade head` → `pytest -m db` (RLS on, both roles) → compose down. Exit propagated.
- **Unit tests need no DB/network:** `-m "not db"`, all gateways/embedders/reranker/Claude are fakes.
- **Browser test is the real Playwright suite** against `/test-hosts/none`, asserting the widget mounts (launcher visible, one `iframe[title="Obi chat"]` at `/embed`).
- **`make eval` exits 0** with real per-dataset metrics — it does **not** print "no gold set yet"; the four bundled datasets satisfy it (documented in `harness.md` §4).
- **Fixture collection (16 pages, `harness.md` §"Fixture pages") includes every required category:** one page per knowledge-scope tag (3001 general, 3002 mews, 3003 operacloud, 3004 toast — all 4 `config/knowledge_scopes.json` tags), a two-label page (3005), a classified page (3006), an unlabeled page (3007), an attachment page (3008), a group-restricted page (3009), an empty page (3010).
- **One shared conftest fixture:** pages load through the shared `gateway` fixture (`FixtureConfluenceGateway`, `app/features/confluence_sync/tests/conftest.py:139`) over `tests/fixtures/confluence/loader.py`; a shared session-autouse fixture provides Postgres + roles + RLS, and a per-test autouse `TRUNCATE ... RESTART IDENTITY CASCADE` + `rollback()` isolates every test.
- **`harness.md` matches Makefile + CI command-for-command** (the four targets and the floor step map 1:1). Two **stale** claims in `harness.md` are flagged, not command/config mismatches: (i) it says "this repo has no git remote configured" — a remote now exists; (ii) its illustrative counts (453 unit / 168 db) predate later batches (now 533 / 289). Neither changes the command mapping.
- **README staleness (documentation requirement):** at audit time `README.md` was dated 2026-09-16 / commit `2ac7e7a` and listed 0.5.1's changed files, not "one accurate line per evidence file." As permitted (evidence files under `final_docs/0.5-regression-tests/`), it was refreshed to the current date/commit with one line per evidence file. Disclosed here rather than silently.

## Test 2 — Coverage of all built panels — FAIL

The audit brief's premise "exactly 91 implemented panel IDs" is **stale.** The canonical design-page source (`tools/panel.py --list`) reports **108 `built`** panels (plus 47 `change`, 29 `build`, 5 `unverified`, 3 `discuss` = 192 total), matching the coverage-map's own header. The real question — are all 108 accounted for — was audited.

- **108 built panels confirmed.** Classification: **100 green** (real cited tests, all verified to exist and be collected — zero fabricated/stale citations in a ~190-test-name sample), **7 boundary-enforced** and documented as such (`cm-sync`, `cm-ingest`, `cm-retrieval`, `cm-agent`, `cm-web`, `sc-frontend`, `sc-backend` — architecture claims enforced by `make boundaries`, no single dedicated test), **0 red-today**, **0 duplicates**.
- **DEFECT (fails Test 2): `ov-auth` is a blank built-panel row** (`coverage-map.md:29`) with no cited test under its own id. Its panel names concrete checks (a forged/modified/expired token is a 401; a body `knowledge_scope` disagreeing with the token is ignored) that *are* proven elsewhere (`r1-auth` → `test_platforms.py::test_hs256_alg_is_forbidden +15`, `em-backend` → `test_token_verifier.py::test_valid_token +20`) but are never cited for `ov-auth`. The 2026-09-18 System-overview batch covered 3 of the 4 `ov-*` panels and left this one stranded. Its only other trace is the narrow, **red/unconfirmed** `ov-auth step 5` needs-live sub-item (real-platform signing key), which does not cover the panel's other checks.
- **DEFECT (data integrity): the main table has 109 rows vs its stated 108.** The extra row is `w-scope` (`coverage-map.md:104`), whose canonical status was demoted `built → change` in 0.4.2 (`ledger.md:18`), so it no longer belongs in a "one row per built panel" table. Its cited test is real (not fabricated) — the row is simply misplaced.

**Resolution 2026-09-18 (documentation only — no code, no new tests, nothing repaired that was red):**
- `ov-auth` row filled with its already-existing, already-green coverage: `test_router_auth_context.py::test_bad_token_is_401_before_search` + `::test_body_scope_disagreeing_with_token_is_ignored` (database, real `/chat` endpoint) and seven verifier-level rejection tests in `test_token_verifier.py` (re-verified: 7 passed; both endpoint tests collect + green in `test-db`). The live-key check stays red under `ov-auth` step 5 in "needs live." Note: `ov-auth` was never in any action-plan protect substep — `p0-s0_5-reg-system-overview` is scoped to exactly `ov-confluence`/`ov-corpus`/`ov-widget` — so the plan's own Phase-0 gate ("every generated regression item ticked") did not require it; this is classification of pre-existing coverage, applied at the auditor's stricter "all built panels" bar.
- `w-scope` row annotated inline as `change`-status / not one of the 108 built, reconciling the row count without deleting a real, green test citation.
With these two corrections, all 108 built panels are accounted for (101 green — including `ov-auth`'s in-repo checks — + 7 boundary-enforced), 0 duplicates, 0 red-today. Test 2's substance is now clean; the FAIL is retained in the header as the honest audit-time finding.

## Test 3 — Tests genuinely protect behavior — PASS

- **~45 regression-added tests read directly** across all eight `p0-s0_5-reg-*` batches. Every listed check has its own real assertion against the real production path (`plan_chunks`, `run_once`/`index_page` through the real sync worker, `HybridRetriever.retrieve`, the real FastAPI `/chat` + feedback via `TestClient`, live Postgres catalog/RLS queries as the real `rag_reader` role, the Anthropic-shaped client over `httpx.MockTransport`, the Next.js route handlers/`ChatSessionProvider` over mocked `fetch`), asserting independently-derived values (Postgres's own `to_tsvector`, spies capturing `SELECT current_user`, computed token counts, hex/luminance math) — not restated constants.
- **No weak/invalid tests found** among the regression set: none crash-only, tautological, mock-the-behavior-under-test, production-path-bypassing, order-dependent, external-network, or unseeded-nondeterministic.
- **Skips/xfails:** exactly one in the whole tree — `test_worker_sync.py::test_delete_marks_the_active_version_superseded`, strict `xfail`, panel `tg-deactivate`, Planned/substep 2.2.4, documented in `harness.md` + `docs/plan/decisions.md`. Accepted. No other skip/xfail/`assert True`/TODO anywhere in `apps/automation` or `apps/web/src`.
- **No real network in any test** (all `httpx.MockTransport` / mocked `fetch`; the shared gateway is the `FixtureConfluenceGateway` fake). DB tests truncate + rollback per test (`conftest.py:120-135`). The one `time.sleep` reference is a monkeypatch stub, not a real sleep.
- **Determinism:** the full unit+db suite was run a **second time** (fresh compose DB) — identical outcomes (unit 533 passed; db 289 passed + 1 xfailed), same collected set. Deterministic.
- **Disclosed (pre-existing, inert):** the coverage-map notes an order-sensitivity in `test_reader_rls_reconcile.py` under `pytest-randomly`; that plugin is **not** a project dependency (absent from `pyproject.toml`/`uv.lock`), so it cannot trigger in the repo's actual `make test-db`/CI run. Tracked, not a regression-batch defect.

## Test 4 — Live staging isolation — BLOCKED

**Not run this session — no fresh live output was produced, and none was fabricated.**

- **No dedicated staging config exists.** `STAGING_DATABASE_URL` / `STAGING_DATABASE_READER_URL` are **not set** in `.env`. The only Supabase URLs are the general `DATABASE_URL` / `DATABASE_READER_URL`, both pointing at `aws-1-eu-west-1.pooler.supabase.com` — the same host tied to two prior **safety incidents** in this project (stray live writes, `docs/Final_docs/ledger.md` "Need from you").
- **No this-session confirmation that the resolved host is staging, not production.** The prior run's "owner-confirmed staging" was on 2026-09-16; the audit rule is "Never use production for live testing" and "confirm staging + read-only" first.
- **The available credential is the owner/writer role**, not a read-only one; the isolation script (`scripts/setup_supabase.py verify-isolation`) would connect with it. This does not satisfy the "connection is read-only" requirement on its face.
- **Even the last successful run was not all-green:** the coverage-map "needs live" table records the 2026-09-16 run as **6 green / 6 red** (e.g. `cm-infra` prod-on-Supabase, `sc-user`, `e-ops` figures, `em-hostbackend`, `ov-auth step 5`). So the needs-live set is not fully proven regardless of access.

**What is needed to unblock:** (1) explicit owner confirmation this session that `aws-1-eu-west-1.pooler.supabase.com` is the staging (non-production) project; (2) a dedicated **read-only** `STAGING_DATABASE_URL`/reader so the check runs isolated from any write role; then a fresh `verify-isolation` run saved to `live-isolation-2026-09-18.txt`, plus resolution of the 6 previously-red needs-live items.

## Test 5 — CI blocks regressions — PASS (existing proof verified live, read-only)

A complete CI-gate proof already exists from substep 0.5.4 (`ci-gate-proof.md`, 2026-09-16). Rather than open a new PR and push a fresh deliberate break (redundant outward activity on a real repo), the recorded proof was **verified against the live GitHub API, read-only**, on 2026-09-18:

- **Required check on `main`:** `gh api .../branches/main/protection` → required contexts `["obi four-level check (0.5.1)"]`, `strict: true`, `enforce_admins: true`. Matches `ci-gate-proof.md` exactly; a PR cannot merge until that check passes, admins included.
- **Red run** `35151345624` → status `completed`, conclusion **`failure`** (the deliberate webhook-HMAC break; failing test `test_bad_signature_is_rejected`, `assert 200 == 401`).
- **Green run** `35151531728` → status `completed`, conclusion **`success`** (after revert).
- **Temp branch** `prove-gate-2026-09-16` → `404 Branch not found` (deleted).
- **PR #1** → state **`CLOSED`**, unmerged, title "…(0.5.4 proof, not for merge)".

All artifacts are genuine and current. The CI workflow (`.github/workflows/ci.yml`) runs the four `make` targets + the coverage floor on every `pull_request`.

---

## Roll-up

- **Overall:** FAIL.
- **Branch / commit:** `feat/rag-phase-3.5` @ `9a9ab3b` (+ uncommitted working tree).
- **Test totals by level:** unit 533 passed · db 289 passed + 1 xfailed · browser 1 passed · eval exit 0 · **823 collected** (floor 621).
- **Panels:** 108 built — 107 accounted for (100 green + 7 boundary-enforced), **1 blank (`ov-auth`)**; 0 duplicates; 0 red-today; 1 stale row (`w-scope`, now `change`).
- **Behavioral checks verified:** every listed check across the 8 `p0-s0_5-reg-*` batches (~45 tests read); per-panel counts in Test 3.
- **Coverage vs floor:** 823 / 621 = 132% of the required floor. Panel coverage 107/108 = 99.1% classified.
- **Timings:** test-unit 17s · test-db 45s · test-ui 8s · eval 1s (wall via make).
- **Live checks:** BLOCKED — 0 run this session; last run (2026-09-16) 6 green / 6 red.
- **Red today:** none (no failing test); the `ov-auth` gap is a missing citation, not a red test.
- **Weak / skipped / nondeterministic:** none among the regression set beyond the one documented strict `tg-deactivate` xfail; one disclosed, inert order-sensitivity.
- **Evidence files created/updated this audit:** `release-audit-2026-09-18.md` (new), `README.md` (refreshed to current date/commit + one line per evidence file), `ci-gate-proof.md` (re-verification note appended). No `live-isolation-2026-09-18.txt` was created — Test 4 is BLOCKED and no live run occurred.

## Single next action (result is still not PASS)

Test 2's coverage-map defects were resolved on 2026-09-18 (above). The **one remaining blocker to a
green phase is Test 4**: obtain explicit owner confirmation that `aws-1-eu-west-1.pooler.supabase.com`
is the staging (non-production) project, plus a **read-only** `STAGING_DATABASE_URL`, then re-run the
live isolation check fresh into `live-isolation-2026-09-18.txt` and resolve the 6 previously-red
needs-live items. Until then the overall result stays FAIL (a blocked required live result is not a
successful regression phase).
