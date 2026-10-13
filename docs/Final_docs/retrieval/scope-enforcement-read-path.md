# Scope enforcement on the read path (RLS GUCs + search filters)

> **⚠️ PARTIALLY RETIRED by ADR-0021 (2026-10-12).** The KNOWLEDGE-SCOPE axis
> (`app.allowed_knowledge_scopes`, `apply_knowledge_scope`, the `tags && :knowledge_scopes`
> predicate, and the `chunk_scope_read` / `curated_knowledge_entry_scope_read` RLS policies) is
> **retired** — migration `0018` drops those two policies and the retrieval path now opts the scope
> GUC out (wildcard). The SOURCE axis (`apply_source_scope` / `app.allowed_sources` /
> `chunk_source_read`) is **unchanged** and still the source/company isolation fence, and the
> ROUTING-LABEL axis (`app.allowed_labels` / `chunk_labels_read`, see
> `directed-label-hardfilter.md`) is now the sole content filter. This doc has been rewritten to
> describe today's two live axes; the retired knowledge-scope material is kept below in a clearly
> marked subsection for provenance.

- **Workflow:** retrieval
- **Owning code:** `backend/app/features/retrieval/infrastructure/search_repo.py` (the GUC
  appliers `apply_source_scope` / `apply_allowed_labels` / `apply_hnsw_gucs` and the search SQL;
  `apply_knowledge_scope` remains but is opted out to the wildcard); consumed by `retriever.py`
  (one search transaction), parent expansion, and the curated lookup in `rag_agent`.
- **Design panel:** `r3-scope` · `tg-filter`
- **Status:** Implemented — source isolation (live fence) + routing-label content filter (live);
  the knowledge-scope axis is retired (ADR-0021, migration 0018).

## What it does

Every database read in retrieval runs inside a transaction that first sets its RLS GUCs from the
request's one authorization context, each via `set_config(..., is_local=true)` with bound
parameters. Two axes are live today:

**Source axis — the isolation fence (unchanged).** `apply_source_scope` sets
`app.allowed_sources` from the authorization context. The PERMISSIVE `chunk_source_read` policy
reads it: a chunk is visible only when its `source_id` is in the allowed source list. This is the
source/company isolation boundary (lock 1), fail-closed, and is untouched by ADR-0021.

**Routing-label axis — the content filter (live).** `apply_allowed_labels` sets
`app.allowed_labels` from the session's directed-connection labels. The RESTRICTIVE
`chunk_labels_read` policy reads it: a chunk is visible only when its `labels` array overlaps the
session labels (`labels && string_to_array(guc, ',')`), with `'*'` as the explicit opt-out
sentinel (a legacy/slot/tokenless chat sets `'*'`, so the filter is a no-op there — labels are the
relevance axis, not the access fence). This is the sole content-routing filter; its mechanics and
proofs live in `directed-label-hardfilter.md` (panel `mi-hardfilter`).

The search SQL carries the same filters as its own predicates (active, child kind, current status,
source list, label overlap) for correctness and planner use — RLS stays the security net
underneath. Since 8.3.1 the same `WHERE` clause also carries the applicability/eligibility
predicate when a verified customer context is present (`eligibility-filtering.md`): it narrows
INSIDE what these access filters already allow and never replaces them — parent expansion and the
curated lookup stay access-only, reached solely from ids the filtered search produced.

GUC *values* are validated at this choke point before being joined: `None` means the
internal/eval wildcard; a list may not contain an element with an embedded `,` or `*` — either
raises `ValueError` before any SQL runs, because the policy splits the GUC on commas and compares
the whole value to `'*'`, so such an element would semantically widen access (the G14 finding,
closed 2026-10-05). This discipline applies to both live axes.

## Why it does it

Never-bend rule 3: one authorization context per request, and no read runs under looser rules
than the search. Source isolation and the routing-label filter are both set on every reader
transaction (search, rerank text, curated lookup, parent expansion), so no read runs looser than
the search. ADR-0004 set the bound-parameter GUC discipline after the injection review.
`is_local=true` scopes each GUC to its transaction so pooled connections cannot leak one request's
values into the next. Binding alone stops SQL-syntax injection but not value-semantics collision —
that is why the element validation exists: `string_to_array` cannot tell one element containing
`"mews,toast"` from two elements, and a joined value of `"*"` is indistinguishable from the
intentional sentinel.

## How we know it works

- **Unit** (`retrieval/tests/test_search_repo_gucs.py`): the source applier emits bound-param SQL
  (never interpolated), `None` → `'*'`, `[]` → `''` (fail closed); the hnsw GUC whitelist rejects
  an injection string. `retrieval/tests/test_s_reader_session_binding.py` pins that `dense_search`,
  `fetch_page_scopes` and `fetch_rerank_texts` each run on the one GUC-bound reader session (G10).
  The routing-label applier (`apply_allowed_labels`) and overlap are proven in
  `retrieval/tests/test_search_repo_labels.py` (see `directed-label-hardfilter.md`).
- **Database:** source isolation under `rag_reader` (`test_reader_vector_access.py` — a
  nearer-but-forbidden ANN hit in another source is never returned) and the routing-label
  include/exclude proofs (`retrieval/tests/test_label_hardfilter_db.py`). The two repurposed
  isolation E2E tests now exercise source-scoped membership and cross-subject cache isolation under
  the new axis set (ADR-0021).
- **Live:** source isolation and the GUC/RLS mechanics were proven on Supabase (as `rag_reader`)
  in the 2026-09-25 proof recorded in `docs/Final_docs/sync-rules/plan.md` §0; migration 0018
  (dropping the scope policies) is proven on the local pinned pgvector only — the Supabase apply is
  an owner/operator step (see the ledger's ADR-0021 entry).
- Proof fragments for the 4.2 additions: `docs/Final_docs/4-test-foundation/test-proof.md`.

## Retired (ADR-0021) — the knowledge-scope axis

Historical, no longer live. ADR-0011 added a second GUC, `app.allowed_knowledge_scopes`, set by
`apply_knowledge_scope` from the authorization context's `allowed_scopes`. Two RESTRICTIVE policies
read it — `chunk_scope_read` on `chunk` and `curated_knowledge_entry_scope_read` on
`curated_knowledge_entry` — making a row visible only when its `tags` array overlapped the allowed
scopes (`tags && string_to_array(guc, ',')`), with `'*'` as the opt-out and an unset/empty GUC
failing closed. ADR-0014 made that RLS the flag-independent backstop (the app-layer
`enable_knowledge_scope_filtering` predicate was redundant defence, default off).

ADR-0021 retired this axis: migration `0018` drops both policies (reversibly — `downgrade()`
re-applies them), the authorization context now derives no `allowed_scopes` (empty everywhere),
and `retriever.py` / the curated lookup opt `app.allowed_knowledge_scopes` out to the wildcard
`None`. The GUC is now read by no policy. The `chunk.tags` / `page_source.tags` columns and their
GIN index remain as inert data (no column drop). The historical proofs — cross-scope read blocked,
unset-GUC denial, the G14 semantic-injection cases — are in
`confluence_sync/tests/test_customer_isolation_backstop.py` against the pre-0018 policy; the
two knowledge-scope security E2E tests were repurposed (not deleted) under ADR-0021. Source/company
isolation (`chunk_source_read`) was always a separate PERMISSIVE policy and is unaffected.
