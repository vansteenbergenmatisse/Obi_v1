# 0019 — Page-Principal ACL Is App-Layer-Only In v1

Status: Accepted
Date: 2026-09-22
Governs: `backend/app/features/retrieval/domain/permission.py` (`PrincipalPermissionPolicy`); `knowledge-base/migrations/versions/0009_reconcile_non_chunk_rls.py` (the `page_restriction` reader policy); the retrieval read path

## Context

The SEC-S3 slice of the Phase-4 embed security-hardening pass (see
`docs/Final_docs/phase-4-embed-security/`) audited how page-level Confluence restrictions are
enforced. The finding (matrix gap CIP-5): the source axis and the knowledge-scope axis both have a
DB-level RLS backstop that fails closed independent of the application (source RLS from ADR-0004;
scope RLS from ADR-0014 / migration 0010). The **page-principal** axis does not. Migration 0009
gives `page_restriction` only a coarse `USING(true)` reader policy, and the actual restriction is
applied in application code (`PrincipalPermissionPolicy.allowed`).

This is safe today only because of a v1 invariant: embedded users have **no principal**.
`build_auth_context` hard-codes `principal=None` on every path (spec §6 — integration-level content
scoping only, no per-person Confluence ACL in v1), so `allowed(page, principal=None)` returns pages
with no restriction set and denies restricted pages. There is no code path that yields a non-None
principal, so the app-layer filter cannot currently be bypassed by a fabricated or reused principal.

The risk is latent, not present: the moment per-principal ACL is enabled (a real principal mapping
lands), the page-principal axis would rely on the application filter alone — weaker than the two
axes that have an RLS backstop, and inconsistent with the "Lock 3" page-permission expectation.

## Decision

1. Record, here and in the ledger, that in v1 page-principal ACL is enforced **only in the
   application layer** and has **no DB/RLS backstop** — a known, accepted defense-in-depth gap
   whose safety rests entirely on the `principal is always None` invariant.
2. Pin that invariant with a regression test so it cannot be silently broken:
   `backend/app/features/retrieval/tests/test_fusion_and_permission.py::test_r3_acl_principalless_reader_default_denies_restricted_pages`
   asserts that with a restriction set present, `PrincipalPermissionPolicy.allowed(page,
   space_id=None, principal=None)` denies a restricted page and allows an unrestricted one.
3. **Before per-principal ACL is ever enabled**, a DB-level RLS backstop for `page_restriction`
   (parity with the source and scope axes) MUST be added, in a new migration, with its own
   fail-closed customer-isolation test. Enabling per-principal ACL without that backstop is a
   blocking regression, not an incremental change.

No production code changes in v1 — the behavior is already correct under the invariant. This ADR
makes the gap explicit and gates the future work.

## Consequences

- The v1 read path is unchanged and correct; the pinning test makes the `principal=None → only
  unrestricted pages` guarantee a hard, checked contract.
- Any future work that introduces a non-None principal is on notice: it carries a mandatory,
  ADR-gated prerequisite (the `page_restriction` RLS backstop + isolation test) before it can ship.
- This ADR is scoped to the page-principal axis only; the source (ADR-0004) and knowledge-scope
  (ADR-0014) axes already have their DB backstops and are unaffected.
