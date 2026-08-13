# Future ideas — not scheduled

Backlog of product ideas raised in conversation, captured here so they aren't lost. **None of
these are scoped, designed, or scheduled** — they are not part of `docs/rag/PLAN.md` and carry no
commitment. Before any of these becomes real work: run it through `docs/rag/PLAN.md`'s own
process (design first, an ADR if it's a durable architecture decision, then a phase with
acceptance criteria) rather than building ad hoc.

Each idea below is written as raised, plus a short note on how it would connect to what already
exists — not a spec.

---

## 1. Clarify before searching, on an underspecified question — **promoted to `docs/rag/PLAN.md` Phase 9 (2026-08-11)**

If the incoming question is too vague or irrelevant to search well, ask the user a clarifying
follow-up **before** running retrieval, instead of firing a low-quality query at the RAG database
and either hallucinating or refusing.

**No longer just an idea — it has an owning PLAN.md phase now** (Phase 9, the plan's deliberately
last phase, scoped not designed) that carries the concrete requirement: the ambiguity/vagueness
classifier, the clarification-response mechanism, differentiated refusal reasons, the Obi widget
fallback UX, a human-hand-off stub (logged event + CTA text only, no real integration this phase —
Salesforce noted as the eventual target when that's prioritized), and fallback-quality evaluation.
Read that section, not this one, for the current state — this entry is kept only as the original
raised-in-conversation framing, per this file's own convention of not deleting history.

**9.6 hand-off CTA address is a placeholder, not a real decision (2026-08-13).** Asked the user
what the "connect me to a human" CTA (ADR-0008 decision 6) should actually say/do, since inventing
a real support email or link isn't this agent's call to make. User's answer: use `test@gmail.com`
as the CTA's `mailto:` target for now, and record here that it is a stand-in — **the real contact
address/channel is still an open product decision**, separate from the already-noted eventual
Salesforce hand-off integration (decision 6's own note, above). Whoever revisits Salesforce hand-off
should also settle this address at the same time, since both are "where does a refused query
actually go" decisions.

**Relation to current architecture (as originally written).** Today, an underspecified query just falls through the
existing pipeline (rewrite → retrieve → rerank → refuse if the top score is weak) and comes out
the other end as a refusal ("not in the docs — routed to a human") — see `refusal_min_rerank_score`
and `AnswerService` in PLAN Phase 4.2. This idea adds a stage *before* retrieval: a cheap
classification/rewrite-model call that decides "is this answerable as asked, or do I need one more
detail from the user first" — closer to a conversational disambiguation turn than a retrieval
change. Would need: a way to detect "too vague" (heuristic or a routing-model call), and a new SSE
event type (or reuse of `refused`) so the UI can render "I need a bit more detail" distinctly from
a hard refusal.

## 2. Account/tier/integration awareness

Integrate with the surrounding system so the bot knows things about the asker: what pricing tier
they're on, what integrations they have enabled, what systems/products they use. Answers (and
retrieval scope) could then be tailored to what's actually relevant to *that* customer instead of
the whole corpus.

**Relation to current architecture.** There's no tenant/account model in this repo today —
`principal` on `POST /chat` is just a caller-self-reported string used for page-level ACL
(`PrincipalPermissionPolicy`, PLAN 4.3), not a customer/account record with tier or integration
data. This would need a new data source (likely an existing internal system-of-record, reached via
a new `platform/clients` integration) and a way to fold that context into retrieval scope
(`source_id`/`tags` filtering, see idea 4) and/or into the generation prompt.

## 3. Screenshot-grounded guidance — **promoted to `docs/rag/PLAN.md` Phase 7 (2026-08-11)**

Take a screenshot of the user's current page/screen and tell them exactly what to do next based on
what's actually visible there, instead of a generic text answer. Also covers the same gap for a
regular file/clipboard image attachment, not just the screenshot button — both go through the same
vision-analysis gap.

**No longer just an idea — it has an owning PLAN.md phase now** (Phase 7, scoped not designed) that
carries the concrete requirement, the known seams (contract gap, backend gap, the security review
this needs per `securing-http-and-llm-endpoints`, and the frontend follow-on), and its sequencing.
Read that section, not this one, for the current state — this entry is kept only as the original
raised-in-conversation framing, per this file's own convention of not deleting history.

**Relation to current architecture (as originally written).** This is a new modality (vision
input) the current pipeline doesn't have at all — `AnswerService` is text-in/text-out. Would need:
a way for the client to capture and send a screenshot (privacy/consent implications — this is
genuinely sensitive input, review under `securing-http-and-llm-endpoints` before building), a
vision-capable model call, and probably a way to ground the screenshot against known UI states/docs
rather than freeform description.

## 4. Segment retrieval by connector instance within one deployment

**Corrected 2026-08-10** — this idea previously conflated two different concepts. "Muse vs. Toast"
is **not** a corpus-tagging problem: Muse is a future *second full deployment* (its own database/
knowledge base, same codebase) reusing this app, not a content category inside Toast's own corpus.
That split is a deployment decision, now governed by `docs/adr/0006-Defer-Multi-Product-Extraction.md`
— deliberately deferred until Muse is a real, scheduled second deployment, and not solved by
ADR-0004's tagging model at all.

The part of the original idea that *is* a real tagging problem, kept here: **within one deployment**
(e.g. Toast), a single customer can have multiple instances of the same connector — e.g. two separate
QuickBooks accounts — and retrieval should be scoped to the relevant connector instance, not the
whole corpus for that integration type, as opposed to today's behavior which doesn't distinguish
connector instances at all.

**Relation to current architecture.** `page_source`/`chunk` already carry `source_type`, `source_id`,
and a free-form `tags` array (ADR-0004, PLAN 3.5.3), and `source_scope` (PLAN 3.5.6) already resolves
which Confluence roots/spaces feed which tags. Extending tags (or `source_id` itself) to encode a
connector-instance identity (e.g. `quickbooks:acct-1234` vs. `quickbooks:acct-5678`) and then
filtering `HybridRetriever` by that identity in addition to the existing `source_id` filter is
plausibly a small extension of the existing seam rather than new architecture — but confirm that
against the real tag taxonomy and how connector instances are actually identified upstream before
assuming it's just a config change. Not scoped, designed, or scheduled — same as every other idea in
this file.

## 5. Frontend/backend repository separation — **de-scheduled from `docs/rag/PLAN.md` Phase 4.8 (2026-08-12)**

**Was briefly a real, scoped phase, then un-scheduled.** This was raised in conversation on
2026-08-10 and immediately turned into `docs/rag/PLAN.md` Phase 4.8 (see
`docs/adr/0007-Frontend-Backend-Repository-Separation.md`), skipping this backlog entirely. It sat
blocked on three unanswered decisions through Phase 7's whole lifecycle and never started. On
2026-08-12 the user confirmed this is a **future** want, not a near-term one — nothing is live yet
(no second product/deployment, no registry chosen, no repo-naming work done) — so it moved back
here as an unscheduled idea, per `docs/adr/0010-Redefer-Repository-Separation.md`. Read that ADR
(and 0006/0007 before it) for the full decision history; this entry keeps the design work itself so
none of it is lost.

**The idea.** `apps/web` (frontend) and `apps/automation` (backend) become independently deployable
and independently versioned — able to live in separate git repositories — with
`packages/contracts` and `packages/design-tokens` as *published, versioned* packages instead of
pnpm workspace `workspace:*` links (which only resolve inside one monorepo checkout). Motivation is
separation of concerns and independent deployability, not multi-product reuse per se (though it
would also serve that later, see idea #4's note on Muse).

**Relation to current architecture.** Today everything lives in one pnpm workspace; `apps/web`
depends on both packages via `workspace:*`. That link only works inside this one checkout — before
either app could leave the monorepo, both packages need a real publish target and semver
discipline (a breaking contract change = a major version bump, consumed explicitly by each app, not
silently picked up). `apps/automation` already hand-authors its own Pydantic models against the
same wire shapes (no codegen) — that convention would stay true; only the distribution mechanism
would change.

**The work, as scoped when it was Phase 4.8** (kept in full — this is real design work, not a
one-line idea):

1. **Publish `packages/contracts` and `packages/design-tokens`** to a real registry (private npm
   registry vs. GitHub Packages — **open decision**) with semantic versioning discipline.
2. **Extract `apps/web` into its own repository** — name is an **open decision** (e.g.
   `omniboost-rag-web`). History-preserving extraction (`git subtree split` / `git filter-repo`, not
   a fresh copy — keep blame/history). Switch `@omniboost/contracts`/`@omniboost/design-tokens` from
   `workspace:*` to real published version ranges. New standalone CI (lint/typecheck/test/build) —
   today it piggybacks on the monorepo's root scripts, which won't exist once standalone.
3. **Extract `apps/automation` into its own repository** — name is an **open decision** (e.g.
   `omniboost-rag-automation`). Same history-preserving extraction; its Makefile/`uv` toolchain and
   `alembic/` migrations move unchanged (already self-contained, per ADR-0003). New standalone CI
   (`make check`, `make boundaries`, ruff, pyright).
4. **Decide the origin monorepo's fate** — **open decision**. Options: (a) archive it once both
   extractions are verified working; (b) keep it as a thin umbrella (`infra/` for combined local
   Postgres, `docs/adr/`, `docs/rag/`, root `CLAUDE.md`), referencing the two new repos as git
   submodules or documentation links, for "run both together locally" without cloning three repos.
   (b) was the lean for local-dev ergonomics, unless full self-containment per repo (more
   duplication, simpler mental model) is preferred instead.
5. **CI/CD and secrets per repo.** Each new repo gets its own pipeline and its own secrets scope —
   `CHAT_API_KEY`/`CONFLUENCE_*`/`ANTHROPIC_API_KEY` etc. belong to the backend repo only; the
   frontend repo needs only `CHAT_API_KEY` + `AUTOMATION_API_BASE_URL` for its proxy. No secret
   should live in a repo that doesn't need it.
6. **Update governing docs.** Amend `docs/adr/0001-Archetype-And-Stack.md` (currently describes one
   monorepo archetype) to reflect the multi-repo topology; write a new ADR recording the actual
   split decision at that time; update root `CLAUDE.md`'s "Layout" section once the split is real.
7. **Exit gate.** Both repos build/lint/typecheck/test/deploy independently with zero references to
   the other by path (only by published package version); a deliberate breaking change to
   `packages/contracts` proves the version-bump workflow catches it in CI on the *other* repo, not
   silently at runtime; local combined dev still works per whatever the monorepo-fate decision was.

**Open decisions, unchanged from when this was Phase 4.8** — nothing here executes without answers
to: which registry (item 1), the two new repo names (items 2/3), and the origin monorepo's fate
(item 4). Not scoped, designed, or scheduled — same as every other idea in this file. **Trigger to
revisit** (per ADR-0010): a real second product/deployment with a committed launch date, or the user
deciding the three open decisions with enough conviction to actually execute.

---

## Later: visualize the target system

Once any of the above gets real shape, draw the target pipeline (probably a Mermaid diagram in a
markdown file here or in `docs/rag/DESIGN.md`) showing how clarification, account context,
screenshots, and corpus segmentation compose with the existing
`rewrite → retrieve → rerank → ground → refuse → CRAG` pipeline. Not needed until one of these
ideas is actually being designed.

---

**No longer "already scheduled"** — see idea #5 above for the current state of the repo-separation
idea (moved back here from `docs/rag/PLAN.md` Phase 4.8 on 2026-08-12, per
`docs/adr/0010-Redefer-Repository-Separation.md`).