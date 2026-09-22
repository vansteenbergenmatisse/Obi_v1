# Phase-4 embed security loop — wave log

Append-only. One section per wave. Never edit a prior wave; a correction is a new dated note.

## Wave 0 — Research & requirement-traceability matrix (2026-09-22)

Six independent read-only research agents (auth & host-key, browser/iframe, authorization/isolation, Confluence/identity, lifecycle/stale-state, config/migration/CI) inspected code, config, tests, migrations, and docs — reaching conclusions from the code itself, not the plan. One agent (auth & host-key) hit a structured-output failure on the first run and was re-run standalone. A synthesis pass built `traceability-matrix.md`.

**Baseline (green) before any change:** `make boundaries` OK · backend unit 529 passed · knowledge-base unit 17 passed · frontend vitest 240 passed · Playwright e2e 4 passed.

**Headline findings.** The backend auth/authorization core is correctly built and well-tested (JWT chain, RESTRICTIVE RLS migration 0010 fail-closed, host-key constant-time + server-only, body-cannot-override-token, cache keys bound to scope+subject). Genuine gaps cluster in: frontend embed lifecycle (obi:clear is not a real logout; token-fetch race; silent scope switch), production config (no guard against test/localhost platforms or domains in prod), and backend identity (token_subject not issuer-namespaced). Five mandate premises **refuted**: token_subject not namespaced; obi:clear does not drop in-flight answers; a token refresh can silently change scope; there are no `docs/brief` runbooks (three packs in `docs/embedding/`); test/localhost platforms are not rejected in production. "Base" and "OmniBoost Test" do not exist as named platforms (confirmed).

**Gap → slice grouping:** see README. Owner decisions: fix **all actionable gaps**; execute **autonomously, committing each verified slice** (green gate + ledger entry), reporting at each audit-wave boundary.

### Implementation slices

**S1 — embed lifecycle & logout — DONE (committed).** Implemented by an independent implementation agent, test-first; verified independently in the main window. Closed LC-1/LC-4 (obi:clear now routes through the chat session's `restart()` — aborts the in-flight stream, clears messages + conversationId — so it is a real logout, not a panel hide), LC-5 (module-scoped epoch guard drops a stale in-flight token fetch after clear/re-point), LC-2/3/6 (bridge decodes display-only integration+company claims and resets the conversation on a scope-changing renewal; a 401 drives a subscribed onUnauthorized→restart), BIT-7 (runtime non-empty-string guard on the obi:token field). 9 new tests. **Gate:** vitest 240→249 passed · typecheck clean · Playwright embed e2e 4 passed · boundaries green. Client-side claim decode is display/equality-only, never trust-bearing (backend TokenVerifier stays authoritative). Files: app/embed/embed-frame.tsx, features/chat/index.ts, features/embed/{iframe-bridge,loader}.ts + 3 test files.

_S2 — production config guard: next._
