# Retire the Knowledge-Scope `-test` Tags; Routing Labels Are the Sole Content Axis

Identifier: `ADR-routing-labels-sole-content-axis` (formerly numbered 0021). File paths updated to the current layout (`backend/`, `frontend/`, `knowledge-base/`) on 2026-10-20; the decision is unchanged.

Status: Accepted
Date: 2026-10-12
Governs: `knowledge-base/config/knowledge_scopes.json`, `knowledge-base/config/platforms.json`,
`knowledge-base/config/platforms.local.json`, `backend/app/platform/config/knowledge_scopes.py`,
`backend/app/platform/config/settings.py`, `backend/app/platform/config/platforms.py`,
`backend/app/features/retrieval/infrastructure/search_repo.py` (`apply_knowledge_scope`,
`_base_filters`), `backend/app/features/retrieval/application/retriever.py`,
`backend/app/features/retrieval/domain/knowledge_scope.py`,
`backend/app/features/rag_agent/application/auth_context.py`,
`backend/app/features/rag_agent/application/answer_service.py`,
`backend/app/features/rag_agent/infrastructure/curated_knowledge_repo.py`,
`backend/app/features/confluence_sync/domain/ingest_decision.py`,
`knowledge-base/migrations/versions/0018_*` (new), the widget's dead `knowledgeScope` prop.
Supersedes ADR-knowledge-scope-tagging-and-filtering in full (its `obi-…-test` knowledge-scope axis is retired). Completes ADR-directed-source-target-routing-labels
D0 (it said the scope tags were "retired for routing"; this retires them outright and makes labels
the only content axis). Does NOT touch source/company isolation (ADR-source-id-row-security-with-reader-writer-roles `chunk_source_read`),
the Supabase anon fences (ADR-vision-grounded-image-analysis), the edge-token verification (ADR-signed-token-verified-at-the-edge), or the label routing
axis (ADR-directed-source-target-routing-labels migration 0016).

## Context

ADR-knowledge-scope-tagging-and-filtering introduced a knowledge-scope axis: a page had to carry a recognized Confluence label
(`obi-general-test`, `obi-mews-test`, `obi-operacloud-test`, `obi-toast-test`) to enter the index,
those labels were stamped on `chunk.tags`, and retrieval hard-filtered on `tags && :knowledge_scopes`
behind a RESTRICTIVE RLS policy (`chunk_scope_read`, GUC `app.allowed_knowledge_scopes`).

ADR-directed-source-target-routing-labels (directed-connection routing) added a second, independent axis: routing labels on a
separate `chunk.labels` column, filtered by `labels && :session_labels` behind its own RESTRICTIVE
policy (`chunk_labels_read`, GUC `app.allowed_labels`). D0 said the knowledge-scope tags were
"retired **for routing**" but kept them as a membership/isolation axis, so a page still needed
`obi-general-test` to index — which is exactly why the relabelled test corpus (nine routing-label
pages, no `-test` tag) did not index.

The owner's decision (2026-10-12): the knowledge-scope `-test` axis is redundant and is retired
entirely. The `obi-general-test` base tag is **not** kept as a hidden membership tag, and no other
mandatory base tag replaces it. Routing labels become the sole content-eligibility axis; company and
source isolation stay exactly as they are.

The DB layer makes this clean: source, scope and labels are **three separate policies** on `chunk`
(no combined policy), so the scope axis is removable without touching source isolation. The only
PERMISSIVE policy on `chunk` is `chunk_source_read` (source isolation); the scope and labels policies
are both RESTRICTIVE and AND on top of it.

## Decision

1. **Index membership = published + at least one recognized routing label + not `classified`.**
   `confluence_sync/domain/ingest_decision.py` decides membership on the page's routing labels
   (validated against the product catalog's label forms — `obi-general`, `{slug}-general`,
   `{slug}-to-{pos|pms|accounting}`), not on knowledge-scope tags. Removing the last recognized
   routing label removes the page from the index (empty → `delete`). The reserved `classified`
   label still always removes (never-bend rule 5, unchanged). The `source_scope` authorization
   gate (which space/page roots are eligible to ingest at all) is unchanged — it is the ingestion
   allow-list, not the knowledge-scope axis.

