# Phase-4 embed security-hardening pass

The single home for the owner-requested **implementation → independent-audit → repair → re-audit** loop over the Obi embed / JWT security core. Start here.

> **This is not a numbered action-plan substep.** It is a security-hardening pass, requested by the owner as a closed audit loop, over work that already landed under Phase 4 / PLAN 11.1c / ADR-0014. It runs on branch `feat/rag-phase-4-embed-security-hardening`. Ledger and progress-log entries for this pass are marked `SEC-*` and say so, so the append-only record stays honest about what was substep work and what was this hardening pass.

## What lives here

- `traceability-matrix.md` — the requirement-traceability matrix and 15-item test-contract coverage from the initial research wave (six independent read-only auditors + synthesis). One row per requirement: required behavior, current behavior, status, implementation location, existing/missing tests, smallest change, severity, evidence. Includes the premise-verification table (which mandate assumptions were confirmed vs refuted) and the prioritized gap list.
- `loop-log.md` — the running record of each loop wave: implementation slices, audit findings, triage verdicts, repairs, mutation-test results, and the two-consecutive-clean-wave exit gate. (Appended as the loop runs.)

## The gap slices

Grouped non-overlapping from the matrix, run in priority order (HIGH-severity first):

- **S1 — embed lifecycle & logout** (frontend): LC-1/LC-4 (obi:clear a real logout), LC-5 (cleared-token race), LC-2/3/6 (silent scope switch + 401 handling), BIT-7 (obi:token runtime validation).
- **S2 — production config guard** (backend + frontend): CFG-02 (no test/placeholder platform active in prod), CFG-04 (no localhost domain in prod CSP), CFG-05 (one env signal).
- **S3 — backend identity & defense-in-depth**: CIP-4 (issuer-namespaced token_subject), BIT-10 (server-only trip-wire), CIP-5 (record page-ACL is app-layer-only).
- **S4 — migration 0010 deploy gate**: MIG-02 (deploy-blocking readiness check).
- **S5 — regression-test-only coverage**: AUTH-6/AUTH-7, CIP-1/2/3, AUTHRT-2/3/4.

## Exit criterion

The loop ends only on the mandate's clean-exit: every actionable gap has an implementation location and an automated (or explicitly-named staging) proof; all suites green; every targeted mutation caught by the tests; no unresolved critical/high/medium core finding; docs + ledger match the code; and **two consecutive fresh independent audit waves produce no new actionable core finding.**

## External-dependency line

Local + CI proof uses deterministic fixtures and self-signed test keys. Real **Data Hub** / **Base** production readiness is a separate gate (real issuer, JWKS, domains, token endpoint, host key, and migration `0010` applied + verified in pre-production) and is **not** claimed by this pass.
