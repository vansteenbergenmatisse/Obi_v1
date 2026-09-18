# Future ideas — deferred by design, not lost

Things we know we will want and choose not to do now, so they are not lost. One section per
idea: what it is, why it is deferred, where in the plan it would land, and the date added. This
is the substep-1.3.1 ideas file named by CLAUDE.md's "where the truth lives" — a distinct,
narrowly-scoped list of deferred *plan-adjacent* features, not the broader ad hoc backlog kept at
`docs/future-ideas/IDEAS.md`.

---

# Owner decisions surfaced 2026-09-18 — page-vs-code drifts to rule on

This holds design-page-vs-code drifts where the tests assert the real (code) behavior, so they are
green today, but each is a latent red the moment anyone asserts the panel's stated claim. Each needs
your one-word call: implement the behavior, or correct the page. (The two infra blockers found in the
same pass — the local test-DB routing and the missing git remote — were moved to the deferred list
below on 2026-09-18 at the owner's request. The safety caution on the DB-routing one still stands.)

## DECISION · Four design-page-vs-code drifts: implement the behavior, or correct the page
What: four panels where the design page claims behavior the code does not have. The regression
tests assert the **real** (code) behavior, so they are green today — but each is a latent red the
moment anyone asserts the panel's stated claim. For each, you decide: **build the missing behavior**
or **fix the panel text**.
- `ov-confluence`: the "APIs used" line lists labels under v1; the code reads labels from v2
  (`/api/v2/pages/{id}/labels`). Likely a page-text fix.
- `r1-limits`: ~~the panel claims an `X-Forwarded-For` client-IP rate-limit fallback for untokened
  requests; no such code exists.~~ **RESOLVED 2026-09-18** (decision `r1-limits-ipkey`): drop the
  claim, keep `request.client.host`; the panel today-line is corrected and a regression test pins
  that a forged XFF header changes nothing. `TRUSTED_PROXY_HOPS` (default 0) is added by 3.2.6 and
  set for real in 7.1.1. See `docs/plan/decisions.md` (`r1-limits-ipkey`, open `trusted-proxy-hops`).
- `w-composer`: the panel claims a 5 MB per-image size cap; nothing enforces byte size (only
  count = 4). Decide whether to enforce a size cap or correct the page.
- `d-event_ledger`: the panel's Columns list names an `actor` column that does not exist (only
  `actor_account_id`, and it's never persisted to `event_ledger`). Likely a page-text fix.
**What you should do:** for each of the four, say "implement" or "correct the page." The
correct-the-page ones I can batch into a single design-review pass; the implement ones become their
own substeps with their own tests.
Where it would go: a design-review pass (page-text fixes) plus per-panel substeps for any you want
built; panels ov-confluence, r1-limits, w-composer, d-event_ledger.
Added: 2026-09-18

---

## Multilingual keyword index instead of translation
What: Build the keyword-search index (r2-keyword) directly against each source language's own
word forms — a per-language tsvector configuration or a genuinely multilingual index — instead of
always translating a non-English question to English before search (rule 9) against an
English-only corpus.
Why not now: The whole pipeline is built around one contract — translate the question in,
translate the checked answer back out, keep citations and the trace in English — and every source
document is authored in English today. Building a second index shape now would duplicate the
keyword-search path with no non-English source content yet to search against it.
Where it would go: Phase 3, stage 2; panels r1-rewrite, r2-keyword.
Added: 2026-09-16

## Per-question cost tracking with a monthly total
What: Record the token/dollar cost of every model call a question triggers (rewrite, embed,
rerank, generate, and later the support judge) on its query_trace row, and roll those up into a
running monthly total per company or per deployment.
Why not now: query_trace (d-query_trace) carries no cost field today and no per-call cost is
captured anywhere in the pipeline; this needs a schema addition and a place to read the totals
back out (a dashboard or a report), neither of which exists yet.
Where it would go: Phase 5, telemetry; panel d-query_trace.
Added: 2026-09-16

## Live streaming with per-sentence checks (show, then verify)
What: Show the answer sentence by sentence as the model writes it, run the support judge (r5-
ground) on each sentence in parallel, and mark or retract a sentence that fails after it has
already been shown. Today the person waits 7 to 9 seconds because every sentence is checked
before anything is sent — r5-stream's own note records this: "Not live generation streaming...
Live streaming would need per-sentence citation checking and is not built."
Why not now: a shown sentence cannot be unshown; the retract path needs a UI state and a measured
judge latency (5.2.2) before it is safe. Accuracy before speed is the decision in decisions.md.
Where it would go: Phase 3, stage 5, after 3.6.4; panels r5-stream, r5-ground; the widget's bubble
rendering (w-panel).
Added: 2026-09-16
Depends on: the judge's p95 from 5.2.2 and a rule for what the person sees when a sentence is
retracted.

## The reranker v4 and Voyage bake-offs on the gold set
What: swap the Cohere reranker for the current v4 model and recalibrate the refusal threshold on
the same run. rerank-v3.5 is live today; v4.0-pro and v4.0-fast exist (December 2025, 32k
context) but aren't adopted. Cohere sits at stage 4, scores each candidate chunk next to the
question, and after 3.1.3 reads the exact child that matched.
Why not now: a model swap moves every score, so the refusal threshold (3.5.3) and the coverage
band (3.6.2) must be recalibrated together, and that needs the full gold set from 6.1 — the gold
set (e-gold) doesn't exist yet.
Where it would go: Phase 6, next to 6.1.3; panels r4-rerank, r4-weak, e-gold.
Added: 2026-09-16
Done when: precision at 5 and the unsupported rate on held-out are both no worse than before, in
one before-and-after row.

## Company-specific content rules
What: let a company configure rules that change how an answer is built for their questions
specifically — e.g. always mention their contract tier, never suggest a competitor's feature,
phrase answers a certain way — read alongside the authorization context (r1-ctx) at stage 1.
Why not now: r1-ctx carries only identity and access-scope fields today (company_id, integration,
allowed_scopes), not behavior-changing configuration; there is no data model or admin surface for
a company to set its own rules, and folding per-company prompt rules into a shared prompt is
untested territory for the citation/refusal guarantees.
Where it would go: Phase 3, stage 1 (build the authorization context); panel r1-ctx.
Added: 2026-09-16

## Per-person Confluence permissions for embedded users
What: resolve page-level access (r3-acl) per the actual embedded end-user's own Confluence
identity, not just per company/integration — so a permission-restricted page is honored per
person, the way it already is for a native Confluence user.
Why not now: the signed note (em-token) carries no per-person Confluence identity today — it's
still a stand-in with no values configured — and page_restriction resolution (r3-acl) has no path
from an embedded widget user to a real Confluence principal to check against.
Where it would go: Phase 4; panels em-token, r3-acl.
Added: 2026-09-16

## Agentic retrieval, one loop at a time
What: let the model decide the next step instead of one fixed pass. Three loops, in this order:
(a) search each question part from 3.2.4 separately and search again only for the parts the
coverage check found empty; (b) multi-hop: when a chunk links to another Confluence page, follow
the link and treat the page as a candidate; (c) tool use: call a Confluence search or a platform
API (Mews, Toast) when the corpus has no answer, with the result cited like a chunk.
Why not now: every loop is another model call (latency) and another chance to talk itself into a
wrong answer (accuracy). The two-extra-reads rule (3.3.3, 3.5.1) is the current limit and it is in
the rules that never bend.
Where it would go: Phase 3, stage 2 and stage 5, after the held-out numbers from 6.1 exist;
panels r1-rewrite, r2-prov, r4-fallback, r5-coverage.
Added: 2026-09-16
Rule for adding any loop: one at a time, behind a setting, with a before-and-after row on
held-out; keep it only if recall rises and the unsupported rate does not. The support check and
the refusal rules stay as the last wall regardless of how many loops run.

## Semantic answer cache, rejected once
What: cache a generated answer keyed by semantic similarity of the question (not just an exact
string/history match) and serve it again for a close-enough repeat question, skipping retrieval
and generation.
Why not now: rejected outright, not merely deferred — a cached answer can silently outlive a
permission change (3.2.7): if a page's access changes after the answer was cached, replaying it
would show content the asker may no longer be allowed to see. The exact-match answer cache in
cm-agent is already marked "(to remove)" for a related reason; a semantic (fuzzy-match) cache
widens that same exposure instead of closing it.
Where it would go: nowhere planned — stays rejected unless a cache-invalidation story for 3.2.7 is
designed first; panel cm-agent.
Added: 2026-09-16

## Gate "Protect" regression batches on retrieval quality, not just plumbing
What: after a "Protect" batch (e.g. the vector-database or relational-database panels) adds its
structural regression tests, also run features/evaluation's gold-set runner (make eval) and record
a before-and-after row — so a change that keeps every new structural test green (index exists, RLS
still hides a forbidden row, the embedding provider is still shared, etc.) but silently degrades
precision@k, recall@k, or faithfulness still gets caught before it ships.
Why not now: today's "Protect" tests are deliberately narrow — they prove the plumbing a panel
describes still behaves exactly as documented, nothing about whether retrieval is *good*. Gold-set
evaluation is a slower, separate harness (features/evaluation/, make eval) built for that question;
folding a full eval run into every fast structural-regression batch would blow up what is meant to
be a quick gate. Two related gaps are already tracked elsewhere, not duplicated here: the embedding
model/dimension itself is a live, unresolved choice (vd-model in docs/plan/decisions.md), and
reranking (r4-rerank) already has its own dedicated regression tests from an earlier batch.
Where it would go: features/evaluation/; likely paired with the CI-gate substep (0.5.4) or
whichever substep next extends the "Protect" batch pattern.
Added: 2026-09-17

## An agreed auth service to sign the note (em-hostbackend)
What: a shared, agreed authentication service that signs the platform's note (the JWT the widget
receives), instead of each platform/owner signing it directly.
Why not now: the owner signs the notes directly for now ("I sign the notes", 2026-09-18); whether a
separate agreed auth service should exist "depends" and cannot be decided yet. It describes a system
outside this repo, so no code here implements or checks it.
Where it would go: Phase 4 / the token contract; panels em-hostbackend, em-token, ov-auth.
Added: 2026-09-18
Blocked on: the owner's call on which team/system owns note-signing at scale.

