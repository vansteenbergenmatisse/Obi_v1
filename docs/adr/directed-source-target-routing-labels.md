# Directed-Connection Retrieval Routing (Option A)

Identifier: `ADR-directed-source-target-routing-labels` (formerly numbered 0020). File paths updated to the current layout (`backend/`, `frontend/`, `knowledge-base/`) on 2026-10-20; the decision is unchanged.

Status: Accepted
Date: 2026-10-09
Governs: the retrieval routing axis — `backend/app/features/retrieval/infrastructure/search_repo.py` (`_base_filters`), `backend/app/features/retrieval/application/retriever.py`, `backend/app/features/rag_agent/application/auth_context.py` + `server/token_verifier.py`, `backend/app/features/rag_agent/domain/prompt.py` (connection block), `backend/app/platform/config/product_catalog.py` (`build_labels`/`resolve_system`), `knowledge-base/schema/models.py` (`Chunk.labels`), the next ingestion migration (`0016_*`), `packages/contracts/src/token-claims.json`. Supersedes the routing semantics of ADR-knowledge-scope-tagging-and-filtering; amends the tagging model of ADR-source-id-row-security-with-reader-writer-roles and ADR-scope-state-materialized-as-tags. Does NOT touch ADR-supabase-postgres-store-without-force-rls / ADR-db-level-customer-scope-isolation-backstop / ADR-signed-token-verified-at-the-edge / ADR-page-acl-enforced-in-app-layer-only (customer isolation, scope backstop, edge-token, page-principal ACL) — those invariants stand.

## Context

Obi's shipped retrieval model (Phase 8, substeps 8.1.1–8.5.1; `docs/Final_docs/plan.md` §D)
routes on **membership slots**: the token carries `context.slots{pos,pms,accounting}` (which systems
a company *has*), the gate derives eligibility (general + each filled slot + the pairs POS-PMS and
PMS-Accounting), and an in-SQL applicability filter (migration 0015) narrows further. Direction is
not modeled — a Mews→Toast customer and a Toast→Mews customer are indistinguishable to the gate, and
a direct POS→Accounting pair is deliberately not derivable (decision-memo O1).

A dev handoff ("Obi page routing — Option A: how Obi picks pages") proposes a different model:
route each chat on a **directed `source → target` connection**, selecting pages by a hard filter on
exactly four Confluence label "boxes". The owner evaluated both (2026-10-09) and chose Option A on
the merits that matter for an accuracy-first assistant:

- **Precision / determinism.** A hard label pre-filter guarantees a chat cannot retrieve
  wrong-connection pages (a Mews→Toast chat can never see Toast→QuickBooks steps) — the single most
  reliable answer to cross-integration leakage, and aligned with the product rule "a wrong answer is
  not accepted" (`speed-vs-accuracy`).
- **Direction.** `toast-to-pms ≠ mews-to-pos` — the setup content genuinely differs by direction,
  which the slot model cannot express.
- **Speed / cost.** Filtering before top-k shrinks the candidate set the reranker and the LLM see.
- **Scalability.** A new system is one catalog line plus its labels; the routing rule is fixed.

The cost is accepted: a Confluence relabel to the new scheme, and a routing rebuild that supersedes
part of the shipped slot work. Much of the groundwork already exists — the product catalog already
holds `role` (= kind: pos/pms/accounting), slugs, aliases and `connection_types` with directions
(`pos_to_pms`, `pms_to_pos`, `pms_to_accounting`, `pos_to_accounting`), and the connection-block
renderer, the single filter chokepoint, the `tags`+GIN pattern, and the label-event webhook are all
present. There is no LightRAG/graph agent to change.

The full staged build is `docs/Final_docs/sync-rules/plan.md` → "Volgende stap — Option A:
directed-connection retrieval routing" (Stages 0–9). This ADR records the decision and its locked
parameters; it does not itself land code (implementation is staged and gated by this ADR).

## Decision

1. **Adopt directed-connection routing.** Every chat is one directed connection:
   `source_system → target_system` + `business_id`. At chat-start (once per chat) the backend
   resolves both systems in the product catalog, builds exactly four label boxes —
   `obi-general`, `{source.slug}-general`, `{target.slug}-general`, `{source.slug}-to-{target.kind}`
   — writes a connection block into the system prompt, and saves them on a chat-session row. Every
   question reuses the saved session (no re-lookup) and hard-filters hybrid search + rerank on those
   four labels before top-k. A partner switch refires chat-start and replaces the block and labels.

