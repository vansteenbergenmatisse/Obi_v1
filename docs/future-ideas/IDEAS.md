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

## 2. Account/tier/integration awareness — **retrieval-side gap partially promoted 2026-08-21 → `docs/rag/PLAN.md` Phase 10**

**The specific gap this entry identified by direct code read — `tags` written at ingestion, never
read at query time — is what `docs/rag/PLAN.md` Phase 10 (`docs/adr/0011-Knowledge-Scope-Tagging-
And-Retrieval-Filtering.md`) closes.** Phase 10 covers only the *declared* case: which platform a
deployment/embed is scoped to, resolved once per session, filtered with a **hard** SQL predicate.
Everything else raised in this entry stays here, unbuilt:
- The **hard-vs-soft scoping nuance** below (a customer's own integration context needs a *soft*
  bias so switching/comparison questions stay answerable) — ADR-0011 Decision 5 explicitly chose a
  hard filter for Phase 10's declared-scope case and left soft/blended scoping for an *inferred*
  customer-integration case as future work, unchanged from this entry's original framing.
- The **"Baze" detection mechanism** thread (below) — entirely unaddressed; Phase 10's scope is
  always supplied by the deployment/embed, never inferred from a customer record.
- Any actual account/tier data model — still doesn't exist.

Read Phase 10 (and ADR-0011) for the now-real "which tags exist and how they're filtered" mechanics;
read on below for the parts of this idea that remain genuinely future.

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

**Elaborated 2026-08-12 — detection mechanism + a hard-vs-soft scoping nuance.** Raised again in
conversation using "Muse" and "Toast" as example names for two of the ~16 planned third-party
integration types (POS/PMS-style systems a client's business runs, same category as QuickBooks for
accounting) — **a client-integration-type meaning, not** the same two words' existing meaning in
`docs/adr/0006-Defer-Multi-Product-Extraction.md` / idea #4 (where "Toast" = this product's own
current deployment and "Muse" = a hypothetical future *second deployment* of this codebase). That
collision was flagged in conversation and deliberately left unresolved at the user's direction —
whoever picks this idea up should pick example names that don't collide with ADR-0006's usage, or
explicitly confirm the two are unrelated before scoping real work.

Two concrete pieces surfaced this pass:

1. **Detection mechanism.** The user named a system called **"Baze"** (spelling/exact identity not
   verified — nothing under that name exists in this repo today, confirmed by a repo-wide grep) as
   something Omniboost could integrate with to learn, per client, which integration is their main
   one (e.g. Muse) and which secondary ones they run (e.g. QuickBooks for accounting) — turning
   "account/tier/integration awareness" from a manual/self-reported signal into a real, queryable
   fact. Before any design work: confirm what Baze actually is (a CRM? an internal onboarding
   system? a third-party product?), what API/export it offers, and whether it's already something
   `platform/clients` could reach.

2. **Hard-vs-soft scoping — the actual retrieval design gap.** The instinct is "filter to only the
   client's own integration's content," but the user was explicit that switching/comparison
   questions ("we're on Muse, does this also work on Toast?") must still be answerable — so this
   cannot reuse ADR-0004's RLS mechanism as-is. RLS is **deliberately hard default-deny** (a security
   boundary: an unset scope returns zero rows, by design) — the right tool for isolating principals/
   sources, the wrong tool for "prefer this content but don't exclude the rest." What's actually
   needed is closer to a **soft bias**: default the retrieval/rerank scope to the client's detected
   integration's tags, but fall through to (or blend in) the wider corpus when the query is itself
   about a *different* integration or about switching/comparison — which likely also needs the query
   itself classified ("is this a comparison/switching question") before deciding how hard to scope,
   not a static per-client filter alone.

**Checked, not assumed, before writing this**: `source_scope.tags` → `page_source.tags` →
`chunk.tags` already exist end-to-end (`ADR-0004`, PLAN 3.5.3/3.5.6) and are already described in
their own code comments as "for bot scoping" — but a direct read of
`app/features/retrieval/infrastructure/search_repo.py`'s `_base_filters()` confirms retrieval's SQL
**never references `tags` at all today** — only `source_id` (RLS + explicit `WHERE`) and `space_id`
are filtered. The tagging plumbing already exists and is already populated at ingest time; nothing
today reads it back out at query time. Wiring a *soft* tag-based scope into `HybridRetriever` (a
boost/bias, not a hard `WHERE tags && ARRAY[...]`) is the concrete extension this idea would need —
plausibly building on idea #4's existing "connector instance" tagging extension rather than
inventing a second tagging mechanism alongside it.

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