## A real platform signing key to verify the note end-to-end (ov-auth)
What: verify the note's alg/signature/issuer/audience/expiry against a real platform's live signing
key (ov-auth step 5), end-to-end, not just against synthetic test-host keys.
Why not now: no real platform signing key exists to test against yet (2026-09-18). The verification
code and its tests already run against synthetic keys (`test_token_verifier.py`); only the live-key
proof is missing.
Where it would go: Phase 7 (environments) live checks; panel ov-auth.
Added: 2026-09-18
Blocked on: a real platform (Data Hub first) issuing a signing key.

## A real per-person identity flow to shape the identity mapping (sc-user)
What: a real embedded end-user identity flow so the per-person identity mapping (sc-user) can be
designed and tested against something concrete, not local test-host scaffolding.
Why not now: no real per-person identity flow is available yet (2026-09-18). This is the same
blocker as "Per-person Confluence permissions for embedded users" above — v1 uses integration-level
scoping only (decision `embedded-scoping`), and the note carries no per-person Confluence identity.
Where it would go: Phase 4; panels sc-user, em-token, r3-acl. See the per-person-permissions idea above.
Added: 2026-09-18
Blocked on: a platform providing a real per-person identity in the note.

## Write the four missing ADRs (cm-docs)
What: write the decisions-of-record ADRs the design page implies exist but do not, covering the
fingerprint, scope_state, label-gated ingestion, and the edge token.
Why not now: deferred doc-debt (owner, 2026-09-18). The four topics are real, implemented behavior;
the gap is only that no ADR documents them. Until written, the design page must not imply they
exist and the coverage-map keeps `cm-docs` red under "needs live" (`live-0.5.3-cm-docs`).
Where it would go: `docs/adr/` — four new numbered ADRs; panel cm-docs.
Added: 2026-09-18
Note: I can draft these on request; each is a short ADR describing already-shipped behavior.

