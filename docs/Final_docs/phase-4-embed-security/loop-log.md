# Phase-4 embed security loop — wave log

Append-only. One section per wave. Never edit a prior wave; a correction is a new dated note.

## Wave 0 — Research & requirement-traceability matrix (2026-09-22)

Six independent read-only research agents (auth & host-key, browser/iframe, authorization/isolation, Confluence/identity, lifecycle/stale-state, config/migration/CI) inspected code, config, tests, migrations, and docs — reaching conclusions from the code itself, not the plan. One agent (auth & host-key) hit a structured-output failure on the first run and was re-run standalone. A synthesis pass built `traceability-matrix.md`.

**Baseline (green) before any change:** `make boundaries` OK · backend unit 529 passed · knowledge-base unit 17 passed · frontend vitest 240 passed · Playwright e2e 4 passed.

**Headline findings.** The backend auth/authorization core is correctly built and well-tested (JWT chain, RESTRICTIVE RLS migration 0010 fail-closed, host-key constant-time + server-only, body-cannot-override-token, cache keys bound to scope+subject). Genuine gaps cluster in: frontend embed lifecycle (obi:clear is not a real logout; token-fetch race; silent scope switch), production config (no guard against test/localhost platforms or domains in prod), and backend identity (token_subject not issuer-namespaced). Five mandate premises **refuted**: token_subject not namespaced; obi:clear does not drop in-flight answers; a token refresh can silently change scope; there are no `docs/brief` runbooks (three packs in `docs/embedding/`); test/localhost platforms are not rejected in production. "Base" and "OmniBoost Test" do not exist as named platforms (confirmed).

**Gap → slice grouping:** see README. Owner decisions: fix **all actionable gaps**; execute **autonomously, committing each verified slice** (green gate + ledger entry), reporting at each audit-wave boundary.

### Implementation slices

_S1 — embed lifecycle & logout: recorded below as it completes._