2. **Retrieval filters on routing labels only.** The scope-tag filter is removed: the
   `apply_knowledge_scope` chokepoint, the `tags && :knowledge_scopes` predicate in `_base_filters`,
   the `allowed_scopes` plumbing on `AuthContext`, and the `resolve_allowed_scopes` resolver are
   retired. `labels && :session_labels` (`app.allowed_labels`) is the only content filter. Source
   isolation (`app.allowed_sources`) and label routing are set on every reader transaction exactly
   as before (never-bend rule 3 — no read looser than the search).

   *As-built note (2026-10-20):* the scope **filter** is gone, but `apply_knowledge_scope` still
   exists in `search_repo.py` and still sets the `app.allowed_knowledge_scopes` GUC (to the
   wildcard) on each reader transaction, because the downgrade of migration
   `0018_retire_knowledge_scope_rls.py` re-creates policies that read it. It filters nothing at
   head. The `tags && :knowledge_scopes` predicate is likewise inert, since `allowed_scopes` is always
   empty.

3. **Config.** `knowledge_scopes.json` keeps only the reserved `classified` entry (the delete
   signal); the four `obi-…-test` scopes are removed. Startup validation no longer requires a
   general scope; it still requires `classified` present, still rejects uppercase and duplicates.
   `platforms.json` / `platforms.local.json` drop the `integration → [obi-…-test]` scope maps (the
   backend otherwise fails the `platforms.py` cross-check at boot). The product-catalog rule that
   forbids `obi-*`/`classified`/`general` as a product id/alias stays.

4. **RLS migration (reversible).** A new forward migration `0018` drops the two scope-tag policies
   via the existing idempotent helpers — `schema.drop_chunk_scope_rls` (`chunk_scope_read`) and
   `schema.drop_curated_scope_rls` (`curated_knowledge_entry_scope_read`). `downgrade()` re-applies
   them via `schema.apply_chunk_scope_rls` / `schema.apply_curated_scope_rls`, so the migration is
   fully reversible. The GUC `app.allowed_knowledge_scopes` is then referenced by no policy. The
   `chunk.tags` / `page_source.tags` columns and their GIN index are left as inert data (no column
   drop — avoids a destructive, slow rewrite; nothing reads them after this).

5. **`classified` is retained** as an overriding exclusion/deletion signal only — it is present in
   `knowledge_scopes.json`, never offered, never selectable, and a `classified` Confluence label
   removes a page from the index (design rule 5).

6. **Isolation is preserved.** `chunk_source_read` (source/company isolation, the only PERMISSIVE
   `chunk` policy), the three `*_reader_read` anon fences, the non-chunk RLS enables, and
   `chat_session` RLS are untouched. After this change a `chunk` row's visibility is
   `chunk_source_read (permissive) AND chunk_labels_read (restrictive)` — source isolation intact,
   routing labels the content filter. For `curated_knowledge_entry`, dropping its RESTRICTIVE scope
   policy leaves its PERMISSIVE `rag_reader` read policy: curated entries become visible to any
   reader session regardless of scope (the intended effect of retiring the scope axis); the anon
   fence is unaffected (anon has no matching permissive policy).

## Consequences

- **Supersedes ADR-knowledge-scope-tagging-and-filtering in full.** Its knowledge-scope tagging, retrieval scope-filter, and the
  `obi-…-test` names no longer exist in code or config. The `curated_knowledge_entry` table, its
  `tags` column and the curated-prompt layer remain (ADR-knowledge-scope-tagging-and-filtering Decision 7), now unscoped.
- **Completes ADR-directed-source-target-routing-labels D0.** D0's "retired for routing" becomes "retired outright"; the corpus needs
  no `-test` membership tag. The nine relabelled routing-label pages now index on their routing
  label alone.
- **Data.** The live vector store was wiped to 0 for the relabel (owner-attested; independent
  re-verification from the build environment is blocked by a production-read guard and is an
  owner/operator step). No corpus data is deleted by this change; the `-test` values exist only in
  config and test fixtures, which are updated. The `chunk.tags` column is left in place as inert
  data.
- **Widget.** The dead `knowledgeScope` request-body field (already ignored by the backend since
  ADR-db-level-customer-scope-isolation-backstop) is removed from the widget provider and its tests.
- **Reversibility.** `0018` downgrade restores both scope policies. The config change is a text
  edit. No embeddings change.
- **Invariants that MUST hold (unchanged):** never-bend rule 1 (RLS never disabled on Supabase —
  this migration only drops two RESTRICTIVE policies, re-exposing nothing to anon), rule 3 (no read
  looser than the search — the remaining source + label filters are set on every reader txn), the
  edge-JWT verification, and company/source isolation.