**Not the same axis as Phase 10 (2026-08-21).** `docs/rag/PLAN.md` Phase 10 / `docs/adr/0011-*.md`
builds knowledge-scope tagging (which third-party *platform*'s docs a chunk belongs to — Mews vs.
Opera Cloud). This idea is a different axis entirely (which *instance* of one connector — e.g. two
QuickBooks accounts) and remains unbuilt; ADR-0011 Decision 8 lists it as an explicit non-goal of
Phase 10, not a duplicate of it.

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

## 7. Folder-level `source_scope` roots (space, page, **or folder**) — raised 2026-08-21

**Confirmed missing, not assumed** — the user gave a real Confluence folder link
(`.../wiki/spaces/omnidoc/folder/709066762/Ancon+POS+to+PMS`) to sync. `source_scope.root_type`
and `scope_resolver.py`'s resolution logic only know two root types today:
`ROOT_TYPE_SPACE`/`ROOT_TYPE_PAGE` (`seed_source_scope.py --root-type` only accepts
`space`/`page`). A **folder** is a distinct Confluence content type, not a page.

**Why it doesn't just work today, walked through in code, not guessed:**
`resolve_scope_roots()` (`domain/scope_resolver.py`) walks `parent_id` chains over
`live_pages`, which comes from `list_space_pages()` — the Confluence v2 `/pages` endpoint,
which returns only `type=page` content. A folder's id **never appears** in that listing. So a
`page`-type root pointed at a folder's id hits `stack = [root_page_id] if root_page_id in
live_ids else []` — the folder id is never in `live_ids`, the stack starts empty, and
`resolved[root.id]` comes back as an **empty set**. Not an error, not a warning — a silent
zero-coverage no-op, even though the folder may contain many real pages with `parent_id`
pointing at it. This is the same class of "silently does nothing" failure mode this session's
restrictions-endpoint fix (PLAN 4.6.2, 2026-08-21) just closed elsewhere in this codebase —
worth being deliberate about here rather than repeating it.

**What real support would need — scoped, not designed:**
1. `seed_source_scope.py --root-type` gains `folder` alongside `space`/`page`.
2. The gateway needs a way to enumerate a folder's contents. **Unverified against a live
   instance — confirm before building**, per this same session's lesson that Confluence's v2 API
   surface doesn't always work the way its shape suggests (the restrictions endpoint looked
   right and returned 418). Plausible candidates to check live: `GET /wiki/api/v2/folders/{id}`
   for folder metadata, and either a folder-children endpoint or `GET /wiki/api/v2/pages` filtered
   by `parent-id={folderId}` — v2's page-listing already supports parent-based queries for the
   page case, so the same mechanism may extend directly to a folder parent, but that must be
   checked live, not assumed from the docs.
3. `resolve_scope_roots()`'s tree-walk would need to mix folder and page ids in one parent-child
   chain (a folder can contain sub-folders *and* pages; a root folder's descendant pages may sit
   several folder-levels deep, not just one hop below the root) — the existing `children_of`
   map-and-stack-walk shape likely generalizes once folder ids are includable, but the "leaf"
   check (what actually gets ingested vs. what's just a container) needs to explicitly exclude
   folder nodes themselves from becoming `page_source` rows.

Not scoped, designed, or scheduled — same as every other idea in this file. **Trigger to
revisit:** the next time someone wants to scope a sync to a folder instead of a whole space or a
single page subtree (this session's own blocked attempt is the first concrete instance).

## 8. Multi-provider platform architecture: reusable core, provider-scoped knowledge — **knowledge/RAG-corpus piece promoted 2026-08-21 → `docs/rag/PLAN.md` Phase 10**

**The third concern below ("Knowledge / RAG separation") now has an owning phase and ADR** —
`docs/rag/PLAN.md` Phase 10, decided by `docs/adr/0011-Knowledge-Scope-Tagging-And-Retrieval-
Filtering.md`. Read that ADR and phase for the current state of: recognized-scope configuration,
label-driven per-page tagging, the retrieval-time hard filter (behind `enable_knowledge_scope_
filtering`, ships dark), request-level `knowledge_scope` threading, and the always-present curated-
knowledge layer. **Confirmed 2026-08-21: the recognized scope set is `general`, `mews`, `opera-cloud`,
`toast`** — the real named platforms, not the illustrative "avoid toast" placeholders this idea
originally used (see the superseded terminology-collision guidance below, kept for the reasoning
trail). This entry is kept in full below as the original raised-in-conversation framing and because
several threads it named are **explicitly still deferred**, not resolved by Phase 10:

- **Multiple recognized provider labels on one page.** Phase 10 (ADR-0011 Decision 3) treats this as
  an invalid/conflict state — the page is quarantined to zero label-derived tags and logged, not
  ingested into more than one provider scope. A page intentionally belonging to more than one
  provider scope at once is still future work, unscoped.
- **Explicit cross-provider / cross-scope retrieval** ("search everything," or blending `general +
  mews + opera-cloud` on purpose for comparison/admin/research use cases) — explicitly out of scope
  for Phase 10 (ADR-0011 Decision 5/8). The default (and, for Phase 10, the *only* mode) stays
  `general + active scope`; widening it is a deliberate, separate future feature, never a silent
  default.
- Frontend/backend reusability (concerns 1–2 below) — unaffected by Phase 10, which only touches the
  knowledge/RAG concern; idea #5 remains the mechanism for the frontend/backend piece, still
  de-scheduled.
- Soft-vs-hard scoping, the "Baze" detection mechanism, and connector-instance tagging (idea #4) —
  all still unbuilt; see the updated notes on ideas #2 and #4 above.

**Read ideas #2, #4, #5, and #7 first — this idea ties their threads together rather than
replacing them.** It does not introduce new mechanisms so much as name the end-state that #2's
integration-awareness scoping, #4's connector-instance tagging, #5's repo-separation motivation, and
#7's `source_scope` root gap are all partial pieces of. Nothing below is scoped, designed, or
scheduled — same as every other idea in this file.

**Terminology collision — read before using the word "Toast" anywhere near this idea. RESOLVED
2026-08-21 for Phase 10, kept here for the reasoning trail, not as live guidance to "avoid" it.** This
codebase's own repo/deployment is itself code-named **Toast** (`RAG-TOAST-omniboost`,
`docs/adr/0006-Defer-Multi-Product-Extraction.md`'s "Muse vs. Toast" = two hypothetical *deployments
of this same product*). This idea, as raised, uses "Toast" as an example of a **third-party
hospitality POS platform** (alongside Mews and Opera Cloud — real PMS/POS systems this product's
customers run) that a *customer* might be integrated with — a completely different meaning, same
word. Idea #2 already flagged the identical collision for "Muse"/"Toast" used as example third-party
integration names and left it explicitly unresolved at the user's direction. **The user has since
confirmed (ADR-0011, `docs/rag/PLAN.md` Phase 10) that `toast` — meaning Toast POS — is a real
recognized knowledge scope, collision disclosed and accepted, not avoided.** The advice below (originally:
pick example names that don't collide, avoid "Toast"/"Muse") applied to *illustrative* naming in this
idea's own discussion, not to a considered real decision once one exists — Phase 10 is that considered
decision for the knowledge-scope axis. "Muse" remains unused and avoidable (no real product is named
that); "Toast" is now a real, intentional recognized scope value. Whoever scopes remaining real work
here (idea #2's soft-scoping, idea #4's connector-instance tagging) must still pick example names that
don't collide with this repo's own ADR-0006 vocabulary where the naming is still illustrative
(Mews/Opera Cloud remain safe placeholders; avoid "Muse" as a stand-in for an external provider), or
state outright that the two meanings are unrelated before writing anything that could be misread as "this
product embeds inside itself."

**Problem / why.** As currently built, this is one product (chat widget + retrieval pipeline) with one
knowledge corpus. The direction under discussion is deploying the same product into or alongside
multiple third-party hospitality platforms (Mews, Opera Cloud, and others are the named examples —
not an exhaustive or committed list) plus a standalone deployment, without forking the whole
application per platform and without leaking one platform's knowledge into another platform's
answers.

**High-level shape.** Three concerns, each already structurally distinct in this repo today, need to
stay that way and get more deliberate about it as more providers appear:

1. **Frontend** (`apps/web`) — should stay one reusable core product, not one fork per provider.
2. **Backend** (`apps/automation`) — should stay one shared core service, not one deployment per
   provider.
3. **Knowledge / RAG corpus** — the one thing that *should* become provider-partitioned, because
   unlike the app code, provider-specific documentation is genuinely provider-specific content.

**Frontend reusability.** `apps/web/src/features/chat` is already the one place the chat UI, widget,
composer, and session logic live, behind its own `index.ts` public root (per this project's
feature-boundary convention) and `apps/web/src/platform/automation-api` as the one client to the
backend. There is no per-provider frontend fork today — that is already the right shape; this idea
just says: keep it that way as providers multiply, rather than letting a "Mews build" and an "Opera
build" diverge into separate codebases. Idea #5 (frontend/backend repository separation, currently
de-scheduled per `docs/adr/0010-Redefer-Repository-Separation.md`) is the mechanism that would let
`apps/web` be independently deployed/embedded per provider context while staying one codebase — this
idea is a second, concrete reason #5's trigger ("a real second product/deployment with a committed
launch date") might eventually fire, alongside Muse.

**Shared backend.** Per ADR-0006 decision 2, `apps/automation/app/platform/config/settings.py` is
already fully env-driven — no product-specific literal is baked into logic — so multiple deployments
of the same backend already cost an environment/ops action, not a code fork. That property should
hold for provider-scoped deployments too: a "Mews-facing" backend instance and an "Opera-facing" one
should be the same image, different config/scope, not different code. `apps/automation/app/platform/
clients` (`confluence_client.py` is the one existing example) is the established pattern for adding a
new external integration client without duplicating the service around it — the repeatable shape a
future provider's data connector would follow (see idea #4/#7 for what that connector needs to feed
into ingestion).

**Knowledge / RAG separation — the part that should genuinely partition.** "Knowledge" here means
what `apps/automation/app/features/retrieval` retrieves from — the `page_source`/`chunk` corpus fed
by `apps/automation/app/features/confluence_sync` ingestion — not prompts, agent instructions, or
skills. `docs/adr/0004-Multi-Source-Provider-Tagging-And-RLS.md` already built most of the mechanism
this idea needs: `source_type`/`source_id`/`tags` columns on `page_source` and `chunk`, `source_type`
deliberately a CHECK constraint (not a PG enum) specifically so a new connector type doesn't need an
`ALTER TYPE`, and RLS keyed on `source_id` as the hard security boundary. `source_scope`
(`apps/automation/app/platform/db/models.py`, resolved by `apps/automation/app/features/
confluence_sync/domain/scope_resolver.py`) already resolves which Confluence roots feed which tags at
ingest time. None of this was built for multi-provider scoping specifically (ADR-0004 was written for
generic multi-source isolation, e.g. Confluence vs. a future Zendesk), but it is the same shape:
"shared/general" would be one `source_id`/tag value, "Mews-specific" and "Opera-specific" would be
others, coexisting in one database, one corpus, isolated by the same RLS the codebase already relies
on for hard boundaries.

**Shared vs. provider-specific knowledge.** Two tag/source categories, both expressible in the
existing model without a schema change:
- Shared/general — valid regardless of active provider, always in scope.
- Provider-specific — Mews-only, Opera-only, future-provider-only; excluded from retrieval by default
  when a different provider is active.

**Default retrieval behavior — the concrete gap, already identified once (idea #2).** A direct read of
`apps/automation/app/features/retrieval/infrastructure/search_repo.py`'s `_base_filters()` confirms
retrieval's SQL filters by `space_id` and `source_id` (RLS + explicit `WHERE`) today, but **never
reads `tags` at query time** — the tagging columns are populated at ingest but nothing reads them back
out during retrieval. That is the literal mechanism this idea needs built: `HybridRetriever`
(`apps/automation/app/features/retrieval/application/retriever.py`) would need to fold "shared tags +
active-provider tag" into its filter (or a soft rerank bias, per idea #2's hard-vs-soft nuance — a
strict provider tag filter is fine here because there is no cross-provider comparison expectation the
way idea #2's client-integration case had, but that should be confirmed, not assumed, when this is
actually scoped) rather than only `source_id`/`space_id` as today.

**Provider context: determined once, not per message.** Mirrors idea #2's already-identified need
for account/integration-awareness, but the trigger here is *which platform this deployment/session is
embedded in*, not *which integrations a given customer runs*. Whatever resolves that (a config value
for a provider-specific deployment, or a runtime lookup for an embedded/multi-tenant case — genuinely
undecided) should be resolved once at session/deployment start and carried forward, the same way
`principal` is threaded through `apps/web/src/features/chat/server/route-handlers.ts` and
`apps/automation/app/features/rag_agent/server/router.py`'s request handling today — not
rediscovered on every `/chat` call. There is no tenant/account/session-context model in this repo
today beyond that caller-self-reported `principal` string (idea #2 already noted this); provider
context would need something in the same spirit, scoped appropriately.

**Explicit cross-provider retrieval.** Default stays scoped (general + active provider); an explicit
user action ("search everything") could widen the scope, mirroring idea #2's comparison/switching-
question case ("we're on Mews, does this also work on Opera?") — same underlying tension between hard
default-deny scoping and an intentional wider search, not necessarily the same mechanism.

**Ingestion vs. runtime retrieval are different concerns.** `confluence_sync` already ingests and
tags at a single seam (ADR-0004 item 8, `ingestion/application/versioning.py`) — that seam already
knows how to write `source_id`/`tags` per document. Ingestion knowing about every provider's content
does not mean every request should search every provider's content; that split (ingest-time tagging
vs. query-time scoping) is exactly what today's gap (tags written, never read back) currently
collapses by omission, and what idea #2/#4/#7 all separately point at from different angles.

**Scalability — a repeatable pattern per new provider.** Because `source_type` is a CHECK constraint
and the ingestion seam is already parameterized (ADR-0004 item 8: "a constant today, a parameter when
a second source lands"), adding a provider in principle costs: a new `platform/clients` integration
(mirroring `confluence_client.py`), a provider tag/`source_id` value, and a `source_scope` root — not
a new deployment fork. That repeatability is unverified in practice since only one provider
(Confluence) exists today; treat it as a hypothesis this idea would need to test on a real second
provider, not a guarantee.

**Benefits / goals.** Named explicitly, not just implied by the mechanism above:
- **Separation of concerns** — frontend, backend, and knowledge get clearer, independently-reasoned-
  about responsibilities instead of one product that silently conflates "what platform is this" with
  "what code runs."
- **Reusability** — deploy into/alongside multiple providers without copying the application.
- **One core backend** — a backend improvement (retrieval quality, a bug fix, a new capability)
  propagates to every provider deployment instead of being reimplemented per fork.
- **Reusable frontend** — a UI/UX improvement doesn't need to be rebuilt separately for Mews, Opera,
  and whatever comes next.
- **Knowledge isolation** — a provider retrieves shared/general knowledge plus its own, never another
  provider's exclusive content, without depending on the LLM remembering to ignore it.
- **Better RAG quality** — fewer irrelevant candidates in the retrieval set for a given provider
  context, which idea #2 already predicted would improve precision.
- **Lower LLM confusion** — the model isn't shown competing/contradictory provider-specific guidance
  it then has to silently arbitrate.
- **Scalability** — retrieval cost/precision doesn't degrade as more providers are added, because the
  candidate set stays scoped rather than growing with every new provider's corpus.
- **Maintainability** — a repeatable "add a provider" pattern instead of each provider becoming its
  own bespoke fork of the product.
- **Easier for developers and coding agents** — clearer ownership boundaries make it safer for a human
  or Claude Code to change one concern without accidentally touching another.

**Related current architecture.**
- Frontend: `apps/web/src/features/chat/**` (chat UI, session, `route-handlers.ts` principal
  handling), `apps/web/src/platform/automation-api/**` (the one backend client).
- Backend/core: `apps/automation/app/platform/config/settings.py` (env-driven config, ADR-0006
  decision 2), `apps/automation/app/platform/clients/confluence_client.py` (the integration-client
  pattern), `apps/automation/app/features/rag_agent/server/router.py` (principal handling).
- Knowledge/RAG: `apps/automation/app/features/retrieval/infrastructure/search_repo.py`
  (`_base_filters()` — where scoping would need to read `tags`), `apps/automation/app/features/
  retrieval/application/retriever.py` (`HybridRetriever`), `apps/automation/app/platform/db/models.py`
  (`SourceScope`, `source_type`/`source_id`/`tags` on `page_source`/`chunk`), `apps/automation/app/
  features/confluence_sync/domain/scope_resolver.py` (root resolution), `apps/automation/app/
  features/confluence_sync/application/versioning.py` (the one ingestion tagging seam).
- Governing docs: `docs/adr/0004-Multi-Source-Provider-Tagging-And-RLS.md`,
  `docs/adr/0006-Defer-Multi-Product-Extraction.md`, `docs/adr/0010-Redefer-Repository-Separation.md`,
  and ideas #2, #4, #5, #7 in this file.

**Open questions / decisions for later.** Exact RAG tagging/namespace format for provider scope
(reuse `tags` as-is, or a dedicated column); whether retrieval scoping should be a hard filter or a
soft bias (idea #2's open question, inherited here); the provider-context detection mechanism (config
vs. runtime lookup — idea #2's unresolved "Baze" thread may be the same detection problem, may not
be); session/context persistence mechanism; cross-provider search UX and permissions; whether
knowledge ever needs physical (not just tag) separation; multi-provider-per-customer behavior
(explicitly out of scope per the framing this idea was raised with); exact repo/deployment topology
if idea #5 is ever revived alongside this.

**Explicit non-goals for now.** No separate backend per provider. No separate frontend fork per
provider. No new database or vector store. No schema change (ADR-0004's columns are believed
sufficient; confirm, don't assume, once real work starts). No solving multi-provider-per-customer
routing. No implementation of any kind — this entry is documentation only.

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