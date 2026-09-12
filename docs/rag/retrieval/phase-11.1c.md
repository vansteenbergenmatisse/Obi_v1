# Phase 11.1c — Obi embed + JWT edge binding (read-path)

**Status:** 🟩 code + tests done (2026-09-12), committed on `feat/rag-phase-3.5`. Read/answer path
only — no ingestion counterpart. Sits on top of the Phase 11.1a DB backstop (ADR-0014 scope-GUC RLS).
Design of record: [`../../embedding/PHASE-11.1c-obi-embed-jwt-spec.md`](../../embedding/PHASE-11.1c-obi-embed-jwt-spec.md)
+ [`../../adr/0014-Customer-Scope-Isolation-Backstop.md`](../../adr/0014-Customer-Scope-Isolation-Backstop.md).

## What changed on the read path

Before 11.1c the knowledge scope was a **caller-reported** `knowledge_scope` string in the `/chat`
body. Now it is derived from a **platform-signed JWT verified server-side** — the customer/integration
boundary is bound at the edge, not trusted from the caller.

Per-request flow on `POST /chat`:

1. **Host key first** — `_verify_api_key` (unchanged shared-secret `chat_api_key`) gates the endpoint.
2. **Token → identity** — `_resolve_auth_context` reads the `X-Obi-Token` header. Absent → the
   general-only `AuthContext` (tokenless internal/eval/pilot path). Present → `TokenVerifier.verify`
   (alg allow-list, never HS256; JWKS-by-`kid` with a finite fetch timeout; `iss` ∈ `platforms.json`;
   `aud=obi`; `exp`/`iat` required; lifetime bounded by the platform max; business claims
   all-three-or-none) → `build_auth_context` maps the verified `integration` to `allowed_scopes`
   (`obi-general-test` always included). A bad token or an unknown integration → **401 before search**.
3. **Body scope is no longer authoritative** — a body `knowledge_scope` that is well-shaped but not a
   recognized slug → **400**; a recognized slug that disagrees with the token's scopes → logged and
   ignored. Body `principal` is ignored entirely (v1 embedded users are principal-less).
4. **Scope drives every reader txn** — `AnswerService.answer(history, auth)` passes
   `auth.allowed_scopes` to `retrieve_with_context`, which sets the `app.allowed_knowledge_scopes`
   GUC (RESTRICTIVE RLS, ADR-0014) — so isolation holds at the DB even if the app predicate is off.
5. **Rate limit + caches keyed on the verified identity** — the rate-limit key is
   `sub:<sha256(token_subject)>` (falls back to client IP when tokenless); the idempotency and
   answer caches bind to `(history, principal, allowed_scopes, token_subject)`. The raw token is
   never a key, never logged, never persisted.
6. **Audit** — `query_trace.subject_hash` records `sha256(sub)` (migration `0011`) — never the raw
   subject or token.

## Files (read/answer path)

- `apps/automation/app/platform/config/platforms.py` + `config/platforms.json` — trusted-issuer +
  integration→scope registry, validated at startup (Task A1).
- `apps/automation/app/features/rag_agent/server/token_verifier.py` — `TokenVerifier` / `VerifiedClaims`
  (A3).
- `apps/automation/app/features/rag_agent/application/auth_context.py` — `AuthContext`,
  `build_auth_context`, `general_only_context` (A2).
- `apps/automation/app/features/rag_agent/server/router.py` — `X-Obi-Token` dependency, body-scope
  validation, rate-limit key, wiring (B1).
- `apps/automation/app/features/rag_agent/application/answer_service.py` +
  `application/answer_cache.py` — `answer(history, auth)`, cache key, `subject_hash` persistence (B1/B2).
- `apps/automation/app/main.py` — builds `TokenVerifier` at startup (fail-fast on a bad registry).
- `apps/automation/alembic/versions/0011_query_trace_subject_hash.py` + `platform/db/models.py` (B2).

Frontend counterpart (host loader + `/embed` frame + test hosts) is under `apps/web` — see the
implementation plan and `docs/embedding/obi-embed-local-test-keys.md`.

