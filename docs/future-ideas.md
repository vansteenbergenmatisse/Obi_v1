# Future ideas — deferred by design, not lost

Things we know we will want and choose not to do now, so they are not lost. One section per
idea: what it is, why it is deferred, where in the plan it would land, and the date added. This
is the substep-1.3.1 ideas file named by CLAUDE.md's "where the truth lives" — a distinct,
narrowly-scoped list of deferred *plan-adjacent* features, not the broader ad hoc backlog kept at
`docs/future-ideas/IDEAS.md`.

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