## Route local/dev/test make targets away from live Supabase (deferred safety)
What: the root `.env` sets `DATABASE_URL` to a live Supabase pooler, not the local `:5434` Postgres.
`make test-db` is safe (it pins the local URL for its own two commands), but `make check`, `make test`
and `make migrate` still resolve the old way. Two prior safety incidents came from a run connecting to
live Supabase. The fix is one call: (a) `.env` stops setting `DATABASE_URL` for local dev, or (b) every
db-touching make target pins the local URL the way `test-db` already does.
Why not now: deferred at the owner's request (2026-09-18). **CAUTION while deferred:** do not run bare
`make check` / `make test` / `make migrate` — they may hit live Supabase. Use `make test-db` (pinned)
or set `DATABASE_URL` to the local instance explicitly for any db-touching command.
Where it would go: the harness/make targets, near substep 0.5.4 (the CI gate).
Added: 2026-09-18 (moved here from the 0.5 owner-actions section)

## Configure a git remote so CI runs for real (deferred)
What: `git remote -v` is empty, so no pull request has ever exercised `.github/workflows/ci.yml`. The
four underlying commands were verified locally and the gate mechanism was proven historically (PR #1
red→green in ci-gate-proof.md), but the real CI path on this repo is unproven end-to-end. Configure a
remote (the GitHub repo) and a branch push + PR proves CI live.
Why not now: deferred at the owner's request (2026-09-18); no remote exists yet. Not a failing test —
the local suite is green and the gate logic is proven; only the live-on-remote proof is outstanding.
Where it would go: substep 0.5.1 / 0.5.4 (the CI gate), once a remote exists.
Added: 2026-09-18 (moved here from the 0.5 owner-actions section)

## Read-only staging DB URL for the live isolation run (pre-production)
What: a read-only staging connection string (`DATABASE_READER_URL` for staging) so the live isolation
script (`scripts/setup_supabase.py verify-isolation`, substep 0.5.3 / the 7.1.1 live checks) can prove,
against the real managed Postgres, that the reader role cannot write and RLS hides forbidden rows.
Why not now: the isolation *logic* is already proven at the local DB level by the `-m db` tests (both
roles, all policies, RLS on). The live run is an extra proof that only becomes necessary at 7.1.1, just
before production, when a misconfigured reader role would expose real tenant data — and no production
exists yet. The only Supabase URL in `.env` today is the writer/pooler tied to two prior stray-write
incidents, so the run must NOT use it; it needs a genuinely read-only string.
What you should do: when a staging reader credential exists, hand me `DATABASE_READER_URL` and confirm
the host is staging (not production); I'll run the script and save the output to
`final_docs/0.5-regression-tests/live-isolation-<date>.txt`.
Where it would go: substep 0.5.3 (live isolation) and 7.1.1 (environments); panels r3-reader, s-reader.
Added: 2026-09-18