2. **Locked parameters (D0–D7).** These are the owner-confirmed defaults as of 2026-10-09:
   - **D0 — Labels replace scope tags as the content-routing axis.** The four routing labels become
     the content-routing dimension; the per-integration knowledge-scope tags (`obi-mews-test`, …)
     are retired for routing. Company/source isolation (ADR-source-id-row-security-with-reader-writer-roles source RLS, ADR-db-level-customer-scope-isolation-backstop scope backstop,
     `source_scope`, locks 0–2) is unchanged. Consequence: the Confluence corpus is relabelled to
     `obi-general` / `{slug}-general` / `{slug}-to-{kind}` (owner/content task).
     > **Updated 2026-10-12 by ADR-routing-labels-sole-content-axis.** D0 originally kept the knowledge-scope tags as a
     > membership tag (a page still needed `obi-general-test` to index). ADR-routing-labels-sole-content-axis retires that axis
     > **outright**: index membership is now "published + ≥1 recognized routing label + not
     > `classified`", with no base `-test` tag. The routing-label axis (`chunk.labels`,
     > `app.allowed_labels`, `chunk_labels_read`) is the sole content axis; `chunk_source_read`
     > (source/company isolation) is still unchanged.
   - **D1 — Filter enforced at the RLS/GUC layer, not only in SQL text.** A new `labels text[]`
     column on `chunk` (+ partial GIN `WHERE is_active`), a new `app.allowed_labels` GUC, and a
     RESTRICTIVE RLS policy mirroring `chunk_scope_read`, plus the app-layer `labels && :session_labels`
     overlap in `_base_filters`. This keeps never-bend rule 1 (RLS) and rule 3 (no read looser than
     the search) intact — a raw `WHERE`-only filter would violate rule 3 and is rejected.
   - **D2 — Unlabelled pages are invisible under an active connection filter** (empty array overlaps
     nothing; self-gating).
   - **D3 — A label-only change restamps the `labels` column via the existing metadata-only path, no
     re-embed.** This intentionally diverges from the handoff's "re-ingest" wording, justified because
     labels do not change embeddings; it matches how `tags` already update.
   - **D4 — Direction granularity is `{source.slug}-to-{target.kind}`** (source product → target
     kind). Splitting the box by specific target product is deferred (handoff Q3).
   - **D5 — Accounting is a first-class target.** O4's "accounting inert" is retired for routing;
     `pms-to-accounting` and `pos-to-accounting` are valid. Launch behavior is content-gated: route
     when the box has pages, refuse with a reason when it is empty.
   - **D6 — A chat reads only its four boxes.** A Toast→Mews chat does not also open `mews-to-pos`
     for Mews-side setup. Deferred (handoff Q1).
   - **D7 — One directed connection per chat.** A multi-system customer picks one pair per chat;
     more is a partner switch.

3. **Token contract.** A third, optional structured form is added to `token-claims.json`:
   `source_system` + `target_system` (canonical catalog ids) + `business_id` (≈ `company_id`). The
   legacy single `integration` claim and the `context.slots` form stay *accepted* for backward
   compatibility but no longer drive routing. The contracts schema, the `REQUIRED_CLAIMS` drift test,
   the OpenAPI `chat.yaml`, and `token_verifier.py` change together. The gate validates source/target
   against the catalog (unknown → 400 before any search); the request body never decides the
   connection (never-bend rules 2–3).

4. **Supersession is explicit, never silent.** Every superseded statement in `plan.md` §D,
   `decision-memo.md` (O1/O4/O5), `context-contract.md` §5.2 and `docs/plan/decisions.md`
   (`partner-token-handover`) carries a dated "SUPERSEDED by Option A (ADR-directed-source-target-routing-labels)" note; the old text
   is kept for provenance. A new `decisions.md` row (`connection-routing`) supersedes
   `partner-token-handover`.

5. **Invariants that MUST hold.** The eight sync rules; RLS locks 0–2 and the §D access invariants;
   never-bend rule 3 (no read looser than the search — hence D1); rule 8 (at most two extra reads);
   lock-0 edge-JWT verification (ADR-signed-token-verified-at-the-edge). Any Stage that would weaken these is a blocking
   regression, not an increment.

## Consequences

- **Supersedes** the routing semantics of ADR-knowledge-scope-tagging-and-filtering (knowledge-scope tagging drove retrieval
  filtering by per-integration scope; routing now uses directed connection labels). **Amends**
  ADR-source-id-row-security-with-reader-writer-roles and ADR-scope-state-materialized-as-tags (the `tags` axis gains a sibling `labels` axis with its own RLS policy;
  the tag taxonomy changes). The source-isolation and scope-backstop *mechanisms* they establish are
  reused, not removed.
- **Closes** decision-memo O1 (connection records beyond the three slots now exist, as directed
  labels) and **retires for routing** O4 (accounting inert) and O5 (`context.slots` is the fixed
  handover shape — still accepted, no longer the routing contract).
- **Requires a Confluence content relabel** (D0) before Option A serves production content; until
  then it runs against relabelled test pages. This is the single largest operational cost and is an
  owner/content-team task (plan Stage 7).
- **The applicability stamp (migration 0015 / `applicability.py`) becomes dead for routing** but its
  column and plumbing remain as data; a page can otherwise pass the label boxes yet be dropped by a
  stale stamp, so routing is made authoritative and slot-eligibility is retired (plan Stage 0/6).
- **Partner handover changes:** Data Hub and Base vend `source_system`/`target_system`/`business_id`
  rather than `context.slots`; the Jasper/Marien drafts are rewritten accordingly (plan Stage 9).
- **This ADR gates the build.** No routing code lands until Stage 0 (this ADR + the `decisions.md`
  row) and Stage 1 (design-page panels) are complete; the design page remains the source of truth.
