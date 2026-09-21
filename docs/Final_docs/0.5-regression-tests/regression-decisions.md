# Regression decisions — the settled calls the 0.5 suite builds to

Date added: 2026-09-18
Decisions dated: 2026-09-14 (the owner's calls)
Substep context: 0.5 regression phase

The 0.5 regression suite protects behaviour the owner has already decided. This file is
the one place those settled calls are written down with their value, so a regression
panel (and the agent writing its test) reads the default here instead of stopping to ask,
and nobody re-argues a settled point. Every regression test or panel that names one of
these decisions points at the row below.

Canonical source: **`docs/plan/decisions.md`** is the source of truth for every settled
call (action plan substep 0.6.1 mandates the full list live there). This file is the
regression-scoped view and mirror; when the two differ, `docs/plan/decisions.md` wins.
It also carries the four calls added 2026-09-18 (i2-fetch, i4-failed, widget test level,
r1-limits IP key) and the open `trusted-proxy-hops` line, which the mirror below folds in.

Changing a settled call needs a new ADR under `docs/adr/`.

## Settled calls (owner, 2026-09-14)

| id | decision | value | status | date | note |
|---|---|---|---|---|---|
| vd-model | embedding model | the model in use today, 3072 dimensions; same model for questions and for children | confirmed | 2026-09-14 | the model bake-off is deferred to `docs/future-ideas.md` (vd-model) |
| speed-vs-accuracy | accuracy before speed | a correct answer in 7–9 s per answer is acceptable; a wrong answer is not | confirmed | 2026-09-14 | |
| folder-move | when the folder move happens | early — Phase 1 | confirmed | 2026-09-14 | frontend/ backend/ knowledge-base/ split |
| embedded-scoping | scoping for embedded users | integration-level scoping; no per-person Confluence permissions in v1 | confirmed | 2026-09-14 | per-person permissions stay an open target on the design page (section 11) |
| note-ttl | how long the note lives | 60 minutes per platform | confirmed | 2026-09-14 | |
| note-empty | a note with no values | gives general pages only | confirmed | 2026-09-14 | |
| note-fetch-timing | when the note is fetched | at the button click | confirmed | 2026-09-14 | |
| platform-order | platform rollout order | Data Hub first; Mews and Toast follow; Opera Cloud stays inactive until confirmed | confirmed | 2026-09-14 | |
| translation | non-English questions | translated to English before search; the checked answer translated back before replay | confirmed | 2026-09-14 | citations, markers and the trace stay English (rule 9) |
| keyword-lang | the keyword index language | stays English | confirmed | 2026-09-14 | |
| cost-per-q | cost per question | 3–6 cents per question is accepted for now | confirmed | 2026-09-14 | |
| doc-gap-ownership | documentation-gap ownership | out of scope for now | confirmed | 2026-09-14 | |
| support-judge | the support judge | fails closed | confirmed | 2026-09-14 | Priority 2, the batched support check before send |
| hosting | where Obi is hosted | AWS, in the last phase | confirmed | 2026-09-14 | |
| dev-webhook | a public webhook during development | runs through a tunnel | confirmed | 2026-09-14 | |
| i2-fetch | when the page body is fetched | on a version change only (2.2.2 owns the target) | confirmed | 2026-09-18 | panel's "attachment list moved" text overstates the code |
| i4-failed | a gate-failed version | never garbage collected; queue-path rollback leaves no version row | confirmed | 2026-09-18 | 2.4.3 keeps the stage-4 regression tests green |
| widget-test-level | the 0.5 widget regression test level | jsdom component (unit) + `widget-mounts.spec.ts` smoke; Playwright per panel in Phase 4 | confirmed | 2026-09-18 | |
| r1-limits-ipkey | the untokened rate-limit IP key | `request.client.host`, no XFF, until 7.1.1 | confirmed | 2026-09-18 | 3.2.6 adds `TRUSTED_PROXY_HOPS` (default 0); 7.1.1 sets the real count |
| freshness-target | the freshness target in seconds | — | open | 2026-09-14 | needs the owner's number |
| latency-budget | the worst-case latency budget | — | open | 2026-09-14 | needs the owner's number |
| rerank-depth | the rerank depth | 75 today | open | 2026-09-14 | recalibrate on the gold set |
| trusted-proxy-hops | the trusted proxy hop count for the rate-limit IP key | `TRUSTED_PROXY_HOPS = 0` (= `request.client.host`) | open | 2026-09-18 | set in 7.1.1 once the browser→proxy→LB→API chain is known |
