# 0011 — Confluence-Label-Driven Knowledge-Scope Tagging and Retrieval Filtering

Status: Accepted
Date: 2026-08-21
Governs: apps/automation (confluence_sync, ingestion, retrieval, rag_agent, platform/db, platform/config,
alembic), apps/web (chat feature, contracts)

## Context

Promotes `docs/future-ideas/IDEAS.md` idea #8 ("Multi-provider platform architecture: reusable core,
provider-scoped knowledge") into real, scoped work, folding in the retrieval-side gap idea #2 already
identified by direct code read. The product intends to deploy the same chat widget against multiple
third-party hospitality platforms plus a general/standalone deployment, without forking the frontend
or backend per platform and without one platform's documentation leaking into another platform's
answers. **Confirmed 2026-08-21: the initial recognized knowledge-scope set is `general`, `mews`,
`opera-cloud`, `toast`** — the user's real, named list of platforms to support (not illustrative
placeholders); `Settings.knowledge_scopes` (Decision 1) remains config-driven so a fifth platform is a
config change, not a code change.

**Terminology collision, read first — and confirmed, not avoided.** This repo's own deployment is
itself code-named **Toast** (`RAG-TOAST-omniboost`; `docs/adr/0006-Defer-Multi-Product-Extraction.md`'s
"Muse vs. Toast" names two hypothetical *deployments of this same product*). This ADR's "provider" — a
third-party system a customer runs (Mews, Opera Cloud, and **Toast POS**, an unrelated real product
that happens to share this repo's codename) — is an unrelated meaning of the same word, already
flagged as an unresolved collision by idea #8. **This ADR calls the concept a "knowledge scope," never
a "provider,"** specifically to keep it out of ADR-0004's `source_type`/`source_id` vocabulary
(source = data connector: Confluence, future Zendesk) and out of ADR-0006's deployment vocabulary
(Toast = this deployment, Muse = a hypothetical second one). **The user has confirmed, with the
collision disclosed, that `toast` is a real recognized knowledge-scope value** (Toast POS is one of
the three platforms this product must scope knowledge for) — this is a deliberate, informed choice,
not a default inherited from convenience. Anywhere `toast` appears as a `tags`/`knowledge_scope` value
in code, logs, or a `.env` file, it means the third-party POS platform, never this repository's own
codename; this paragraph is the canonical disambiguation to link back to.

**What already exists (confirmed by direct code read, not assumed).** ADR-0004 added `source_type`,
`source_id`, and a free-form `tags ARRAY(Text)` column to `page_source` and `chunk`, described in its
own decision text as "free-form per-source tags for **bot scoping**." PLAN 3.5.6 added `source_scope`
(space/page-root rows, each carrying its own `tags`) and `confluence_sync/domain/scope_resolver.py`,
which unions active roots' `tags` onto every page they cover — but `source_scope.tags` are assigned
**manually by an operator running `scripts/seed_source_scope.py`**, not derived from Confluence's own
per-page label feature, and they currently encode *sync inclusion* (which pages get ingested at all),
not knowledge scope. Separately, `HttpConfluenceClient.get_labels()` already fetches a page's native
Confluence labels on **every** sync run (used today only to compute `labels_hash` for change
detection); `ChangeClass.labels_changed` is already computed but folded into a `metadata_only` update,
never a distinct code path. Most importantly: `apps/automation/app/features/retrieval/infrastructure/
search_repo.py::_base_filters()` filters only `is_active`, `kind`, `page_status`, `space_id`, and
`source_id` — **`tags` is written at every ingestion activation and read by nothing at query time.**
The tagging plumbing ADR-0004 built for "bot scoping" was never wired to retrieval. This ADR closes
that gap and adds the missing per-page, label-driven, automatic tag source.

**Production data already exists under the pre-existing mechanism.** As of this session, 9 live pages
are `source_scope`-tagged `base` (PLAN.md §0, 2026-08-21 sync) and serve real retrieval today with no
knowledge-scope tag of any kind. Any change here must not silently make those pages unretrievable.

## Decision

1. **A knowledge scope is a recognized Confluence page label, plus the always-recognized value
   `general`.** Recognized scopes are centrally configured, not hardcoded: a new
   `Settings.knowledge_scopes: str` (comma-separated) field, exposed as a derived
   `Settings.knowledge_scope_set -> frozenset[str]`, validated at settings construction to contain
   `"general"` (fail-fast, matches this repo's existing fail-closed conventions rather than silently
   defaulting it in). Unrecognized Confluence labels are ignored entirely — they never become tags,
   scopes, or filters. **The code-level default stays `"general"` alone** (a bare install with no
   `.env` override should not silently invent scopes); the confirmed real deployment value is
   `KNOWLEDGE_SCOPES=general,mews,opera-cloud,toast`, set via environment override at 10.7's rollout
   step, not baked into the `Settings` field default.

2. **Label-derived tags are a new, additive contribution to the existing `tags` column, unioned with
   `source_scope`'s existing tags — not a replacement.** A new pure function,
   `confluence_sync/domain/knowledge_scope.py::resolve_knowledge_scope_tags(labels, recognized) ->
   KnowledgeScopeResult`, intersects a page's live Confluence labels with `knowledge_scope_set`.
   `sync_service.handle_sync_page` unions this result's tags with the existing `source_scope`-derived
   tags before calling the **same, already-parameterized** `stage_and_activate`/`_apply_metadata_only`
   seam (`ingestion/application/versioning.py`) that already accepts and stamps a `tags` list end to
   end. No change to `versioning.py`'s core logic. This preserves the live `base` tag unchanged and
   lets an operator still hand-assign a knowledge-scope value via `source_scope` if they choose to.

3. **One recognized provider-specific label per page; `general` is not a conflict with a provider
   label.** `recognized ∩ labels` minus `{general}` must have at most one member. If a page carries
   more than one recognized provider label (e.g. both `mews` and `opera-cloud`), the label-derived
   contribution is **quarantined to empty** (not "first wins," not "both apply") — `sync_service`
   still unions in whatever `source_scope` tags exist, but contributes zero knowledge-scope tags from
   labels, logs a `knowledge_scope_conflict` structlog event (page id, title, matched labels), and
   the page stays invisible to every knowledge-scope-filtered query until an operator fixes the
   Confluence labels — the next sync re-evaluates automatically (self-heals, same pattern already
   used for `rollback_to`'s hash restoration). This is a deliberate **fail-closed** choice, consistent
   with this session's own restrictions-endpoint fix (v2 418 → v1, fail-open → fail-closed) and PLAN
   4.6.1's group-restriction fail-closed precedent — never "make it available everywhere by default."

4. **Retrieval filtering is a hard SQL filter, gated behind a new flag that ships dark.**
   `_base_filters()` gains an optional `knowledge_scopes: Sequence[str] | None` parameter, adding
   `AND tags && ARRAY[:knowledge_scopes]` (Postgres array-overlap) when provided, backed by a new
   partial GIN index `ix_chunk_tags_gin ON chunk USING gin(tags) WHERE is_active`, matching this
   schema's existing `WHERE is_active`-partial-index convention. The filter is **only ever applied**
   when a new `Settings.enable_knowledge_scope_filtering: bool = False` flag is on — the same
   ships-dark pattern already used for `enable_clarification_branch`. Default off means zero behavior
   change (including for the 9 live `base`-tagged pages) until an operator has confirmed the real
   corpus is properly labeled and deliberately flips the flag.

5. **Hard filter, not a soft bias — for this phase only.** Idea #2 already identified that a
   *customer's own* integration context needs a **soft** bias (switching/comparison questions like
   "we're on Mews, does this also work on Opera?" must stay answerable) because that scope is
   *inferred* about the asker. This ADR's scope is different: it is *declared* by the deployment/embed
   context, not inferred, and there is no stated requirement yet for a single session to compare two
   providers' documentation. A hard filter is simpler, matches ADR-0004's own RLS precedent (also a
   hard default-deny filter for a different, declared axis), and is cheaper to reason about and test.
   Soft/blended scoping, if a comparison use case becomes real, is future work (`docs/future-ideas/
   IDEAS.md`), not this phase — see Decision 8.

6. **Active knowledge scope is a request-level value, resolved once, not inferred.** A new field,
   `ChatRequestBody.knowledge_scope: str | None`, threads through `AnswerService.answer()` →
   `HybridRetriever.retrieve_with_context()` exactly the way `principal` already does. A new pure
   resolver, `retrieval/domain/knowledge_scope.py::resolve_allowed_scopes(requested, recognized,
   default) -> list[str]` (co-located with the existing `permission.py::classify_scope`, which already
   plays this "interpret an incoming request-shaped scope value" role for `principal`), decides the
   final allow-list: `requested` if recognized, else `default` (`Settings.default_knowledge_scope`, a
   new deployment-level fallback for single-scope deployments), else `general` alone — always
   including `general`. An unrecognized requested scope degrades to the default/general (logged,
   never a hard 400) rather than breaking the chat entirely over a stale or misconfigured embed.
   `packages/contracts`' `ChatRequest` and the widget's embed configuration gain the equivalent field,
   forwarded unmodified by `route-handlers.ts::toBackendChatBody()` the same way `principal` is
   today — this is genuinely new plumbing (no prior page/embed-context mechanism exists anywhere in
   this codebase, confirmed by direct read of `chat-session-provider.tsx`, `OBI-WIDGET-DESIGN.md`, and
   `router.py`), not a rename of something existing.

7. **A fourth, separate prompt layer for always-present curated knowledge, reusing the existing
   citation machinery rather than inventing a second one.** A new table, `curated_knowledge_entry`
   (`id`, `tags ARRAY(Text)` — empty/`general` = always included, or a specific scope — `title`,
   `body`, `is_active`, timestamps), seeded by a new one-off CLI mirroring
   `scripts/seed_source_scope.py` (no CRUD API yet, same ownership decision as `source_scope`). At
   answer time, active entries matching the resolved allowed scopes (capped by a new
   `Settings.curated_knowledge_max_entries: int = 5`) are rendered as synthetic leading hits and
   **prepended to the real retrieved hits before `build_evidence_block`/`enforce_citations` run** —
   they get citation markers `[1..k]` exactly like retrieved evidence, so the existing
   grounding/citation-enforcement guarantee (`ANSWER_SYSTEM_PROMPT`'s load-bearing rule: an uncited
   claim is discarded) covers curated knowledge too, with zero new citation logic. This mirrors
   ADR-0009 decision 4's precedent of composing a new knowledge source as an additive, labeled
   section rather than modifying the one grounded/cited generation call's contract.

8. **Explicit non-goals for this phase**, deferred to `docs/future-ideas/IDEAS.md`:
   multiple recognized provider labels on one page (Decision 3 quarantines this state instead);
   an explicit "search all scopes" / cross-scope comparison mode; soft/blended scoping for
   comparison questions (idea #2); automatic provider-context detection (idea #2's "Baze" thread);
   connector-instance-level tagging (idea #4, a different axis — which instance of one connector, not
   which provider); any change to `source_scope`'s existing sync-inclusion role or ADR-0004's
   source-connector isolation model.

## Reason

Retrieval already writes a `tags` column at every ingestion activation and has never read it back —
this ADR is closing a gap the codebase already declared its intent to close (ADR-0004's own docstring:
"for bot scoping"), not inventing new architecture. Deriving tags from Confluence's native label
feature (rather than only from operator-run `source_scope` seeding) is what makes scope assignment
dynamic and near-real-time, matching Confluence's role as the system of record. Unioning with, rather
than replacing, `source_scope`'s existing tags avoids breaking the one real production dataset that
exists today. A hard filter behind a dark-by-default flag makes rollout safe: nothing changes for any
existing deployment until an operator has verified the corpus is labeled and deliberately opts in.
Reusing the evidence-block/citation-enforcement machinery for curated knowledge avoids a second,
parallel "trust this content" mechanism that `enforce_citations` doesn't know about.

## Alternatives considered

- **Reuse `source_scope.tags` as the only tag source (no new label-derived mechanism).** Rejected:
  `source_scope` tags are operator-assigned per root (space/page-tree), not per-page, and require a
  manual seed-script run per page — the opposite of "Confluence remains the dynamic source of truth,"
  and does not react automatically to a label added/removed on one page inside an already-scoped root.
- **Replace `source_scope`-derived tags with label-derived tags on the same column.** Rejected: would
  silently break the 9 live `base`-tagged pages and redefine what `source_scope.tags` means without a
  migration path for existing rows.
- **Soft rerank-bias filter instead of a hard SQL filter.** Rejected for this phase: no stated
  cross-scope-comparison requirement exists yet (unlike idea #2's client-integration case), and a hard
  filter is simpler to build, test, and reason about; revisit if/when a comparison use case is real.
- **A separate, uncited "always-present knowledge" prompt block (like `SMALL_TALK_SYSTEM_PROMPT`).**
  Rejected: `ANSWER_SYSTEM_PROMPT`'s citation enforcement discards any claim without a valid `[n]`
  marker — content injected outside the evidence-block/citation numbering would be systematically
  stripped from real answers, defeating the point of "always present."
- **A dedicated `knowledge_scope` column instead of reusing `tags`.** Rejected: `tags` is already
  `ARRAY(Text)`, already plumbed end to end through ingestion, and ADR-0004 explicitly designed it as
  free-form for exactly this kind of bot-scoping use — a second column would duplicate the seam ADR-0004
  already built without a concrete reason `tags` itself can't serve.

## Consequences

- Enabling `enable_knowledge_scope_filtering=true` without first labeling (or `source_scope`-tagging)
  the live corpus with a recognized scope makes those pages invisible to every knowledge-scope-filtered
  query — this is Decision 1's explicit "no recognized tag → does not participate" rule working as
  designed, not a bug, but it is an operational step that must happen before the flag flips in any
  environment with real content (see the governed phase's migration section).
- `toast` is a confirmed, real knowledge-scope value (Toast POS), deliberately configured despite
  colliding with this repo's own codename — any log line, test fixture, or support conversation
  reading "toast" must be checked for which meaning applies; this ADR's Context section is the
  canonical disambiguation to point people at.
- `search_repo.py`'s query plan gains one more predicate and one more partial index to maintain;
  negligible at the current corpus size (85 chunks) but should be re-verified under `EXPLAIN` once a
  real multi-scope corpus exists.
- Curated knowledge entries consume the same `evidence_token_budget` as retrieved evidence — a large
  curated set could crowd out real retrieved evidence; `curated_knowledge_max_entries` is the initial
  guard, not a scaling guarantee.

## Paths governed

`apps/automation/app/features/{confluence_sync,ingestion,retrieval,rag_agent}/**`,
`apps/automation/app/platform/db/**`, `apps/automation/app/platform/config/settings.py`,
`apps/automation/alembic/**`, `apps/automation/scripts/**`, `packages/contracts/**`,
`apps/web/src/features/chat/**`.