### Embed UX (host launcher + `/embed` frame) — updated 2026-09-12

The host-page launcher and the framed chat now mirror the main-site widget exactly:

- **`apps/web/src/features/embed/loader.ts`** (bundled to `public/obi.js`) injects the **same "star"
  launcher as the main site** — Obi's two-tone sparkle in a 52px white round button with the
  `ChatLauncher` border/shadow/hover tokens, inlined as literals since the bundle runs in the host
  realm with no Tailwind (kept in lockstep with `features/chat/ui/{chat-launcher,assistant-mark}.tsx`).
  It is a **toggle**: click opens (show iframe + `obi:open`), click again hides it (token/conversation
  kept; `Obi.clear()` is the real logout). The iframe sits **above** the launcher so the open panel
  never overlaps it.
- **`apps/web/src/app/embed/embed-frame.tsx`** renders the **panel directly** (`FloatingFrame` +
  `PanelBody`) on `obi:open`, not the full `ChatWidget` — the host launcher is the only launcher, so
  there is no second, nested one inside the frame, and one click goes straight to the panel. The
  embedded panel shows no Close (X) chrome; the host launcher is the single open/close control.
- `obi:open` now drives the frame (via `initIframeBridge`'s new `onOpen`), still accepted only from an
  allowed parent origin — the postMessage contract is unchanged (still exactly `obi:open`/`obi:token`/
  `obi:clear`); only its UI effect was wired up.

**Local-testing gotcha:** the backend must be started with `PLATFORMS_PATH` pointing at
`config/platforms.local.json` (the same value `apps/web/.env.local` uses). Without it the backend loads
the committed `config/platforms.json`, which has no `test-*` issuers, so every test-host token is
rejected and `/chat` returns **401** (`request failed (401)` in the widget). Both apps must read the
same registry — see `docs/embedding/obi-embed-local-test-keys.md`.

## Security baseline (surface: POST /chat, tier LLM-CALL — 11.1c delta only)

```yaml
security_baseline:
  applies: true
  surfaces:
    - id: POST /chat (X-Obi-Token edge binding)
      tier: LLM-CALL
      controls:
        C1_auth:        { status: covered, mechanism: "host chat_api_key + verified platform JWT (alg allow-list, JWKS-by-kid, iss/aud/exp/iat, lifetime bound); bad/unknown -> 401" }
        C2_rate_limit:  { status: covered, mechanism: "keyed on sha256(token_subject), IP fallback" }
        C3_input:       { status: covered, mechanism: "body knowledge_scope validated (400 unrecognized) then ignored; body principal ignored" }
        C4_timeout:     { status: covered, mechanism: "finite JWKS fetch timeout + per-issuer cache; existing retrieval/answer timeout/retry/breaker" }
        C6_redaction:   { status: covered, mechanism: "unchanged; token never logged, only sha256(sub) traced" }
        C9_audit:       { status: covered, mechanism: "query_trace.subject_hash = sha256(sub); never raw subject/token" }
        C10_abuse:      { status: covered, mechanism: "per-subject rate limit + existing LLM cost/abuse caps" }
```

## Posture change (documented, not a bug)

Task D4 retired the pilot `WIDGET_ACCESS_TOKEN` (the browser→proxy shared secret). The Next proxy
is now open: a tokenless request reaches the backend as **general-only** (the general corpus is
intentionally public for an embeddable widget), and scoped content still requires a verified token.
Backend rate-limiting, input validation, cost caps, and scope isolation all remain in force.

## Live prerequisites (operator-gated — do not block local dev)

- Apply migrations `0010` then `0011` to Supabase (`uv run alembic upgrade head`).
- Real platform `issuer` / `jwks_url` / `domains` / `integration` for Mews, Toast, Opera Cloud (kept
  `active:false` in `config/platforms.json` until provided) — see the hand-over packs
  `docs/embedding/{mews,toast,opera-cloud}.md`.
- Test companies (one per integration) + a restricted-group test user for the per-user ACL (a later
  phase; v1 is integration-level, `principal=None`).
