# 0017 — Edge Token Verification

Status: Accepted
Date: 2026-09-18
Governs: apps/automation (rag_agent/server, rag_agent/application, platform/db, alembic),
apps/web (chat proxy)

> **Retroactive ADR.** This records a decision already shipped and covered by tests; it
> documents existing behavior, it does not change it. Written to close a documentation gap
> (cm-docs). It complements ADR-0014 (RLS isolation backstop): 0014 governs the database
> locks; this ADR governs how the request's identity and scope are established at the gate.

## Context

The widget is embedded in third-party host applications. Each host hands the widget a signed
JWT ("the note"). The backend must trust identity, company and integration **only** from a
verified token, never from the request body (never-bend rules #2 and #3), and it must fail
closed. Two distinct credentials are in play: the per-request user token (identity/scope) and
the host API key (caller authentication of the proxy).

## Decision

1. **Two credentials, two headers.** The frontend proxy authenticates itself to the backend
   with the host key on `Authorization: Bearer <CHAT_API_KEY>` (server-side only, fails
   closed if unset — `apps/web/src/platform/automation-api/client.ts:23-64`), and forwards
   the end-user JWT separately on `x-obi-token`. The incoming `Authorization` from the
   browser is **never** forwarded back out (`route-handlers.ts:61-71`). Backend host-key
   check is a constant-time compare with rotation overlap (`router.py:317-330`).

2. **Verification order is fixed** (`rag_agent/server/token_verifier.py::verify`):
   1. read `iss` unverified → look up the platform registry entry; unknown issuer → reject;
   2. **algorithm allow-list**, checked before any key work; `HS*` is always rejected
      (blocks an RS256→HS256 downgrade);
   3. resolve the signing key by `kid` via a cached `PyJWKClient` (JWKS, 5s timeout);
   4. verify signature + registered claims with `require = (exp, iat, iss, aud, sub)`,
      `audience = "obi"`, matching issuer, 60s leeway;
   5. enforce the per-platform maximum token lifetime (`exp - iat`);
   6. business claims (`company_id`, `company_name`, `integration`) are all-three-or-none.
   Any non-`TokenError` collapses to `TokenError("invalid token")` → a bare 401. HS256 is
   also rejected at registry load (`platforms.py:81-82`).

3. **One authorization context, built at the gate.** `_resolve_auth_context`
   (`router.py:252-266`): no `x-obi-token` → `general_only_context()` (scopes =
   `("obi-general-test",)`, no principal); otherwise `build_auth_context(claims, registry)`
   maps `integration` → allowed scopes (`UnknownIntegrationError` → 401). The resulting
   `AuthContext` (`rag_agent/application/auth_context.py`) carries
   `allowed_scopes` / `allowed_sources` / `company_*` / `token_subject`; `company_*` is for
   audit only, never a scope axis. `allowed_scopes` drives every scoped read.

4. **The body never decides access.** A body `knowledge_scope` is validated for shape and
   membership only; a recognized-but-disagreeing value is logged
   (`body_knowledge_scope_ignored`) and ignored; the body `principal` is not used for scope
   (`router.py:272-287`).

5. **Only a hash of the subject is persisted.** `query_trace.subject_hash` =
   `sha256(verified subject).hex()`, nullable on the tokenless internal/eval path
   (`answer_service.py:246`, `models.py:553-555`, migration
   `0011_query_trace_subject_hash.py`). The raw subject and the token itself are never
   stored, logged, or placed in a URL (never-bend rule #10). The rate-limit key is likewise
   `sub:<hash>` (`router.py:340`).

## Reason / Consequences

- Trust flows from a cryptographically verified token, resolved against a per-platform
  registry, with the alg allow-list and lifetime bound closing the common JWT downgrade and
  long-lived-token attacks.
- A single `AuthContext` built once at the gate is what every downstream read uses, so no
  read can run under looser rules than the search (never-bend rule #3).
- v1 embedded users have no per-person ACL: `principal` is `None`; isolation is by
  company/integration scope plus the RLS backstop (ADR-0014).

Cross-references: ADR-0014 (customer-scope isolation backstop / RLS), ADR-0011 (knowledge
scopes), never-bend rules #2, #3, #10.

Tests: `test_token_verifier.py`, `test_token_claims_contract.py` (schema `required` matches
`REQUIRED_CLAIMS`), `test_auth_context.py`, `test_edge_auth.py`, `test_router_auth_context.py`,
`test_chat_endpoint.py` (body scope / principal non-authoritative; `subject_hash` persisted),
`test_migration_0011_subject_hash.py`.
